"""
Chat Service.

Orchestrates RAG retrieval, prompt assembly, and SSE streaming.
Includes relevance filtering, detailed chunk logging, and token usage tracking.
"""

import json
import time
import asyncio
import re
from uuid import UUID
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.conversation import Conversation, Message, MessageRole
from services.retrieval_service import RetrievalService
from services.quiz_service import quiz_service
from llm.prompts import build_rag_prompt, build_cheat_sheet_prompt, build_explain_concept_prompt, UngroundedTopicError
from providers.factory import llm_client
from ingestion.pipeline import fix_malayalam_pdf_font_artifacts

from core.database import async_session_factory

# Minimum cosine similarity score to consider a chunk relevant
RELEVANCE_THRESHOLD = 0.30

# Pre-compiled regex patterns for chunk sanitization (avoid recompiling per-call)
_RE_LONG_NUMBERS = re.compile(r'[0-9]{15,}')
_RE_SCERT_HEADER = re.compile(r'സാമൂഹ്യശാസ്[്രത]*ം.*?സംസ്കാരവും ദശീേയതയും')
_RE_MULTI_SPACES = re.compile(r'\s+')
_RE_EXPLANATION_NOTE = re.compile(
    r'(?im)^\s*note:\s*(?:the\s+)?reference\s+material\s+does\s+not\s+contain[^\n]*(?:\n|$)'
)

def sanitize_chunk_text(text: str) -> str:
    """Dynamically clean chunk text before sending to LLM to remove PDF extraction artifacts."""
    if not text:
        return ""
    # 1. Remove long numerical FML artifacts (like 12345678901234567890...)
    text = _RE_LONG_NUMBERS.sub('', text)
    # 2. Remove repeating SCERT PDF headers and footers
    text = _RE_SCERT_HEADER.sub('', text)
    # 3. Apply the dynamic font artifact fixer (in case chunks were embedded BEFORE the new pipeline)
    text = fix_malayalam_pdf_font_artifacts(text)
    # 4. Clean up any remaining multiple spaces left by deletions
    text = _RE_MULTI_SPACES.sub(' ', text).strip()
    return text


def clean_explanation_response(text: str) -> str:
    """Remove model metadata notes before an explanation reaches the chat."""
    cleaned = _RE_EXPLANATION_NOTE.sub('', text or '').strip()
    return cleaned or "I could not find enough course material to explain this topic."


