"""
API v1 — Authentication Routes.

POST /api/v1/auth/register — Register a new user
POST /api/v1/auth/login — Login and get JWT token
GET  /api/v1/auth/me — Get current user profile
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.database import get_db
from api.deps import get_current_user
from auth.hashing import hash_password, verify_password
from auth.jwt import create_access_token
from models.user import User, UserRole
from schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    DirectLoginRequest,
    ExchangeTicketResponse,
)
from core.config import settings
from auth.jwt import create_student_token
from models.sso_ticket import SSOTicket
import uuid
import secrets
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Registration is disabled. Only the admin can log in.",
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(user.id, user.email)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the current authenticated user's profile."""
    return current_user


@router.post("/direct-login", response_model=ExchangeTicketResponse)
async def direct_login(request: DirectLoginRequest):
    """Direct login via API key and student ID."""
    from services.auth_service import ORG_API_KEYS, STUDENT_PROFILES
    
    # Validate API key
    org = ORG_API_KEYS.get(request.api_key)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
        
    # Validate student persona
    student = STUDENT_PROFILES.get(request.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student profile not found",
        )
        
    # Check if student belongs to the organization that owns the key
    if student.get("allowed_key") != request.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this student profile",
        )
        
    # Extract enrolled courses
    enrolled_course_ids = [c["id"] for c in student.get("courses", [])]
    
    # Generate the long-lived JWT
    access_token = create_student_token(
        student_name=student["name"],
        student_external_id=request.student_id,
        org_id=student["org_id"],
        enrolled_course_ids=enrolled_course_ids
    )
    
    return ExchangeTicketResponse(
        access_token=access_token,
        student_name=student["name"],
        org_id=student["org_id"]
    )
