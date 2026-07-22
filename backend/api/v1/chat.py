"""
API v1 — Chat Routes.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.deps import get_current_user
from models.user import User
from models.conversation import Conversation
from schemas.chat import (
    ChatRequest,
    ConversationResponse,
    ConversationListResponse,
)

router = APIRouter(prefix="/courses/{course_id}", tags=["Chat"])


@router.post("/chat", response_class=StreamingResponse)
async def chat_with_course(
    course_id: UUID,
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream chat response using Gemini and RAG."""
    from services.chat_service import ChatService
    
    chat_service = ChatService()
    
    return StreamingResponse(
        chat_service.process_chat(
            user_id=current_user.id,
            course_id=course_id,
            message_text=request.message,
            conversation_id=request.conversation_id,
        ),
        media_type="text/event-stream"
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's conversations for a course."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.course_id == course_id,
            Conversation.user_id == current_user.id
        )
        .order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()
    
    return ConversationListResponse(
        conversations=conversations,
        total=len(conversations)
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    course_id: UUID,
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific conversation with all its messages."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(
            Conversation.id == conversation_id,
            Conversation.course_id == course_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    course_id: UUID,
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a conversation."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.id == conversation_id,
            Conversation.course_id == course_id,
            Conversation.user_id == current_user.id
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    await db.delete(conversation)
    await db.commit()


@router.get("/debug/chunks")
async def debug_chunks(
    course_id: UUID,
    query: str,
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint to see what chunks are retrieved for a query."""
    from services.retrieval_service import RetrievalService
    
    retrieval = RetrievalService()
    try:
        raw_chunks = await retrieval.retrieve_relevant_chunks(
            user_id=str(current_user.id),
            course_id=str(course_id),
            query=query,
            top_k=5
        )
        return {
            "query": query,
            "course_id": course_id,
            "chunk_count": len(raw_chunks),
            "chunks": raw_chunks
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
