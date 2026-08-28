"""
Quiz Service — structured quiz generation, grading, and state machine.

Design goals:
- One LLM call generates the full 10-question quiz as STRICT JSON. The LLM
  is never asked to grade, advance, or re-derive the next question.
- Every subsequent interaction (topic selection, answering, advancing,
  scoring) is pure Python. No re-parsing of free-text LLM output, no regex
  matchers looking for "Question N of 10", no risk of the model drifting
  onto an unrelated question or fabricating a student turn.
- Quiz state lives on Conversation.quiz_state (JSON column) so it survives
  page refreshes and server restarts.
"""
from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from providers.factory import llm_client


# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────────────────

# Asks the LLM to suggest 5 distinct quiz topics derived from the
# reference material. Strict JSON output, no free text.
QUIZ_TOPICS_PROMPT = """You are a strict data-extraction tool. You do NOT converse. You do NOT explain.
You ONLY output one JSON object and nothing else.

Reference Material:
{context}

Task: Extract exactly 5 DISTINCT, NON-REPETITIVE topics from the Reference Material that would make good short quizzes.
Every topic MUST be supported by substantive content in the Reference Material.

Output EXACTLY this JSON shape and nothing else (no markdown fences, no preamble, no trailing text):
{{
  "language": "{target_language}",
  "topics": ["Topic 1", "Topic 2", "Topic 3", "Topic 4", "Topic 5"]
}}
"""


