"""
SQLAlchemy Models — SSOTicket.

Short-lived, single-use tickets for mobile-app-to-web SSO handoff.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class SSOTicket(Base):
    __tablename__ = "sso_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    student_name: Mapped[str] = mapped_column(String(255), nullable=False)
    student_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    org_id: Mapped[str] = mapped_column(String(255), nullable=False)
    enrolled_course_ids: Mapped[list] = mapped_column(JSON, nullable=True, default=list)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
