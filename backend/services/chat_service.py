"""
Chat Service.

Orchestrates RAG retrieval, prompt assembly, and SSE streaming.
Includes relevance filtering, detailed chunk logging, and token usage tracking.
"""

import json
import time
from uuid import UUID
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.conversation import Conversation, Message, MessageRole
from services.retrieval_service import RetrievalService
from llm.prompts import build_rag_prompt
from providers.factory import llm_client


from core.database import async_session_factory

# Minimum cosine similarity score to consider a chunk relevant
RELEVANCE_THRESHOLD = 0.3


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
                await db.flush()

                # Send conversation ID to client immediately
                yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conversation_id)})}\n\n"

                # 3. Retrieve relevant chunks
                t_retrieval_start = time.time()
                raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                    user_id=str(user_id) if user_id else None,
                    course_id=str(course_id),
                    query=message_text,
                    top_k=10  # Fetch more, then filter by relevance
                )
                t_retrieval_end = time.time()
                
                # STRICT FALLBACK VERIFICATION: Filter out any chunks that don't match the course_id
                # This guarantees isolation even if the vector DB index has an issue.
                course_filtered_chunks = []
                for c in raw_chunks:
                    chunk_course_id = c.get('course_id')
                    if chunk_course_id and str(chunk_course_id) != str(course_id).lower().strip():
                        print(f"⚠️ [WARNING] Vector DB returned chunk from wrong course! Expected {course_id}, got {chunk_course_id}. Ignoring.", flush=True)
                        continue
                    course_filtered_chunks.append(c)
                
                # RELEVANCE FILTERING: Only keep chunks above the similarity threshold
                relevant_chunks = []
                discarded_chunks = []
                for c in course_filtered_chunks:
                    score = c.get('score', 0.0)
                    if score >= RELEVANCE_THRESHOLD:
                        relevant_chunks.append(c)
                    else:
                        discarded_chunks.append(c)
                
                # Use relevant chunks (or fall back to top chunks if all are below threshold)
                if relevant_chunks:
                    chunks = relevant_chunks[:7]  # Cap at 7 best chunks
                elif course_filtered_chunks:
                    # All chunks scored below threshold — use top 3 as fallback but warn
                    chunks = course_filtered_chunks[:3]
                    print(f"⚠️ [RELEVANCE] All {len(course_filtered_chunks)} chunks scored below threshold {RELEVANCE_THRESHOLD}. Using top 3 as fallback.", flush=True)
                else:
                    chunks = []
                
                # User requested to remove citations below the chat
                sources = []
                
                # ═══════════════════════════════════════════════════════════
                # DETAILED LOGGING FOR RENDER CLI / BACKEND LOGS
                # ═══════════════════════════════════════════════════════════
                print("\n" + "═" * 80, flush=True)
                print(f"🔍 [RAG RETRIEVAL] Query: '{message_text}'", flush=True)
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
                    score = c.get('score', 0.0)
                    print(f"\n  📄 CHUNK #{idx} | Score: {score:.4f} | File: {c.get('filename')} | Page: {c.get('page_number')}", flush=True)
                    print(f"  {'─' * 60}", flush=True)
                    chunk_text = str(c.get('text', ''))
                    # Log full chunk text
                    for line in chunk_text.split('\n'):
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

                # 4. Get conversation history
                result = await db.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at.asc())
                )
                all_messages = result.scalars().all()
                history = [
                    {"role": msg.role.value, "content": msg.content}
                    for msg in all_messages[:-1]  # Exclude the current message we just added
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
