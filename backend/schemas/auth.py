"""
Pydantic Schemas — Authentication.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from typing import List


class UserRegisterRequest(BaseModel):
    """Registration request payload."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2)


class UserLoginRequest(BaseModel):
    """Login request payload."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT Token response."""
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User profile response."""
    id: UUID
    name: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateTicketRequest(BaseModel):
    """Payload to generate a new SSO ticket from mobile app."""
    student_name: str
    student_external_id: str
    org_id: str
    enrolled_course_ids: List[str]


class GenerateTicketResponse(BaseModel):
    """Response containing the generated ticket."""
    ticket: str
    expires_in_seconds: int


class ExchangeTicketRequest(BaseModel):
    """Payload to exchange a ticket for a JWT from the frontend web view."""
    ticket: str


class ExchangeTicketResponse(BaseModel):
    """Response containing the long-lived student JWT."""
    access_token: str
    token_type: str = "bearer"
    student_name: str
    org_id: str
