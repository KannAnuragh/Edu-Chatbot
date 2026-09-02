"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

import re


class UngroundedTopicError(Exception):
    """
    Raised by build_rag_prompt when a quiz topic has no supporting chunks —
    i.e. context_chunks is empty, which chat_service.py already guarantees
    happens whenever nothing cleared RELEVANCE_THRESHOLD (0.30) during
    retrieval. We check emptiness here rather than re-scoring, since the
    real filtering already happened upstream.

    We stopped trusting the model to self-police this after it fabricated
    full quizzes on unrelated topics (e.g. "French Revolution" against a
    Right-to-Information-Act course) even when explicitly instructed not
    to — a prompt-only instruction was not reliable enough on its own.

    Callers MUST catch this and send `.fallback_message` straight to the
    student WITHOUT calling the LLM at all.
    """
    def __init__(self, fallback_message: str):
        self.fallback_message = fallback_message
        super().__init__(fallback_message)

SYSTEM_PROMPT = """You are a helpful and precise educational tutor. Your task is to answer the student's question accurately, thoroughly, and directly using the provided Reference Material.

CORE RULES:
1. STRICT LANGUAGE MATCHING (CRITICAL):
- You MUST answer in the EXACT SAME LANGUAGE as the student's question.
- If the question is in English and the Reference Material is in Malayalam, you MUST TRANSLATE all information into English and answer ENTIRELY in English. NEVER respond in Malayalam to an English question.
- If the question is in Malayalam, respond in Malayalam.
- NEVER mix languages in the same response.

2. THOROUGH & COMPREHENSIVE EXPLANATIONS (CRITICAL):
- Do NOT provide brief or one-sentence summaries if the Reference Material contains more details.
- Provide a rich, detailed, and comprehensive educational explanation.
- Break down key concepts, historical facts, causes, effects, names, and important points thoroughly.
- Structure your response cleanly using paragraphs, bullet points, and bold headers to make it clear and easy to study.

3. STRICT CONTEXT GROUNDING & FALLBACK:
- If the Reference Material does not contain the information required to answer the question, or if the question is off-topic/unrelated:
  Respond ONLY with:
  "I do not have enough information to answer this question based on the course materials." (if asked in English)
  or
  "കോഴ്‌സ് വിവരങ്ങളുടെ അടിസ്ഥാനത്തിൽ ഈ ചോദ്യത്തിന് ഉത്തരം നൽകാൻ ആവശ്യമായ വിവരങ്ങൾ ലഭ്യമല്ല." (if asked in Malayalam)
- NEVER explain why you cannot answer.
- NEVER mention "Reference Material", "Reference Text", or discuss what the entity means.
- NEVER suggest unrelated topics from the Reference Material.
- NEVER output follow-up questions on fallback responses. Stop immediately.

4. ABSOLUTELY NO PREAMBLES:
- When you can answer the question, start IMMEDIATELY with the actual answer.
- NEVER begin with phrases like "Based on the provided material", "According to the reference text", "The document mentions", or "In the provided context".

5. ACCURACY & SPELLING:
- The Reference Material may contain minor PDF extraction or font artifacts. Correct them into standard, grammatically correct spelling in your response.

6. FOLLOW-UP QUESTIONS:
- ONLY when you have successfully provided a substantive answer from the Reference Material, include up to 3 short, relevant follow-up questions after the main answer using the exact delimiter below:
===FOLLOWUP_QUESTIONS===
["Question 1","Question 2","Question 3"]
- The delimiter must appear on its own line immediately after the final sentence of the main answer.
- After the delimiter, output ONLY valid JSON with a top-level array of strings, not markdown bullets, not bracketed [FOLLOWUP: ...] lines, and not any introduction text.
- If the answer is a fallback response, do NOT include the delimiter or any follow-up questions.

7. QUICK COMMANDS:
- If the message is EXACTLY "Explain a concept", respond EXACTLY with: "Sure, which concept would you like me to explain?"
- If the message is EXACTLY "Generate Cheat Sheet", respond EXACTLY with: "I’ll generate a cheat sheet from your course material."

8. QUIZ MODE OVERRIDE:
- While GRADING an existing quiz answer (evaluating the student's response to a question already asked), the fallback rule (Rule 3) does NOT apply. You must evaluate the student's answer (marking Correct! or Not quite.) and ask the next question. NEVER output the "I do not have enough information" fallback while grading.
- However, when a NEW quiz topic has just been chosen (before Question 1 is written), Rule 3 DOES apply: only start the quiz if the Reference Material actually contains real, substantive content on that topic. If the student picks a topic not covered by the Reference Material (including a free-typed topic via "type your own topic"), do NOT invent questions from general knowledge — output the standard fallback message instead and do not ask a question.
"""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Student Question: {question}