# Asks the LLM to generate the full 10-question quiz as strict JSON. The
# questions are tagged with topic so we can filter by the user's selection.
QUIZ_QUESTIONS_PROMPT = """You are a strict quiz-generation tool. You do NOT converse. You do NOT explain.
You ONLY output one JSON object and nothing else.

Reference Material:
{context}

Chosen topic: {topic}
Output language: {target_language}

Task: Generate EXACTLY 12 multiple-choice questions about the chosen topic, based STRICTLY on the Reference Material above. The application will select the first 10 unique questions.
Do NOT invent facts from outside the Reference Material.

RULES:
- Each question MUST have exactly 4 options labelled "A", "B", "C", "D".
- Exactly one option per question MUST be correct.
- The "correct_key" field MUST be one of "A", "B", "C", "D".
- Questions should progress in difficulty (start easier, get harder).
- Keep stems short and unambiguous. Each option short (one line or less).
- Questions MUST cover different facts, people, events, concepts, dates, or
    relationships from the Reference Material. Do not ask the same fact using
    different wording, and do not create a second question whose answer is
    already tested by another question.
- When the chosen topic is "All Topics (Mixed)", distribute questions across
    the different sections/topics in the Reference Material. Do not focus on
    the preface or one introductory paragraph.
- Do not use vague answers such as "the author and others" unless the exact
    phrase and the complete set of people are explicitly stated in the source.
- Output language MUST be {target_language}.
- "explanation" must briefly justify the correct answer using Reference Material (one concise sentence).
- CRITICAL: each explanation MUST be SPECIFIC to that question's stem and
  the chosen correct option. Do NOT reuse the same wording across multiple
  questions. If the question asks "what inspired X", explain what inspired X.
  If it asks "who were the beneficiaries", explain who the beneficiaries
  were. The explanation should never feel copy-pasted.

Output EXACTLY this JSON shape and nothing else (no markdown fences, no preamble, no trailing text):
{{
  "language": "{target_language}",
  "questions": [
    {{
      "id": "q1",
      "topic": "{topic}",
      "stem": "Question text here?",
      "options": [
        {{"key": "A", "text": "Option A"}},
        {{"key": "B", "text": "Option B"}},
        {{"key": "C", "text": "Option C"}},
        {{"key": "D", "text": "Option D"}}
      ],
      "correct_key": "B",
      "explanation": "Why B is correct according to the Reference Material."
    }}
  ]
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# JSON extraction (defensive — the LLM sometimes wraps JSON in fences)
# ─────────────────────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Pull the first complete JSON object out of an LLM response. The model
    occasionally wraps the object in markdown fences or pads it with text;
    we strip the fences and find the outermost braces before parsing.

    The Cloudflare Llama model is configured (or pre-disposed) to return
    JSON as a parsed Python dict directly, in which case `raw` is already
    a dict and we can short-circuit. Gemini and other providers always
    return a string, so we go through the normal fence-strip + parse path.
    """
    if raw is None:
        return None

    # Short-circuit: the LLM already gave us a parsed dict/list. We only
    # accept dicts (the quiz payloads are always JSON objects), not bare
    # lists or scalars.
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (list, int, float, bool)):
        return None
    if not isinstance(raw, str):
        return None

    candidate = raw.strip()
    if not candidate:
        return None

    fence_match = _FENCE_RE.search(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    obj_match = _OBJECT_RE.search(candidate)
    if obj_match:
        candidate = obj_match.group(0)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

class QuizService:
    """Owns the structured quiz lifecycle."""

    # Limits / invariants — keep the LLM honest by validating every response.
    MIN_TOPICS = 3
    MIN_QUESTIONS = 5
    VALID_KEYS = {"A", "B", "C", "D"}
    QUESTION_COUNT = 10

    # ── LLM call #1: propose topics ──────────────────────────────────────
    async def generate_topics(
        self,
        context_chunks: List[Dict[str, Any]],
        target_language: str,
    ) -> Optional[List[str]]:
        """
        Return a list of 3–5 suggested quiz topics derived from the reference
        material, or None if generation fails. The student picks one (or
        'All Topics' / a free-typed one).
        """
        context = self._format_context(context_chunks)
        if not context.strip():
            return None

        prompt = QUIZ_TOPICS_PROMPT.format(
            context=context,
            target_language=target_language,
        )
        try:
            raw = await llm_client.generate_response_async(prompt)
        except Exception as exc:
            print(f"QUIZ topic generation failed: {exc!r}", flush=True)
            return None
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return None

        topics = data.get("topics")
        if not isinstance(topics, list) or len(topics) < self.MIN_TOPICS:
            return None

        cleaned = [str(t).strip() for t in topics if str(t).strip()]
        return cleaned[:5] if len(cleaned) >= 5 else (cleaned if len(cleaned) >= self.MIN_TOPICS else None)

    # ── LLM call #2: build the full quiz ─────────────────────────────────
    async def generate_questions(
        self,
        context_chunks: List[Dict[str, Any]],
        topic: str,
        target_language: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Generate the full list of quiz questions for the chosen topic. Each
        question dict is validated and re-keyed so downstream grading only
        ever has to look up `correct_key`.
        """
        context = self._format_context(context_chunks)
        if not context.strip():
            return None

        prompt = QUIZ_QUESTIONS_PROMPT.format(
            context=context,
            topic=topic,
            target_language=target_language,
        )
        try:
            raw = await llm_client.generate_response_async(prompt)
        except Exception as exc:
            print(f"QUIZ question generation failed: {exc!r}", flush=True)
            return None
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return None

        questions = data.get("questions")
        if not isinstance(questions, list) or len(questions) < self.MIN_QUESTIONS:
            print(
                f"QUIZ question payload invalid: expected at least {self.MIN_QUESTIONS} questions, "
                f"got {len(questions) if isinstance(questions, list) else type(questions).__name__}",
                flush=True,
            )
            return None

        validated: List[Dict[str, Any]] = []
        seen_signatures = set()
        seen_stem_words: List[set[str]] = []
        for idx, q in enumerate(questions, start=1):
            v = self._validate_question(q, idx, topic)
            if v is None:
                continue
            signature = self._question_signature(v)
            stem_words = self._normalized_words(v.get("stem", ""))
            if signature in seen_signatures or any(
                self._jaccard(stem_words, previous_words) >= 0.84
                for previous_words in seen_stem_words
            ):
                continue
            seen_signatures.add(signature)
            seen_stem_words.append(stem_words)
            validated.append(v)
            if len(validated) == self.QUESTION_COUNT:
                break

        if len(validated) < self.QUESTION_COUNT:
            print(
                f"QUIZ question validation kept {len(validated)}/{self.QUESTION_COUNT} unique questions",
                flush=True,
            )
            return None
        return validated

    # ── Pure-Python state-machine: build a fresh quiz_state ──────────────
    def new_quiz_state(
        self,
        *,
        language: str,
        topic: str,
        topics: List[str],
        questions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build the initial quiz_state object that lives on Conversation.quiz_state."""
        return {
            "language": language,
            "topic": topic,
            "topics": topics,
            "questions": questions,
            "current_index": 0,
            "score": 0,
            "completed": False,
            "history": [],
        }

    # ── Pure-Python state-machine: grade an answer and advance ───────────
    def grade_answer(
        self,
        quiz_state: Dict[str, Any],
        selected_key: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Grade the student's selected option against the current question's
        correct_key, append the result to history, advance current_index,
        and mark the quiz complete if the last question was just answered.

        Returns (updated_quiz_state, result_dict) where result_dict has:
            - is_correct (bool)
            - correct_key (str)
            - explanation (str)
            - question (dict) — the question that was just answered
            - next_question (dict|None) — the next question, or None if done
            - finished (bool)
            - score (int)
            - total (int)
        """
        # JSON columns are not automatically dirty-tracked for nested in-place
        # mutations. Work on a new object so assigning the result back to the
        # Conversation always persists current_index, score, and history.
        quiz_state = deepcopy(quiz_state)
        idx = quiz_state["current_index"]
        questions = quiz_state["questions"]
        question = questions[idx]

        selected_key = (selected_key or "").strip().upper()
        correct_key = (question.get("correct_key") or "").strip().upper()
        is_correct = selected_key == correct_key and selected_key in self.VALID_KEYS

        # Record the attempt in history
        history_entry = {
            "index": idx,
            "question_id": question.get("id"),
            "selected": selected_key,
            "correct": is_correct,
        }
        quiz_state.setdefault("history", []).append(history_entry)

        new_score = quiz_state.get("score", 0) + (1 if is_correct else 0)
        quiz_state["score"] = new_score
        quiz_state["current_index"] = idx + 1

        finished = quiz_state["current_index"] >= len(questions)
        if finished:
            quiz_state["completed"] = True

        next_q = questions[quiz_state["current_index"]] if not finished else None

        result = {
            "is_correct": is_correct,
            "correct_key": correct_key,
            "explanation": question.get("explanation", ""),
            "question": question,
            "next_question": next_q,
            "finished": finished,
            "score": new_score,
            "total": len(questions),
        }
        return quiz_state, result

    # ── Pure-Python helper: render the current question for display ──────
    def current_question(self, quiz_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if quiz_state.get("completed"):
            return None
        idx = quiz_state.get("current_index", 0)
        questions = quiz_state.get("questions", [])
        if idx >= len(questions):
            return None
        return questions[idx]

    # ── Internals ────────────────────────────────────────────────────────
    def _format_context(self, chunks: List[Dict[str, Any]]) -> str:
        parts = []
        for i, chunk in enumerate(chunks or [], 1):
            text = str(chunk.get("text") or "").strip()
            if not text:
                continue
            parts.append(f"--- Reference Text {i} ---\n{text}\n")
        return "\n".join(parts) if parts else ""

    def _validate_question(
        self,
        q: Any,
        idx: int,
        topic: str,
    ) -> Optional[Dict[str, Any]]:
        """Reject malformed questions so a bad LLM response can't break grading."""
        if not isinstance(q, dict):
            return None

        stem = str(q.get("stem") or "").strip()
        options = q.get("options")
        correct_key = str(q.get("correct_key") or "").strip().upper()
        explanation = str(q.get("explanation") or "").strip()

        if not stem or not explanation:
            return None
        if correct_key not in self.VALID_KEYS:
            return None
        if not isinstance(options, list) or len(options) != 4:
            return None

        seen_keys = set()
        clean_options = []
        for opt in options:
            if not isinstance(opt, dict):
                return None
            key = str(opt.get("key") or "").strip().upper()
            text = str(opt.get("text") or "").strip()
            if key not in self.VALID_KEYS or not text:
                return None
            if key in seen_keys:
                return None
            seen_keys.add(key)
            clean_options.append({"key": key, "text": text})

        if len(clean_options) != 4:
            return None
        if correct_key not in seen_keys:
            return None

        return {
            "id": str(q.get("id") or f"q{idx}"),
            "topic": str(q.get("topic") or topic),
            "stem": stem,
            "options": clean_options,
            "correct_key": correct_key,
            "explanation": explanation,
        }

    def _question_signature(self, question: Dict[str, Any]) -> str:
        """Return a stable signature used to reject repeated question ideas."""
        return " ".join(sorted(self._normalized_words(question.get("stem", ""))))

    def _normalized_words(self, text: str) -> set[str]:
        normalized = unicodedata.normalize("NFKD", text).lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)
        return {word for word in normalized.split() if len(word) > 1}

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        union = left | right
        return len(left & right) / len(union) if union else 1.0


# Module-level singleton — quiz service is stateless aside from the LLM
# client, so a single instance is enough.
quiz_service = QuizService()
