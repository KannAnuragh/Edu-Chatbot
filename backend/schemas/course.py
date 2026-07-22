"""
Pydantic Schemas — Course.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CourseCreateRequest(BaseModel):
    """Course creation payload."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field("", max_length=2000)
    badge_color: Optional[str] = Field(None, max_length=50)


class CourseUpdateRequest(BaseModel):
    """Course update payload."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    badge_color: Optional[str] = Field(None, max_length=50)


class CourseResponse(BaseModel):
    """Course response."""
    id: UUID
    title: str
    description: str
    badge_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    document_count: int = 0

    class Config:
        from_attributes = True


class CourseListResponse(BaseModel):
    """List of courses response."""
    courses: List[CourseResponse]
    total: int
