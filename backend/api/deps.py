"""
API Dependencies — Shared dependencies for FastAPI routes.

Includes get_current_user for JWT authentication.
"""

from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from auth.jwt import decode_access_token
from models.user import User


security = HTTPBearer()


from typing import Optional
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request

security = HTTPBearer(auto_error=False)

async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Check for token manually and return user if found, else None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
        
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        return None
        
    user_id = payload.get("sub")
    if not user_id:
        return None
        
    role = payload.get("role")
    if role == "student":
        # Students aren't in the DB; construct an ephemeral User object
        # Generate a deterministic UUID based on their external ID so their chats are grouped correctly
        import uuid
        from models.user import UserRole
        from datetime import datetime, timezone
        student_uuid = uuid.uuid5(uuid.NAMESPACE_OID, user_id)
        student_user = User(
            id=student_uuid,
            name=payload.get("name", "Student"),
            email=f"{user_id}@student.sso",
            role=UserRole.STUDENT,
            created_at=datetime.now(timezone.utc)
        )
        # Attach the enrolled courses array directly to the object for quick RBAC checks
        student_user.enrolled_course_ids = payload.get("enrolled_courses", [])
        return student_user
        
    try:
        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        return result.scalar_one_or_none()
    except ValueError:
        return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT token, return the authenticated user (requires auth)."""
    user = await get_optional_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, missing or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

    return user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verify the current user is an admin."""
    from models.user import UserRole
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges",
        )
    return current_user