class ChatService:
    """Service for handling chat conversations."""
    
    def __init__(self):
        self.retrieval = RetrievalService()
        
    async def process_chat(
        self,
        course_id: UUID,
        message_text: str,
        user_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Full RAG pipeline and SSE streaming response.
        """
        try:
            async with async_session_factory() as db:
                pipeline_start = time.time()
                
                # 1. Get or create conversation
                if not conversation_id:
                    conversation = Conversation(
                        user_id=user_id,
                        course_id=course_id,
                        # Simple title generation from first message
                        title=message_text[:30] + "..." if len(message_text) > 30 else message_text
                    )
                    db.add(conversation)
                    await db.flush()
                    conversation_id = conversation.id
                else:
                    # Verify conversation exists and belongs to user (if user is provided)
                    query = select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.course_id == course_id
                    )
                    if user_id is not None:
                        query = query.where(Conversation.user_id == user_id)

                    result = await db.execute(query)
                    conversation = result.scalar_one_or_none()
                    if not conversation:
                        yield f"event: error\ndata: {json.dumps({'error': 'Conversation not found'})}\n\n"
                        return

                # Keep routing metadata out of the visible conversation history.
                stored_user_message = message_text
                if message_text.lower().startswith("explain concept|"):
                    parts = message_text.split("|", 2)
                    if len(parts) == 3 and parts[2].strip():
                        stored_user_message = parts[2].strip()
                elif message_text.lower().startswith("cheat sheet:"):
                    stored_user_message = message_text.split(":", 1)[1].strip() or message_text

                # 2. Save user message
                user_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content=stored_user_message,
                )
                db.add(user_msg)
                await db.commit()

                # Load history early so the chapter-selection cheat-sheet flow can
                # build its prompt without an uninitialized variable.
                history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                )
                all_messages = history_result.scalars().all()
                history_messages = all_messages[:-1] if len(all_messages) > 1 else []

                # Send conversation ID to client immediately
                yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation_id)})}\n\n"

                # ─────────────────────────────────────────────────────────
                # STRUCTURED QUIZ STATE MACHINE
                # ─────────────────────────────────────────────────────────
                # The quiz has three phases, all driven by conversation.quiz_state:
                #   1. "quiz me"          -> quiz_state with topics, awaiting topic pick
                #   2. topic selected     -> quiz_state with full questions, current_index=0
                #   3. user submits A/B/C/D -> grade in Python, advance, emit next question
                # After completion (current_index >= len(questions)) we clear the
                # state and fall through to normal RAG on the next message.
                #
                # Grading is PURE PYTHON — no LLM call. The LLM is only used
                # twice: once to suggest topics, once to generate the full
                # question set as strict JSON. Everything else is deterministic.
                quiz_state = conversation.quiz_state if hasattr(conversation, "quiz_state") else None
                is_quiz_me = message_text.strip().lower() == "quiz me"

                if is_quiz_me or quiz_state:
                    async for chunk in self._handle_quiz_flow(
                        db=db,
                        conversation=conversation,
                        user_message=message_text,
                        existing_quiz_state=quiz_state,
                        is_quiz_me=is_quiz_me,
                        course_id=course_id,
                        user_id=user_id,
                    ):
                        yield chunk
                    return

                # ── End of quiz state machine ──

                # --- FAST PATH FOR SUGGESTION COMMANDS ---
                message_text_clean = message_text.strip()
                fast_response = None
                if message_text_clean == "Explain a concept":
                    yield f"event: explain_prompt\ndata: {json.dumps({'modes': ['ELI5', 'DEEP_DIVE', 'EXAM_FOCUSED']})}\n\n"
                    fast_response = "Choose a concept and depth mode."
                # NOTE: "Quiz me" and cheat-sheet flows are handled below with
                # topic selection and retrieval so the content stays focused.

                if fast_response:
                    # Yield token instantly
                    yield f"event: token\ndata: {json.dumps({'text': fast_response})}\n\n"
                    
                    # Save assistant message
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=fast_response,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    
                    yield "event: done\ndata: {}\n\n"
                    return
                # ----------------------------------------

                if message_text_clean.startswith("Explain Concept|"):
                    _, mode, concept = message_text_clean.split("|", 2)
                    concept = concept.strip()
                    mode = mode.strip().upper()
                    raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                        user_id=str(user_id) if user_id else None,
                        course_id=str(course_id),
                        query=concept,
                        top_k=5,
                    )
                    chunks = [
                        dict(chunk, text=sanitize_chunk_text(chunk.get('text', '')))
                        for chunk in raw_chunks
                        if chunk.get('score', 0.0) >= RELEVANCE_THRESHOLD
                    ][:5]
                    history = [{"role": msg.role.value, "content": msg.content} for msg in history_messages]
                    prompt = build_explain_concept_prompt(chunks, history, concept, mode)
                    raw_response = await llm_client.generate_response_async(prompt)
                    full_response = clean_explanation_response(str(raw_response or ""))
                    yield f"event: token\ndata: {json.dumps({'text': full_response})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=full_response,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                # Send conversation ID to client immediately
                yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation_id)})}\n\n"

                # Cheat-sheet selection flow: user clicks the suggestion, then the
                # UI sends a chosen chapter name like "Cheat Sheet: Indian Constitution".
                if message_text_clean == "Generate Cheat Sheet":
                    broad_chunks = await self._retrieve_quiz_chunks(
                        course_id=course_id,
                        user_id=user_id,
                        queries=[
                            "chapter topics sections themes units headings",
                            "main concepts government system institutions events people",
                        ],
                    )
                    if not broad_chunks:
                        fallback = "I do not have enough course material to generate chapter-based cheat sheets yet."
                        yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=fallback,
                            sources=[],
                        )
                        db.add(assistant_msg)
                        await db.commit()
                        yield "event: done\ndata: {}\n\n"
                        return

                    topics = await quiz_service.generate_topics(broad_chunks, "ENGLISH")
                    if not topics:
                        fallback = "I could not find chapter headings in the course material. Please try another course or document."
                        yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=fallback,
                            sources=[],
                        )
                        db.add(assistant_msg)
                        await db.commit()
                        yield "event: done\ndata: {}\n\n"
                        return

                    yield f"event: quiz_topics\ndata: {json.dumps({'language': 'ENGLISH', 'topics': topics, 'mode': 'cheat_sheet'})}\n\n"
                    yield f"event: token\ndata: {json.dumps({'text': 'Choose a chapter to build the cheat sheet.'})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content='Choose a chapter to build the cheat sheet.',
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                last_assistant_text = ""
                for previous_message in reversed(history_messages):
                    if previous_message.role == MessageRole.ASSISTANT:
                        last_assistant_text = previous_message.content.strip().lower()
                        break

                is_typed_cheat_sheet_topic = (
                    last_assistant_text == "choose a chapter to build the cheat sheet."
                    and message_text_clean != "Generate Cheat Sheet"
                    and not message_text_clean.startswith("Explain Concept|")
                )
                has_cheat_sheet_prefix = message_text_clean.lower().startswith("cheat sheet:")
                if has_cheat_sheet_prefix or is_typed_cheat_sheet_topic:
                    selected_topic = message_text_clean[len("Cheat Sheet:"):].strip() if has_cheat_sheet_prefix else message_text_clean
                    if not selected_topic:
                        selected_topic = "chapter overview"

                    yield f"event: cheat_sheet\ndata: {json.dumps({'topic': selected_topic})}\n\n"

                    # Retrieve only the selected chapter/topic.
                    raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                        user_id=str(user_id) if user_id else None,
                        course_id=str(course_id),
                        query=selected_topic,
                        top_k=30,
                    )

                    relevant_chunks = []
                    for c in raw_chunks:
                        score = c.get('score', 0.0)
                        if score >= RELEVANCE_THRESHOLD:
                            relevant_chunks.append(c)

                    chunks = relevant_chunks[:8]
                    if not chunks:
                        fallback = f"I could not find enough material for the chapter '{selected_topic}'. Please choose a different chapter."
                        yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                        assistant_msg = Message(
                            conversation_id=conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=fallback,
                            sources=[],
                        )
                        db.add(assistant_msg)
                        await db.commit()
                        yield "event: done\ndata: {}\n\n"
                        return

                    for c in chunks:
                        c['text'] = sanitize_chunk_text(c.get('text', ''))

                    history = [{"role": msg.role.value, "content": msg.content} for msg in history_messages]
                    prompt = build_cheat_sheet_prompt(
                        context_chunks=chunks,
                        conversation_history=history,
                        question=f"Generate a cheat sheet for {selected_topic}",
                    )

                    full_response = ""
                    async for text_chunk in llm_client.stream_response(prompt):
                        if text_chunk:
                            full_response += text_chunk
                            yield f"event: token\ndata: {json.dumps({'text': text_chunk})}\n\n"

                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=full_response,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return
                # ----------------------------------------

                # 2.5. Load history + conditionally optimize search query
                yield f"event: status\ndata: {json.dumps({'message': 'Searching documents...'})}\n\n"
                
                # OPTIMIZATION: Skip the expensive LLM query-optimization call when:
                # 1. No conversation history (first message — nothing to resolve)
                # 2. Message is self-contained (>50 chars — unlikely to be "tell me more")
                needs_optimization = bool(history_messages) and len(message_text.strip()) <= 50
                
                t_opt_start = time.time()
                if needs_optimization:
                    from llm.prompts import QUERY_OPTIMIZATION_PROMPT
                    history_str = ""
                    for msg in history_messages[-6:]:
                        role = "Student" if msg.role == MessageRole.USER else "Assistant"
                        history_str += f"{role}: {msg.content}\n"
                    
                    opt_prompt = QUERY_OPTIMIZATION_PROMPT.format(history=history_str, query=message_text)
                    
                    # Use native async instead of asyncio.to_thread (avoids thread pool overhead)
                    optimized_query = await llm_client.generate_response_async(opt_prompt)
                    
                    if not optimized_query:
                        optimized_query = message_text
                    else:
                        optimized_query = optimized_query.strip()
                    
                    t_opt_end = time.time()
                    print(f"⏱️ [QUERY OPTIMIZATION] Took {t_opt_end - t_opt_start:.2f}s | Original: '{message_text}' | Optimized: '{optimized_query}'", flush=True)
                else:
                    optimized_query = message_text
                    t_opt_end = time.time()
                    print(f"[QUERY OPTIMIZATION] Skipped (no history or self-contained query) | Using raw query: '{message_text}' | {t_opt_end - t_opt_start:.4f}s", flush=True)

                # 3. Retrieve relevant chunks using the (possibly optimized) query
                t_retrieval_start = time.time()
                raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                    user_id=str(user_id) if user_id else None,
                    course_id=str(course_id),
                    query=optimized_query,
                    top_k=15  # Fetch more, then filter by relevance
                )
                t_retrieval_end = time.time()
                
                print(f"[CHAT DEBUG] Raw chunks retrieved from Qdrant: {len(raw_chunks)}", flush=True)
                
                course_filtered_chunks = raw_chunks
                
                print(f"[CHAT DEBUG] Chunks remaining after course filter: {len(course_filtered_chunks)}", flush=True)
                
                # RELEVANCE FILTERING: Only keep chunks above the similarity threshold
                relevant_chunks = []
                discarded_chunks = []
                for c in course_filtered_chunks:
                    score = c.get('score', 0.0)
                    if score >= RELEVANCE_THRESHOLD:
                        relevant_chunks.append(c)
                    else:
                        discarded_chunks.append(c)
                        
                print(f"[CHAT DEBUG] Chunks above threshold ({RELEVANCE_THRESHOLD}): {len(relevant_chunks)}", flush=True)
                
                # Only use chunks that exceed the relevance threshold to prevent hallucination from unrelated material
                if relevant_chunks:
                    chunks = relevant_chunks[:5]  # Cap at 5 best chunks for richer context
                else:
                    chunks = []
                    print(f"[RELEVANCE] All retrieved chunks scored below threshold {RELEVANCE_THRESHOLD}. Treating context as empty.", flush=True)
                
                # User requested to remove citations below the chat
                sources = []
                
                # ═══════════════════════════════════════════════════════════
                # DETAILED LOGGING FOR RENDER CLI / BACKEND LOGS
                # ═══════════════════════════════════════════════════════════
                print("\n" + "═" * 80, flush=True)
                print(f"[RAG RETRIEVAL] Optimized Query: '{optimized_query}'", flush=True)
                print(f"   Course ID: {course_id}", flush=True)
                print(f"   Retrieval time: {t_retrieval_end - t_retrieval_start:.3f}s", flush=True)
                print(f"   Raw chunks from vector DB: {len(raw_chunks)}", flush=True)
                print(f"   After course filter: {len(course_filtered_chunks)}", flush=True)
                print(f"   Above relevance threshold ({RELEVANCE_THRESHOLD}): {len(relevant_chunks)}", flush=True)
                print(f"   Discarded (below threshold): {len(discarded_chunks)}", flush=True)
                print(f"   Chunks sent to LLM: {len(chunks)}", flush=True)
                print("─" * 80, flush=True)
                
                # Log ALL chunks with full text
                for idx, c in enumerate(chunks, 1):
                    # Sanitize the chunk text dynamically before feeding to LLM
                    clean_text = sanitize_chunk_text(c.get('text', ''))
                    c['text'] = clean_text  # Update the chunk so build_rag_prompt uses the clean version
                    
                    score = c.get('score', 0.0)
                    print(f"\n  CHUNK #{idx} | Score: {score:.4f} | File: {c.get('filename')} | Page: {c.get('page_number')}", flush=True)
                    print(f"  {'─' * 60}", flush=True)
                    # Log full chunk text
                    for line in clean_text.split('\n'):
                        print(f"    {line}", flush=True)
                    print(f"  {'─' * 60}", flush=True)
                
                if discarded_chunks:
                    print(f"\n  DISCARDED CHUNKS (below {RELEVANCE_THRESHOLD} threshold):", flush=True)
                    for idx, c in enumerate(discarded_chunks, 1):
                        score = c.get('score', 0.0)
                        print(f"    #{idx} | Score: {score:.4f} | File: {c.get('filename')} | Page: {c.get('page_number')} | Text: {str(c.get('text', ''))[:100]}...", flush=True)
                
                print("═" * 80 + "\n", flush=True)

                # Send sources to client (empty list to hide citations)
                yield f"event: sources\ndata: {json.dumps(sources)}\n\n"

                # 4. Get conversation history (already loaded above)
                history = [
                    {"role": msg.role.value, "content": msg.content}
                    for msg in history_messages
                ]

                # 5. Build prompt
                try:
                    if message_text_clean == "Generate Cheat Sheet":
                        prompt = build_cheat_sheet_prompt(
                            context_chunks=chunks,
                            conversation_history=history,
                            question=message_text,
                        )
                    else:
                        prompt = build_rag_prompt(
                            context_chunks=chunks,
                            conversation_history=history,
                            question=message_text
                        )
                except UngroundedTopicError as e:
                    # Quiz topic isn't covered by the retrieved course
                    # material (chunks came back empty after relevance
                    # filtering above). Respond directly — skip the LLM
                    # call entirely rather than risk it fabricating a quiz
                    # from outside knowledge.
                    fallback_text = e.fallback_message
                    yield f"event: token\ndata: {json.dumps({'text': fallback_text})}\n\n"

                    assistant_msg = Message(
                        conversation_id=conversation_id,
                        role=MessageRole.ASSISTANT,
                        content=fallback_text,
                        sources=sources,
                    )
                    db.add(assistant_msg)
                    await db.commit()

                    yield "event: done\ndata: {}\n\n"
                    return
                
                # Log the assembled prompt
                print("═" * 80, flush=True)
                print("[ASSEMBLED PROMPT SENT TO LLM]", flush=True)
                print("─" * 80, flush=True)
                for line in prompt.split('\n'):
                    print(f"  {line}", flush=True)
                print("═" * 80 + "\n", flush=True)

                # 6. Stream LLM response
                t_llm_start = time.time()
                full_response = ""
                try:
                    async for text_chunk in llm_client.stream_response(prompt):
                        if text_chunk:
                            full_response += text_chunk
                            # SSE format: event: token\ndata: chunk\n\n
                            # We JSON encode the text to handle newlines properly
                            yield f"event: token\ndata: {json.dumps({'text': text_chunk})}\n\n"
                except Exception as e:
                    error_msg = f"\n\nError during generation: {str(e)}"
                    full_response += error_msg
                    yield f"event: token\ndata: {json.dumps({'text': error_msg})}\n\n"
                
                t_llm_end = time.time()

                # 7. Save assistant message
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    sources=sources,
                )
                db.add(assistant_msg)
                await db.commit()

                # ═══════════════════════════════════════════════════════════
                # PIPELINE SUMMARY LOG
                # ═══════════════════════════════════════════════════════════
                pipeline_end = time.time()
                input_tokens_est = len(prompt) // 4
                output_tokens_est = len(full_response) // 4
                
                print("\n" + "═" * 80, flush=True)
                print("[PIPELINE SUMMARY]", flush=True)
                print(f"   Query: '{message_text}'", flush=True)
                print(f"   Retrieval:    {t_retrieval_end - t_retrieval_start:.3f}s", flush=True)
                print(f"   LLM Response: {t_llm_end - t_llm_start:.3f}s", flush=True)
                print(f"   Total:        {pipeline_end - pipeline_start:.3f}s", flush=True)
                print(f"   ───────────────────────────────", flush=True)
                print(f"   Chunks sent to LLM: {len(chunks)}", flush=True)
                print(f"   Prompt length:  {len(prompt)} chars (~{input_tokens_est} tokens)", flush=True)
                print(f"   Response length: {len(full_response)} chars (~{output_tokens_est} tokens)", flush=True)
                print(f"   Est. total tokens: ~{input_tokens_est + output_tokens_est}", flush=True)
                print("═" * 80 + "\n", flush=True)

                # 8. Send completion event
                yield "event: done\ndata: {}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"FATAL STREAM ERROR: {tb}")
            error_msg = f"\n\nFatal error in stream processing: {str(e)}"
            yield f"event: token\ndata: {json.dumps({'text': error_msg})}\n\n"
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    # ─────────────────────────────────────────────────────────────────────
    # STRUCTURED QUIZ STATE MACHINE
    # ─────────────────────────────────────────────────────────────────────
    async def _handle_quiz_flow(
        self,
        *,
        db: AsyncSession,
        conversation: Conversation,
        user_message: str,
        existing_quiz_state: Optional[dict],
        is_quiz_me: bool,
        course_id: UUID,
        user_id: Optional[UUID],
    ) -> AsyncGenerator[str, None]:
        """
        Drive the entire quiz lifecycle. Three phases, all reading/writing
        conversation.quiz_state:

          Phase 1 — "quiz me"
              LLM proposes 3–5 topics from the reference material. We store
              them on quiz_state and emit a `quiz_topics` SSE event so the
              UI can render a topic picker.

          Phase 2 — user picks a topic (or "All Topics" / free text)
              We re-retrieve chunks scoped to that topic, call the LLM to
              generate the full 10-question quiz as strict JSON, and store
              it on quiz_state. Then emit `quiz_question` for Q1.

          Phase 3 — user submits A/B/C/D
              Pure Python. grade_answer() in QuizService mutates quiz_state
              (score, current_index, history) and returns the next question
              (or the final score). We emit `quiz_result` + (if more
              questions remain) `quiz_question`. No LLM call.

        If the quiz is already complete when the user sends a new message,
        we clear quiz_state and exit — the next iteration of process_chat
        (none, since we `return`) won't be reached; the user has to send
        a new message and we'll start fresh.
        """
        try:
            # Detect language from the user's current message (fallback to English).
            malayalam_chars = len(re.findall(r'[\u0D00-\u0D7F]', user_message))
            target_language = "MALAYALAM" if malayalam_chars >= 2 else "ENGLISH"

            # ── If a previous quiz is complete, clear state and let RAG handle
            #    this new message normally. We do this by NOT entering the quiz
            #    flow — but we got here because existing_quiz_state is truthy.
            if existing_quiz_state and existing_quiz_state.get("completed"):
                continue_answers = {
                    "yes", "y", "yeah", "yep", "sure", "ok", "okay",
                    "continue", "more", "more questions", "ask more",
                }
                stop_answers = {"no", "n", "nope", "stop", "quit", "done", "finish"}
                answer = user_message.strip().lower()

                if answer in continue_answers:
                    # Reuse the material topics, but put the topic just
                    # completed first so the student can revise it again.
                    current_topic = existing_quiz_state.get("topic")
                    previous_topics = existing_quiz_state.get("topics", [])
                    next_topics = [current_topic] if current_topic else []
                    next_topics.extend(
                        topic for topic in previous_topics
                        if topic != current_topic
                    )
                    next_topics = next_topics[:5]

                    conversation.quiz_state = {
                        "language": existing_quiz_state.get("language", target_language),
                        "topic": None,
                        "topics": next_topics,
                        "questions": [],
                        "current_index": 0,
                        "score": 0,
                        "completed": False,
                        "history": [],
                    }
                    await db.commit()

                    continue_text = "Sure. Choose a topic for the next 10 questions."
                    yield f"event: quiz_topics\ndata: {json.dumps({'language': target_language, 'topics': next_topics})}\n\n"
                    yield f"event: token\ndata: {json.dumps({'text': continue_text})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=continue_text,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                if answer in stop_answers:
                    conversation.quiz_state = None
                    await db.commit()
                    finish_text = "Okay. Your quiz is complete."
                    yield f"event: token\ndata: {json.dumps({'text': finish_text})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=finish_text,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                if is_quiz_me:
                    # New "quiz me" — restart the topic flow.
                    conversation.quiz_state = None
                    await db.commit()
                    existing_quiz_state = None
                else:
                    finish_text = "Reply Yes for 5 more questions, or No to finish."
                    yield f"event: token\ndata: {json.dumps({'text': finish_text})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=finish_text,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

            # ─────────────────────────────────────────────
            # PHASE 3: user submitted A/B/C/D → grade in pure Python
            # ─────────────────────────────────────────────
            # Triggered when we already have a chosen topic and at least one
            # question stored. We do NOT call the LLM here at all.
            if (
                existing_quiz_state
                and existing_quiz_state.get("topic")
                and existing_quiz_state.get("questions")
                and not existing_quiz_state.get("completed")
            ):
                target_language = existing_quiz_state.get("language", target_language)
                # The user's text is an answer choice. Normalise.
                selected = user_message.strip().upper()

                updated_state, result = quiz_service.grade_answer(
                    existing_quiz_state, selected
                )
                # Persist updated state immediately so a refresh mid-flight
                # doesn't roll the student back.
                conversation.quiz_state = updated_state
                await db.commit()

                # Emit the grading result event.
                result_payload = {
                    "is_correct": result["is_correct"],
                    "correct_key": result["correct_key"],
                    "explanation": result["explanation"],
                    "score": result["score"],
                    "total": result["total"],
                    "finished": result["finished"],
                }
                yield f"event: quiz_result\ndata: {json.dumps(result_payload)}\n\n"

                # Build the assistant's textual response.
                if result["is_correct"]:
                    feedback = "**Correct!**"
                else:
                    feedback = f"**Not quite.** The correct answer is **{result['correct_key']}**."
                if result["explanation"]:
                    feedback += f" {result['explanation']}"

                if result["finished"]:
                    summary = (
                        f"\n\n**Quiz Complete!**\n\n"
                        f"**Your Score: {result['score']}/{result['total']}**\n\n"
                        "Would you like 5 more questions? Reply **Yes** or **No**."
                    )
                    feedback = feedback + summary
                    yield f"event: token\ndata: {json.dumps({'text': feedback})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=feedback,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                # Not finished — emit the result feedback in the chat bubble
                # AND the next question as a structured QuizCard. The next
                # question is NOT rendered as markdown text (the QuizCard
                # below the bubble is the source of truth for the question
                # content — re-rendering the same stem twice was both
                # visually noisy and made repeated/wrong explanations look
                # like repeated questions).
                next_q = result["next_question"]
                next_idx = updated_state["current_index"]
                total = len(updated_state["questions"])

                # The chat bubble shows just the result feedback. The
                # frontend will append the QuizCard for the next question
                # alongside this message.
                yield f"event: token\ndata: {json.dumps({'text': feedback})}\n\n"
                yield f"event: quiz_question\ndata: {json.dumps(self._serialize_question(next_q, index=next_idx, total=total))}\n\n"
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=feedback,
                    sources=[],
                )
                db.add(assistant_msg)
                await db.commit()
                yield "event: done\ndata: {}\n\n"
                return

            # ─────────────────────────────────────────────
            # PHASE 1: "quiz me" → generate topic suggestions
            # ─────────────────────────────────────────────
            # Triggered only on a fresh "quiz me" request when there is no
            # existing quiz_state. If state already exists with topic=null,
            # we treat the user's input as a topic pick (handled by
            # Phase 2 below) instead of regenerating the topic list.
            if is_quiz_me and not existing_quiz_state:
                yield f"event: status\ndata: {json.dumps({'message': 'Preparing quiz...'})}\n\n"

                # Pull reference chunks (one retrieval covers both topic
                # extraction and question generation).
                chunks = await self._retrieve_quiz_chunks(
                    course_id=course_id,
                    user_id=user_id,
                    queries=[
                        "course chapters main topics concepts events people",
                        "historical developments social political economic cultural topics",
                    ],
                )

                if not chunks:
                    # No reference material — fall back gracefully.
                    fallback = (
                        "കോഴ്‌സ് വിവരങ്ങളുടെ അടിസ്ഥാനത്തിൽ ക്വിസ് തയ്യാറാക്കാൻ ആവശ്യമായ വിവരങ്ങൾ ലഭ്യമല്ല."
                        if target_language == "MALAYALAM"
                        else "I do not have enough information to create a quiz based on the course materials."
                    )
                    yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=fallback,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                topics = await quiz_service.generate_topics(chunks, target_language)
                if not topics:
                    fallback = (
                        "I couldn't identify any quiz topics in the course materials right now. Please try again."
                    )
                    yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                    assistant_msg = Message(
                        conversation_id=conversation.id,
                        role=MessageRole.ASSISTANT,
                        content=fallback,
                        sources=[],
                    )
                    db.add(assistant_msg)
                    await db.commit()
                    yield "event: done\ndata: {}\n\n"
                    return

                # Persist topics; questions will be generated on the next turn
                # once the student picks a topic (so the LLM is asked to
                # generate quiz content for the actual topic chosen, not for
                # every topic in advance).
                conversation.quiz_state = {
                    "language": target_language,
                    "topic": None,  # not yet chosen
                    "topics": topics,
                    "questions": [],
                    "current_index": 0,
                    "score": 0,
                    "completed": False,
                    "history": [],
                }
                await db.commit()

                # Emit the structured topic picker event.
                yield f"event: quiz_topics\ndata: {json.dumps({'language': target_language, 'topics': topics})}\n\n"

                # Also emit a friendly token so the chat bubble shows text.
                intro_text = (
                    "Sure, which topic should I ask from?"
                    if target_language == "ENGLISH"
                    else "ഏത് വിഷയത്തെക്കുറിച്ച് ചോദിക്കണം?"
                )
                yield f"event: token\ndata: {json.dumps({'text': intro_text})}\n\n"

                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=intro_text,
                    sources=[],
                )
                db.add(assistant_msg)
                await db.commit()
                yield "event: done\ndata: {}\n\n"
                return

            # ─────────────────────────────────────────────
            # PHASE 2: user picked a topic → generate questions
            # ─────────────────────────────────────────────
            chosen_topic_raw = user_message.strip()
            # Normalise: case-insensitive match against the suggested topics
            topics = existing_quiz_state.get("topics", [])
            chosen_topic = None
            all_topics_match = chosen_topic_raw.lower() in {
                "all topics", "all topics (mixed)", "all", "everything"
            }
            if all_topics_match:
                chosen_topic = "All Topics (Mixed)"
            else:
                for t in topics:
                    if t.strip().lower() == chosen_topic_raw.lower():
                        chosen_topic = t
                        break
                if chosen_topic is None:
                    # User free-typed a topic. Treat it as the chosen one.
                    chosen_topic = chosen_topic_raw

            target_language = existing_quiz_state.get("language", target_language)
            yield f"event: status\ndata: {json.dumps({'message': 'Generating quiz questions...'})}\n\n"

            # Re-retrieve chunks using the chosen topic as the query so the
            # generated questions are actually grounded in topic-relevant
            # material.
            retrieval_queries = [chosen_topic]
            if chosen_topic == "All Topics (Mixed)":
                # Searching for the literal label "All Topics (Mixed)" mostly
                # returns the textbook preface. Search each suggested topic
                # plus broad chapter-level terms and merge the results.
                retrieval_queries = [
                    *topics,
                    "main chapters events people concepts dates causes effects",
                    "historical developments social political economic cultural topics",
                ]

            chunks = await self._retrieve_quiz_chunks(
                course_id=course_id,
                user_id=user_id,
                queries=retrieval_queries,
            )

            if not chunks:
                fallback = (
                    "I do not have enough information to create a quiz on this topic based on the course materials."
                    if target_language == "ENGLISH"
                    else "കോഴ്‌സ് വിവരങ്ങളുടെ അടിസ്ഥാനത്തിൽ ഈ വിഷയത്തിൽ ക്വിസ് തയ്യാറാക്കാൻ ആവശ്യമായ വിവരങ്ങൾ ലഭ്യമല്ല."
                )
                yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=fallback,
                    sources=[],
                )
                db.add(assistant_msg)
                # Keep topics so the student can pick again.
                conversation.quiz_state = {
                    **existing_quiz_state,
                    "topic": None,
                }
                await db.commit()
                yield f"event: quiz_topics\ndata: {json.dumps({'language': target_language, 'topics': topics})}\n\n"
                yield "event: done\ndata: {}\n\n"
                return

            questions = await quiz_service.generate_questions(
                chunks, chosen_topic, target_language
            )
            if not questions:
                fallback = (
                    "I couldn't generate quiz questions for that topic. Please pick another topic."
                    if target_language == "ENGLISH"
                    else "ആ വിഷയത്തിൽ ക്വിസ് ചോദ്യങ്ങൾ സൃഷ്ടിക്കാൻ കഴിഞ്ഞില്ല. ദയവായി മറ്റൊരു വിഷയം തിരഞ്ഞെടുക്കുക."
                )
                yield f"event: token\ndata: {json.dumps({'text': fallback})}\n\n"
                assistant_msg = Message(
                    conversation_id=conversation.id,
                    role=MessageRole.ASSISTANT,
                    content=fallback,
                    sources=[],
                )
                db.add(assistant_msg)
                conversation.quiz_state = {**existing_quiz_state, "topic": None}
                await db.commit()
                yield f"event: quiz_topics\ndata: {json.dumps({'language': target_language, 'topics': topics})}\n\n"
                yield "event: done\ndata: {}\n\n"
                return

            # Persist the full quiz state. The LLM call is over; the rest
            # is pure Python.
            conversation.quiz_state = {
                "language": target_language,
                "topic": chosen_topic,
                "topics": topics,
                "questions": questions,
                "current_index": 0,
                "score": 0,
                "completed": False,
                "history": [],
            }
            await db.commit()

            # Emit the first question.
            first_q = questions[0]
            yield f"event: quiz_question\ndata: {json.dumps(self._serialize_question(first_q, index=0, total=len(questions)))}\n\n"

            # The chat bubble only carries a short intro line — the
            # structured QuizCard below the bubble shows the actual
            # question. Rendering the question stem in both the markdown
            # text and the card caused the duplication the user reported.
            intro_line = (
                f"Quiz on **{chosen_topic}** — {len(questions)} questions. Here we go!"
                if target_language == "ENGLISH"
                else f"**{chosen_topic}** വിഷയത്തിൽ ക്വിസ് — {len(questions)} ചോദ്യങ്ങൾ. തുടങ്ങാം!"
            )
            yield f"event: token\ndata: {json.dumps({'text': intro_line})}\n\n"
            assistant_msg = Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=intro_line,
                sources=[],
            )
            db.add(assistant_msg)
            await db.commit()
            yield "event: done\ndata: {}\n\n"
            return

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"QUIZ FLOW ERROR: {tb}")
            err = f"Quiz error: {str(e)}"
            yield f"event: token\ndata: {json.dumps({'text': err})}\n\n"
            yield f"event: error\ndata: {json.dumps({'error': err})}\n\n"

    async def _retrieve_quiz_chunks(
        self,
        *,
        course_id: UUID,
        user_id: Optional[UUID],
        queries: list[str],
    ) -> list:
        """Retrieve a broad, deduplicated quiz context across all queries."""
        unique_chunks = {}
        for query in queries:
            try:
                raw = await self.retrieval.retrieve_relevant_chunks(
                    user_id=str(user_id) if user_id else None,
                    course_id=str(course_id),
                    query=query,
                    top_k=45,
                )
            except Exception as e:
                print(f"QUIZ retrieval error for '{query}': {e}")
                continue

            for chunk in raw:
                if chunk.get("score", 0.0) < RELEVANCE_THRESHOLD:
                    continue
                key = (
                    chunk.get("document_id"),
                    chunk.get("page_number"),
                    chunk.get("chunk_index"),
                    chunk.get("text", "")[:120],
                )
                existing = unique_chunks.get(key)
                if existing is None or chunk.get("score", 0.0) > existing.get("score", 0.0):
                    unique_chunks[key] = chunk

        # Keep the best 30 distinct chunks. This is substantially broader than
        # the normal chat context while avoiding unbounded prompt growth.
        return sorted(
            unique_chunks.values(),
            key=lambda chunk: chunk.get("score", 0.0),
            reverse=True,
        )[:30]

    def _serialize_question(
        self, question: dict, *, index: int, total: int
    ) -> dict:
        """Shape a question dict for the frontend `quiz_question` SSE event."""
        return {
            "index": index,
            "total": total,
            "id": question.get("id"),
            "topic": question.get("topic"),
            "stem": question.get("stem"),
            "options": question.get("options", []),
        }

    def _render_question_text(
        self,
        question: dict,
        *,
        index: int,
        total: int,
        language: str,
    ) -> str:
        """Render a question as plain text for the assistant chat bubble."""
        lines = [f"**Question {index + 1} of {total}:**", "", question.get("stem", "")]
        for opt in question.get("options", []):
            lines.append(f"- **{opt.get('key')}**. {opt.get('text')}")
        return "\n".join(lines)