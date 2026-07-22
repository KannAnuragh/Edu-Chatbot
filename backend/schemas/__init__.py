"""
Pydantic Schemas — Package init.
"""

from schemas.common import HealthResponse, ErrorResponse
from schemas.auth import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from schemas.course import CourseCreateRequest, CourseUpdateRequest, CourseResponse, CourseListResponse
from schemas.document import DocumentResponse, DocumentListResponse, DocumentStatusResponse
from schemas.chat import ChatRequest, SourceReference, MessageResponse, ConversationResponse, ConversationListResponse

__all__ = [
    "HealthResponse",
    "ErrorResponse",
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenResponse",
    "UserResponse",
    "CourseCreateRequest",
    "CourseUpdateRequest",
    "CourseResponse",
    "CourseListResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "DocumentStatusResponse",
    "ChatRequest",
    "SourceReference",
    "MessageResponse",
    "ConversationResponse",
    "ConversationListResponse",
]
