"""
API v1 — Courses Routes.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload

from core.database import get_db
from api.deps import get_current_user, get_current_admin
from models.user import User, UserRole
from models.course import Course
from models.enrollment import Enrollment
from models.document import Document
from schemas.course import (
    CourseCreateRequest,
    CourseUpdateRequest,
    CourseResponse,
    CourseListResponse,
)

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    request: CourseCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Create a new course (Admin only)."""
    course = Course(
        title=request.title,
        description=request.description,
        badge_color=request.badge_color or "emerald",
        created_by=admin_user.id,
    )
    db.add(course)
    await db.flush()

    return await _get_course_response(db, course.id)


@router.get("", response_model=CourseListResponse)
async def list_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """List courses. Admins see their created courses, students see all courses."""
    query = select(Course)

    if current_user.role == UserRole.ADMIN:
        query = query.where(Course.created_by == current_user.id)

    query = query.order_by(Course.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    courses = result.scalars().all()

    total_query = select(func.count()).select_from(Course)
    if current_user.role == UserRole.ADMIN:
        total_query = total_query.where(Course.created_by == current_user.id)
    total_result = await db.execute(total_query)
    total = total_result.scalar_one()

    responses = [await _get_course_response(db, c.id) for c in courses]

    return CourseListResponse(courses=responses, total=total)


@router.get("/enrolled", response_model=CourseListResponse)
async def list_enrolled_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List courses the current user is enrolled in."""
    query = (
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == current_user.id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    result = await db.execute(query)
    courses = result.scalars().all()

    responses = [await _get_course_response(db, c.id) for c in courses]
    
    return CourseListResponse(courses=responses, total=len(responses))


@router.post("/{course_id}/enroll", status_code=status.HTTP_200_OK)
async def enroll_course(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enroll the current user in a course."""
    # Check if course exists
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check existing enrollment
    result = await db.execute(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.user_id == current_user.id
        )
    )
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
        db.add(enrollment)
        await db.commit()

    return {"detail": "Successfully enrolled"}


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get course details."""
    response = await _get_course_response(db, course_id)
    if not response:
        raise HTTPException(status_code=404, detail="Course not found")
    return response


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: UUID,
    request: CourseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Update a course (Admin only)."""
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.created_by == admin_user.id)
    )
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found or unauthorized")

    if request.title is not None:
        course.title = request.title
    if request.description is not None:
        course.description = request.description
    if request.badge_color is not None:
        course.badge_color = request.badge_color

    await db.flush()
    return await _get_course_response(db, course_id)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Delete a course and all associated data (Admin only)."""
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.created_by == admin_user.id)
    )
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found or unauthorized")

    # In a full implementation, we should also delete vectors from Qdrant
    # and files from the filesystem before deleting the database records.
    # The DB cascade will handle deleting Document, Enrollment, and Conversation rows.
    await db.delete(course)
    await db.commit()


async def _get_course_response(db: AsyncSession, course_id: UUID) -> CourseResponse | None:
    """Helper to get a course with document count."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    
    if not course:
        return None
        
    doc_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.course_id == course_id)
    )
    doc_count = doc_result.scalar_one()
    
    return CourseResponse(
        id=course.id,
        title=course.title,
        description=course.description,
        badge_color=course.badge_color,
        created_at=course.created_at,
        updated_at=course.updated_at,
        document_count=doc_count
    )