>>> {language_directive} <<<

Instructions:
1. If the answer is NOT present in the Reference Material or if the question is off-topic, respond ONLY with:
"I do not have enough information to answer this question based on the course materials." (if asked in English)
or
"കോഴ്‌സ് വിവരങ്ങളുടെ അടിസ്ഥാനത്തിൽ ഈ ചോദ്യത്തിന് ഉത്തരം നൽകാൻ ആവശ്യമായ വിവരങ്ങൾ ലഭ്യമല്ല." (if asked in Malayalam)
Do not write anything else, do not suggest alternative topics from the text, and do not add follow-up questions.
2. If the answer IS present in the Reference Material:
- Provide a THOROUGH, COMPREHENSIVE, and DETAILED explanation in {target_language}.
- Extract and explain all relevant points, facts, concepts, and details from the Reference Material. Do not give a brief or superficial summary.
- Format your response with clear paragraphs, bullet points, and bold terms where helpful for studying.
- Translate from the Malayalam reference material if the question is in English.
- Start directly with the answer (no preambles like "Based on the text").
3. At the very end of a successful answer (NOT on fallback), insert the exact delimiter on its own line:
===FOLLOWUP_QUESTIONS===
Then output a valid JSON array of up to 3 strings in {target_language}, for example:
["Question 1","Question 2","Question 3"]
Do NOT write any introductory text before the delimiter or after it."""

CHEAT_SHEET_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Student Request: {question}

>>> {language_directive} <<<

You are an expert tutor creating a compact, high-yield cheat sheet from the course materials.
Use ONLY the Reference Material above. Do not invent facts outside the course.

Rules:
- Combine and deduplicate the most important facts from all provided chunks.
- Output clean Markdown only.
- Use exactly these 3 sections, in order:
## Key Formulas
## Essential Vocabulary & Terms
## Core Rules & Principles
- Each section must contain bullet points only.
- Keep each bullet short and high-yield.
- Max 8 bullet points per section.
- If a section has no relevant items, use a short bullet like "No clear formula found in this material."
- Do not add intro text, conclusions, or follow-up questions.
- Do not wrap the response in code fences.
- Be concise but specific.

Output ONLY the Markdown cheat sheet.
"""

EXPLAIN_CONCEPT_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Concept: {concept}
Depth mode: {mode}

>>> {language_directive} <<<

You are an expert tutor. Explain the concept using ONLY the Reference Material.
Do not invent facts. Output clean Markdown only, with no introduction or conclusion.
Keep the response under 350 words and follow the selected structure exactly.

If the Reference Material does not contain substantive information about the
concept, output only: I do not have enough information to explain this concept
based on the course materials.

Selected output structure:
{structure}
"""


def build_explain_concept_prompt(
    context_chunks: list,
    conversation_history: list,
    concept: str,
    mode: str,
) -> str:
    """Build a compact, mode-specific concept explanation prompt."""
    context = "\n\n".join(
        f"--- Reference Text {index} ---\n{chunk.get('text', '')}"
        for index, chunk in enumerate(context_chunks, 1)
    ) or "No reference material available."
    history = "\n\n".join(
        f"{'Student' if item.get('role') == 'user' else 'Assistant'}: {item.get('content', '')}"
        for item in conversation_history
    ) or "No previous conversation."
    malayalam_chars = len(re.findall(r'[\u0D00-\u0D7F]', concept))
    target_language = "MALAYALAM" if malayalam_chars >= 2 else "ENGLISH"
    language_directive = (
        "MANDATORY OUTPUT LANGUAGE: MALAYALAM. Write in Malayalam script."
        if target_language == "MALAYALAM"
        else "MANDATORY OUTPUT LANGUAGE: ENGLISH. Translate source material into English."
    )
    structures = {
        "ELI5": (
            "SIMPLE EXPLANATION (use this structure only):\n"
            "1. **Core Idea**: exactly one simple sentence.\n"
            "2. **Everyday Example**: exactly two sentences using a familiar situation.\n"
            "3. **Remember These**: exactly three short bullet points.\n"
            "4. **Common Misconception**: exactly one bullet point.\n"
            "Do not use technical definitions, exam questions, formulas, or a related-concepts section."
        ),
        "DEEP_DIVE": (
            "DEEP DIVE (use this structure only):\n"
            "1. **Technical Definition**: exactly one precise sentence.\n"
            "2. **Mechanics**: three to five detailed bullet points explaining how it works; include formulas only when present in the source.\n"
            "3. **Conditions and Edge Cases**: exactly three precise bullet points.\n"
            "4. **Related Concepts**: exactly three connections, each with a one-sentence explanation.\n"
            "Do not use analogies, exam questions, or a simple-summary section."
        ),
        "EXAM_FOCUSED": (
            "EXAM-FOCUSED (use this structure only):\n"
            "1. **10-Second Summary**: exactly one high-yield sentence.\n"
            "2. **Likely Exam Questions**: exactly two bullet points phrased as questions, with a short answer after each.\n"
            "3. **Must-Include Keywords**: exactly five bold terms, each followed by a brief meaning.\n"
            "4. **Common Trap**: exactly one bullet point describing a likely mistake.\n"
            "Do not use analogies, formulas-and-mechanics, edge-case, or related-concepts sections."
        ),
    }
    safe_mode = mode if mode in structures else "ELI5"
    return EXPLAIN_CONCEPT_PROMPT_TEMPLATE.format(
        context=context,
        history=history,
        concept=concept,
        mode=safe_mode,
        structure=structures[safe_mode],
        language_directive=language_directive,
    )

QUIZ_START_PROMPT_TEMPLATE = """Reference Material:
{context}

