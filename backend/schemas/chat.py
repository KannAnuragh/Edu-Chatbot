"""
Pydantic Schemas — Chat & Conversations.
"""

from datetime import datetime
from typing import List, Optional, Any, Dict
from uuid import UUID
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str
    conversation_id: Optional[UUID] = None


class SourceReference(BaseModel):
    """Source reference for a chat message."""
    document_id: str
    filename: str
    page_number: int
    chunk_text: str


class MessageResponse(BaseModel):
    """Message response."""
    id: UUID
    role: str
    content: str
    sources: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    """Conversation response with messages."""
    id: UUID
    title: str
    course_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


class ConversationSummaryResponse(BaseModel):
    """Conversation response without messages (for list view)."""
    id: UUID
    title: str
    course_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """List of conversations response."""
    conversations: List[ConversationSummaryResponse]
    total: int
