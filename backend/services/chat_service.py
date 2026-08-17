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
from llm.prompts import build_rag_prompt
from providers.factory import llm_client
from ingestion.pipeline import fix_malayalam_pdf_font_artifacts

from core.database import async_session_factory

# Minimum cosine similarity score to consider a chunk relevant
RELEVANCE_THRESHOLD = 0.30

# Pre-compiled regex patterns for chunk sanitization (avoid recompiling per-call)
_RE_LONG_NUMBERS = re.compile(r'[0-9]{15,}')
_RE_SCERT_HEADER = re.compile(r'സാമൂഹ്യശാസ്[്രത]*ം.*?സംസ്കാരവും ദശീേയതയും')
_RE_MULTI_SPACES = re.compile(r'\s+')

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
                    if not result.scalar_one_or_none():
                        yield f"event: error\ndata: {json.dumps({'error': 'Conversation not found'})}\n\n"
                        return

                # 2. Save user message
                user_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content=message_text,
                )
                db.add(user_msg)
                await db.commit()

                # Send conversation ID to client immediately
                yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation_id)})}\n\n"
                
                # --- FAST PATH FOR SUGGESTION COMMANDS ---
                message_text_clean = message_text.strip()
                fast_response = None
                if message_text_clean == "Explain a concept":
                    fast_response = "Sure, which concept would you like me to explain?"
                elif message_text_clean == "Summarize a chapter":
                    fast_response = "Sure, which chapter would you like me to summarize?"
                elif message_text_clean == "Help me study":
                    fast_response = "Sure, should I summarize or create questions based on the topic you want to study?"

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

                # 2.5. Load history + conditionally optimize search query
                yield f"event: status\ndata: {json.dumps({'message': 'Searching documents...'})}\n\n"
                
                # Load history messages for query optimization and building prompt
                history_result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                )
                all_messages = history_result.scalars().all()
                history_messages = all_messages[:-1] if len(all_messages) > 1 else []

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
                    print(f"⚡ [QUERY OPTIMIZATION] Skipped (no history or self-contained query) | Using raw query: '{message_text}' | {t_opt_end - t_opt_start:.4f}s", flush=True)

                # 3. Retrieve relevant chunks using the (possibly optimized) query
                t_retrieval_start = time.time()
                raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                    user_id=str(user_id) if user_id else None,
                    course_id=str(course_id),
                    query=optimized_query,
                    top_k=15  # Fetch more, then filter by relevance
                )
                t_retrieval_end = time.time()
                
                print(f"🐛 [CHAT DEBUG] Raw chunks retrieved from Qdrant: {len(raw_chunks)}", flush=True)
                
                course_filtered_chunks = raw_chunks
                
                print(f"🐛 [CHAT DEBUG] Chunks remaining after course filter: {len(course_filtered_chunks)}", flush=True)
                
                # RELEVANCE FILTERING: Only keep chunks above the similarity threshold
                relevant_chunks = []
                discarded_chunks = []
                for c in course_filtered_chunks:
                    score = c.get('score', 0.0)
                    if score >= RELEVANCE_THRESHOLD:
                        relevant_chunks.append(c)
                    else:
                        discarded_chunks.append(c)
                        
                print(f"🐛 [CHAT DEBUG] Chunks above threshold ({RELEVANCE_THRESHOLD}): {len(relevant_chunks)}", flush=True)
                
                # Only use chunks that exceed the relevance threshold to prevent hallucination from unrelated material
                if relevant_chunks:
                    chunks = relevant_chunks[:5]  # Cap at 5 best chunks for richer context
                else:
                    chunks = []
                    print(f"⚠️ [RELEVANCE] All retrieved chunks scored below threshold {RELEVANCE_THRESHOLD}. Treating context as empty.", flush=True)
                
                # User requested to remove citations below the chat
                sources = []
                
                # ═══════════════════════════════════════════════════════════
                # DETAILED LOGGING FOR RENDER CLI / BACKEND LOGS
                # ═══════════════════════════════════════════════════════════
                print("\n" + "═" * 80, flush=True)
                print(f"🔍 [RAG RETRIEVAL] Optimized Query: '{optimized_query}'", flush=True)
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
                    print(f"\n  📄 CHUNK #{idx} | Score: {score:.4f} | File: {c.get('filename')} | Page: {c.get('page_number')}", flush=True)
                    print(f"  {'─' * 60}", flush=True)
                    # Log full chunk text
                    for line in clean_text.split('\n'):
                        print(f"    {line}", flush=True)
                    print(f"  {'─' * 60}", flush=True)
                
                if discarded_chunks:
                    print(f"\n  🗑️ DISCARDED CHUNKS (below {RELEVANCE_THRESHOLD} threshold):", flush=True)
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
                prompt = build_rag_prompt(
                    context_chunks=chunks,
                    conversation_history=history,
                    question=message_text
                )
                
                # Log the assembled prompt
                print("═" * 80, flush=True)
                print("📝 [ASSEMBLED PROMPT SENT TO LLM]", flush=True)
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
                print("📊 [PIPELINE SUMMARY]", flush=True)
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