You are a strict data extraction tool. You do NOT converse. You do NOT explain. You ONLY output the requested template.
Extract 5 DISTINCT, NON-REPETITIVE topics from the Reference Material for a quiz.
Output EXACTLY this format and nothing else. DO NOT write full sentences. DO NOT write "Sure, here are". ONLY output this exact template:

Sure, which topic should I ask from?
1. [Topic 1]
2. [Topic 2]
3. [Topic 3]
4. [Topic 4]
5. [Topic 5]
6. All Topics (Mixed)
7. Something else — type your own topic
"""

QUIZ_FIRST_QUESTION_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Student Message (Chosen Topic): {question}

>>> {language_directive} <<<

CRITICAL INSTRUCTION: You are in QUIZ MODE. The student has just selected a topic for their quiz.

GROUNDING CHECK (do this FIRST, before anything else):
- Look at the Reference Material above. Does it contain real, substantive content about "{question}"?
- If NO — the Reference Material is empty, unrelated, or only mentions the topic in passing — do NOT invent quiz questions from general knowledge. Instead output ONLY this (translated into {target_language} if needed) and STOP, asking nothing further:
  "I do not have enough information to create a quiz on this topic based on the course materials. Please choose one of the topics listed earlier, or pick a different topic from your course."
- If YES, continue below and ask the FIRST question based on the Reference Material related to this topic.

RULES (only if the grounding check above passed):
- Ask exactly ONE question at medium difficulty.
- Format the question clearly:
  **Question 1 of 10:**
  [Question text]
  
  (You may provide multiple choice options A, B, C, D, or ask a direct question).
- Every question and its correct answer MUST come from the Reference Material — never from outside knowledge.
- Wait for the student to answer. DO NOT REVEAL THE ANSWER.
- Do NOT output any preambles.
- After asking the question, STOP IMMEDIATELY. Do not write "Student Answer", do not invent or simulate what the student might say, and do not continue the conversation on the student's behalf.
- ALWAYS respond in {target_language}.
"""

QUIZ_EVAL_AND_NEXT_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Previous Question (grade the Student Answer against THIS question ONLY — ignore any other question mentioned elsewhere in the history):
{previous_question_block}

Student Answer: {question}

>>> {language_directive} <<<

CRITICAL INSTRUCTION: You are in QUIZ MODE acting as a strict, rigorous Quiz Master.
You must grade the student's answer with 100% accuracy before continuing.

STEP 1 — STRICT EVALUATION (NO FALSE POSITIVES):
- Use ONLY the "Previous Question" block above (not any earlier question in the history) to find the true answer in the Reference Material.
- If the previous question had options (A, B, C, D):
  * Determine which option letter is TRUE according to the Reference Material.
  * Check the student's selected letter (e.g. "A", "B", "C", "D").
  * If the student chose the WRONG letter (e.g. student chose D, but correct was B):
        You MUST start with: **Not quite.** The correct answer is [Correct Option Letter]: [Correct explanation].
    * Only if the student chose the EXACT correct letter, start with: **Correct!** [Brief explanation].
- If the question was open-ended:
  * If the student gave an incorrect, inaccurate, or off-topic answer:
        You MUST start with: **Not quite.** [Explain the true answer from Reference Material].
    * If accurate, start with: **Correct!** [Brief explanation].
