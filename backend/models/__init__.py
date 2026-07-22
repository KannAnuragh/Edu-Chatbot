"""
SQLAlchemy Models — Package init.

Imports all models so Alembic can discover them.
"""

from models.user import User, UserRole
from models.course import Course
from models.document import Document, DocumentStatus
from models.conversation import Conversation, Message, MessageRole
from models.enrollment import Enrollment

__all__ = [
    "User",
    "UserRole",
    "Course",
    "Document",
    "DocumentStatus",
    "Conversation",
    "Message",
    "MessageRole",
    "Enrollment",
]
