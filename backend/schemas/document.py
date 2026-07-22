"""
Pydantic Schemas — Document.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Document response."""
    id: UUID
    filename: str
    file_path: Optional[str] = None
    file_size: int
    page_count: Optional[int] = 0
    language: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """List of documents response."""
    documents: List[DocumentResponse]
    total: int


class DocumentStatusResponse(BaseModel):
    """Document processing status response."""
    id: UUID
    status: str
    error_message: Optional[str]