- Your explanation MUST be about the Previous Question shown above — never reuse or repeat an explanation that belongs to a different, earlier question.
- CRITICAL: Never say Correct if the student picked the wrong option or wrote a wrong fact!

{step2_instruction}

STRICT RULES:
- NEVER output "I do not have enough information to answer this question...".
- NEVER ask more than ONE question per turn.
- NEVER re-ask a question that has already been asked in the Previous Conversation.
- After asking the next question (or after showing the final score, if the quiz is complete), STOP GENERATING IMMEDIATELY. NEVER write "Student Answer", invent what the student might say, or grade more than the ONE answer given to you in this turn.
- ALWAYS respond in {target_language}.
"""

_QUESTION_MARKER_RE = re.compile(r"\*{0,2}Question\s+(\d+)\s+of\s+10\*{0,2}\s*:?", re.IGNORECASE)


def _extract_last_question(conversation_history: list) -> dict:
    """
    Walk backward through history and find the most recent "Question N of 10"
    marker the assistant produced, returning its number and the full
    question text (stem + options) that followed it.

    Used instead of asking the LLM to re-find and increment the question
    number itself from the raw history blob: that's what caused the same
    question getting re-asked, and grading explanations drifting onto an
    earlier, unrelated question.
    """
    for msg in reversed(conversation_history):
        if msg.get('role') != 'assistant':
            continue
        content = msg.get('content', '')
        matches = list(_QUESTION_MARKER_RE.finditer(content))
        if matches:
            last_match = matches[-1]
            number = int(last_match.group(1))
            question_text = content[last_match.start():].strip()
            return {"number": number, "text": question_text}
    return {"number": 0, "text": ""}


def build_cheat_sheet_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """Build a markdown cheat sheet prompt grounded in the actual PDF chunks."""
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        text = chunk.get('text', '')
        context_parts.append(f"--- Reference Text {i} ---\n{text}\n")

    context_str = "\n".join(context_parts) if context_parts else "No reference material available."

    history_str = ""
    if conversation_history:
        for msg in conversation_history:
            role_val = msg.get('role', '')
            role = "Student" if role_val == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n\n"

    malayalam_chars = len(re.findall(r'[\u0D00-\u0D7F]', question))
    if malayalam_chars >= 2:
        target_language = "MALAYALAM"
        language_directive = "MANDATORY OUTPUT LANGUAGE: MALAYALAM. Write the cheat sheet in Malayalam script."
    else:
        target_language = "ENGLISH"
        language_directive = "MANDATORY OUTPUT LANGUAGE: ENGLISH. Even if the source material is Malayalam, translate the key facts into English."

    return CHEAT_SHEET_PROMPT_TEMPLATE.format(
        context=context_str,
        history=history_str,
        question=question,
        target_language=target_language,
        language_directive=language_directive,
    )


def build_rag_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """
    Build the full RAG prompt with context, history, and question.

    Args:
        context_chunks: List of dicts with text, filename, page_number, score.
        conversation_history: List of dicts with role and content.
        question: The user's current question.

    Returns:
        Formatted prompt string.
    """
    # Format context with reference headers
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        text = chunk.get('text', '')
        context_parts.append(
            f"--- Reference Text {i} ---\n"
            f"{text}\n"
        )
        
    context_str = "\n".join(context_parts) if context_parts else "No reference material available."
    
    # Format history
    history_str = ""
    if conversation_history:
        for msg in conversation_history:
            role_val = msg.get('role', '')
            role = "Student" if role_val == "user" else "Assistant"
            history_str += f"{role}: {msg.get('content', '')}\n\n"

    # Detect Question Language
    malayalam_chars = len(re.findall(r'[\u0D00-\u0D7F]', question))
    if malayalam_chars >= 2:
        target_language = "MALAYALAM"
        language_directive = "MANDATORY OUTPUT LANGUAGE: MALAYALAM. Write your entire response and follow-up questions in Malayalam script."
    else:
        target_language = "ENGLISH"
        language_directive = "MANDATORY OUTPUT LANGUAGE: ENGLISH. The question is in English. Even though the Reference Material is in Malayalam, you MUST TRANSLATE all information and write your ENTIRE response in ENGLISH. Do NOT output Malayalam script. Follow-up questions must also be in English."
            
    # Determine if we are in quiz mode and which phase
    is_quiz = False
    quiz_phase = 0 # 0: none, 1: start (suggest topics), 2: Q&A
    
    if question.strip().lower() == "quiz me":
        is_quiz = True
        quiz_phase = 1
    else:
        for msg in reversed(conversation_history):
            content = msg.get('content', '').lower()
            role = msg.get('role', '')
            if role == 'user' and content == 'quiz me':
                is_quiz = True
                quiz_phase = 2
                break
            if role == 'assistant' and 'quiz complete' in content:
                is_quiz = False
                break
                
    extra_kwargs = {}

    if not is_quiz:
        prompt_template = RAG_PROMPT_TEMPLATE
    elif quiz_phase == 1:
        prompt_template = QUIZ_START_PROMPT_TEMPLATE
    else:
        # Check if the previous message was a question or topic list
        last_assistant_msg = ""
        for msg in reversed(conversation_history):
            if msg.get('role', '') == 'assistant':
                last_assistant_msg = msg.get('content', '').lower()
                break
        
        if "question " in last_assistant_msg:
            prompt_template = QUIZ_EVAL_AND_NEXT_PROMPT_TEMPLATE

            last_q = _extract_last_question(conversation_history)

            if last_q["number"] >= 10:
                step2_instruction = (
                    "STEP 2 — QUIZ COMPLETE:\n"
                    "- Do NOT ask another question.\n"
                    "- Count the total correct answers across the whole quiz using the Previous Conversation.\n"
                    "- Output exactly:\n"
                    "**Quiz Complete!**\n"
                    "**Your Score: X/10**\n"
                    "(Add a brief encouraging summary.)"
                )
            else:
                next_number = last_q["number"] + 1
                step2_instruction = (
                    "STEP 2 — ASK NEXT QUESTION:\n"
                    "- Ask a NEW, distinct question from the Reference Material that has not been asked yet.\n"
                    f"- Label it EXACTLY: **Question {next_number} of 10:**\n"
                    "- ADAPT DIFFICULTY: ask an easier factual question if the student's last answer was wrong, "
                    "a harder conceptual one if it was right.\n"
                    "- Do NOT reveal the answer to the new question."
                )

            extra_kwargs["previous_question_block"] = (
                last_q["text"] or "(not found — grade cautiously and do not guess)"
            )
            extra_kwargs["step2_instruction"] = step2_instruction
        else:
            prompt_template = QUIZ_FIRST_QUESTION_PROMPT_TEMPLATE

            # Deterministic grounding check — chat_service.py already filters
            # chunks by RELEVANCE_THRESHOLD before calling this function, so
            # an empty list here means nothing relevant was found. Reject the
            # topic in code rather than trusting the LLM's own judgment,
            # which has not proven reliable for this (see UngroundedTopicError).
            if not context_chunks:
                if target_language == "MALAYALAM":
                    fallback = (
                        "കോഴ്‌സ് വിവരങ്ങളുടെ അടിസ്ഥാനത്തിൽ ഈ വിഷയത്തിൽ ക്വിസ് "
                        "തയ്യാറാക്കാൻ ആവശ്യമായ വിവരങ്ങൾ ലഭ്യമല്ല. ദയവായി മുകളിൽ "
                        "പറഞ്ഞ വിഷയങ്ങളിൽ ഒന്ന് തിരഞ്ഞെടുക്കുക."
                    )
                else:
                    fallback = (
                        "I do not have enough information to create a quiz on this "
                        "topic based on the course materials. Please choose one of "
                        "the topics listed earlier, or pick a different topic from "
                        "your course."
                    )
                raise UngroundedTopicError(fallback)
    
    return prompt_template.format(
        context=context_str,
        history=history_str or "No previous conversation.",
        question=question,
        target_language=target_language,
        language_directive=language_directive,
        **extra_kwargs
    )

QUERY_OPTIMIZATION_PROMPT = """You are a search engine optimization expert. Your task is to convert the user's latest message into a highly effective search query for a vector database.

Conversation History:
{history}

User's Latest Message: {query}

Instructions:
1. If the message is a greeting or casual chat, just return the exact message.
2. If the message refers to previous context (e.g. "tell me more about it"), include the relevant context in the search query.
3. If the message is a bare quiz answer — a single option letter (A/B/C/D), "true/false", or another very short reply that only makes sense next to a preceding question — do NOT use it as the query. It carries no retrievable meaning on its own. Instead, rewrite the query as the question it is answering, pulled from the Conversation History.
4. The query MUST be in the exact same language and script as the source text used for the query (the user's latest message, or the previous question if rule 3 applies). Do NOT translate it.
5. ONLY return the optimized query string. Do NOT add quotes or explanations.

Optimized Query:"""