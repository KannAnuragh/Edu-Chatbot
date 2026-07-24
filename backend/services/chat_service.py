"""
Chat Service.

Orchestrates RAG retrieval, prompt assembly, and SSE streaming.
"""

import json
from uuid import UUID
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.conversation import Conversation, Message, MessageRole
from services.retrieval_service import RetrievalService
from llm.prompts import build_rag_prompt
from providers.factory import llm_client


from core.database import async_session_factory

class ChatService:
    """Service for handling chat conversations."""
    
    def __init__(self):
        self.retrieval = RetrievalService()
        
    async def process_chat(
        self,
        user_id: UUID,
        course_id: UUID,
        message_text: str,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Full RAG pipeline and SSE streaming response.
        """
        try:
            async with async_session_factory() as db:
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
                    # Verify conversation exists and belongs to user
                    result = await db.execute(
                        select(Conversation).where(
                            Conversation.id == conversation_id,
                            Conversation.user_id == user_id,
                            Conversation.course_id == course_id
                        )
                    )
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
                raw_chunks = await self.retrieval.retrieve_relevant_chunks(
                    user_id=str(user_id),
                    course_id=str(course_id),
                    query=message_text,
                    top_k=5
                )
                
                # STRICT FALLBACK VERIFICATION: Filter out any chunks that don't match the course_id
                # This guarantees isolation even if the vector DB index has an issue.
                chunks = []
                for c in raw_chunks:
                    chunk_course_id = c.get('course_id')
                    if chunk_course_id and str(chunk_course_id) != str(course_id):
                        print(f"⚠️ [WARNING] Qdrant returned chunk from wrong course! Expected {course_id}, got {chunk_course_id}. Ignoring.")
                        continue
                    chunks.append(c)
                
                sources = self.retrieval.format_sources(chunks)
                
                # Detailed terminal logging for inspection
                print("\n" + "=" * 70)
                print(f"🔍 [RAG RETRIEVAL] Found {len(chunks)} context chunks for query: '{message_text}'")
                for idx, c in enumerate(chunks, 1):
                    print(f"  📄 Chunk #{idx} | File: {c.get('filename')} | Page: {c.get('page_number')} | Score: {c.get('score', 0):.4f}")
                    print(f"     Content: {str(c.get('text', ''))[:200]}...")
                print("=" * 70 + "\n")

                # Send sources to client
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

                # 6. Stream LLM response
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

                # 7. Save assistant message
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=full_response,
                    sources=sources,
                )
                db.add(assistant_msg)
                await db.commit()

                # 8. Send completion event
                yield "event: done\ndata: {}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"FATAL STREAM ERROR: {tb}")
            error_msg = f"\n\nFatal error in stream processing: {str(e)}"
            yield f"event: token\ndata: {json.dumps({'text': error_msg})}\n\n"
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
