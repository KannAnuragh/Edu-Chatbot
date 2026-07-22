"""
API v1 — Course Stats Route.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from core.database import get_db
from api.deps import get_current_user
from models.user import User
from models.course import Course
from models.document import Document
from models.enrollment import Enrollment
from models.conversation import Conversation

router = APIRouter(prefix="/stats", tags=["Stats"])

@router.get("/global")
async def get_global_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get global statistics for the admin dashboard."""
    # Only admins or we can restrict, but for now we just return the counts
    
    # Total PDFs added
    doc_count_result = await db.execute(select(func.count()).select_from(Document))
    total_pdfs = doc_count_result.scalar_one()

    # Total students across all courses
    # Wait, "total students in all course". This could mean distinct students enrolled, or total enrollments. Let's do distinct users with role student.
    student_count_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == "student")
    )
    total_students = student_count_result.scalar_one()

    # Students using right now: mock or approximate using recent conversations. Let's return a static or derived number for now, or total active conversations today.
    # We will just return 0 for now as we don't have a real-time socket tracker.
    
    return {
        "total_pdfs": total_pdfs,
        "total_students": total_students,
        "active_students": 0,
    }


@router.get("/course/{course_id}")
async def get_course_stats(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get statistics for a specific course."""
    # Verify course exists
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Document count
    doc_count_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.course_id == course_id)
    )
    document_count = doc_count_result.scalar_one()

    # Total pages across all documents
    total_pages_result = await db.execute(
        select(func.coalesce(func.sum(Document.page_count), 0))
        .where(Document.course_id == course_id)
    )
    total_pages = total_pages_result.scalar_one()

    # Enrolled students
    enrolled_result = await db.execute(
        select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course_id)
    )
    enrolled_students = enrolled_result.scalar_one()

    # Conversation count
    convo_result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.course_id == course_id)
    )
    conversation_count = convo_result.scalar_one()

    return {
        "document_count": document_count,
        "total_pages": int(total_pages),
        "enrolled_students": enrolled_students,
        "conversation_count": conversation_count,
    }
