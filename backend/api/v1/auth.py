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
    GenerateTicketRequest,
    GenerateTicketResponse,
    ExchangeTicketRequest,
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


@router.post("/generate-ticket", response_model=GenerateTicketResponse, status_code=status.HTTP_201_CREATED)
async def generate_ticket(
    request: GenerateTicketRequest, 
    x_api_key: str = Depends(lambda req: req.headers.get("X-API-Key")),
    db: AsyncSession = Depends(get_db)
):
    """Generate a short-lived SSO ticket for mobile-to-web handoff."""
    from fastapi import Request
    
    if not x_api_key or x_api_key != settings.SSO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
        
    ticket_str = f"tkt_{secrets.token_hex(16)}"
    expires_at = datetime.utcnow() + timedelta(seconds=settings.TICKET_EXPIRATION_SECONDS)
    
    ticket = SSOTicket(
        ticket=ticket_str,
        student_name=request.student_name,
        student_external_id=request.student_external_id,
        org_id=request.org_id,
        enrolled_course_ids=request.enrolled_course_ids,
        expires_at=expires_at
    )
    
    db.add(ticket)
    await db.commit()
    
    return GenerateTicketResponse(
        ticket=ticket_str,
        expires_in_seconds=settings.TICKET_EXPIRATION_SECONDS
    )


@router.post("/exchange-ticket", response_model=ExchangeTicketResponse)
async def exchange_ticket(request: ExchangeTicketRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a short-lived SSO ticket for a long-lived JWT."""
    result = await db.execute(select(SSOTicket).where(SSOTicket.ticket == request.ticket))
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ticket",
        )
        
    if ticket.is_used:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ticket has already been used",
        )
        
    if ticket.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ticket has expired",
        )
        
    # Burn the ticket
    ticket.is_used = True
    await db.commit()
    
    # Generate the long-lived JWT
    access_token = create_student_token(
        student_name=ticket.student_name,
        student_external_id=ticket.student_external_id,
        org_id=ticket.org_id,
        enrolled_course_ids=ticket.enrolled_course_ids
    )
    
    return ExchangeTicketResponse(
        access_token=access_token,
        student_name=ticket.student_name,
        org_id=ticket.org_id
    )
