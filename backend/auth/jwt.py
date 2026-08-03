"""
Authentication — JWT Token Management.

Creates and validates JWT tokens for user authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from core.config import settings


def create_access_token(user_id: UUID, email: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_student_token(
    student_name: str,
    student_external_id: str,
    org_id: str,
    enrolled_course_ids: list[str],
) -> str:
    """Create a 180-day JWT for a student."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.STUDENT_JWT_EXPIRATION_DAYS)
    payload = {
        "sub": student_external_id,
        "name": student_name,
        "org_id": org_id,
        "role": "student",
        "enrolled_courses": enrolled_course_ids,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns the payload or None."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None
