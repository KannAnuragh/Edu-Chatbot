"""
API v1 — Courses Routes.
"""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload

from core.database import get_db
from api.deps import get_current_user, get_current_admin, get_optional_user
from typing import Optional
from models.user import User, UserRole
from models.course import Course
from models.enrollment import Enrollment
from models.document import Document
from providers.factory import get_vector_db_client
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
    skip: int = 0,
    limit: int = 100,
):
    """List courses (Publicly accessible)."""
    query = select(Course).order_by(Course.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    courses = result.scalars().all()

    total_query = select(func.count()).select_from(Course)
    total_result = await db.execute(total_query)
    total = total_result.scalar_one()

    responses = [await _get_course_response(db, c.id) for c in courses]

    return CourseListResponse(courses=responses, total=total)


@router.get("/enrolled")
async def list_enrolled_courses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List courses the current user is enrolled in."""
    if current_user.role == "student":
        from fastapi.responses import JSONResponse
        from services.auth_service import STUDENT_PROFILES
        student_id = current_user.email.split("@")[0]
        profile = STUDENT_PROFILES.get(student_id)
        if profile:
            # Sync the mock courses with live DB titles
            live_courses = []
            for mock_course in profile["courses"]:
                c_id = mock_course.get("id")
                # Try to fetch actual course to get latest details
                actual = await _get_course_response(db, c_id)
                if actual:
                    mock_course["title"] = actual.title
                    mock_course["description"] = actual.description
                    mock_course["badge_color"] = actual.badge_color
                    mock_course["document_count"] = actual.document_count
                    mock_course["created_at"] = actual.created_at.isoformat()
                live_courses.append(mock_course)
                
            return JSONResponse({
                "courses": live_courses,
                "history": profile["history"],
                "total": len(live_courses)
            })
            
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
    current_user: Optional[User] = Depends(get_optional_user),
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

    # Delete vectors for all documents in this course from Vector DB (e.g. Cloudflare)
    documents_result = await db.execute(select(Document).where(Document.course_id == course_id))
    documents = documents_result.scalars().all()
    
    vector_db = get_vector_db_client()
    for doc in documents:
        try:
            await vector_db.delete_document_vectors(user_id=str(admin_user.id), document_id=str(doc.id))
        except Exception as e:
            print(f"Failed to delete vectors for document {doc.id}: {e}")

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


@router.get("/{course_id}/students")
async def get_course_students(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """List all students and whether they are enrolled in the course."""
    from services.auth_service import STUDENT_PROFILES
    
    # Verify course exists
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    student_list = []
    for s_id, profile in STUDENT_PROFILES.items():
        is_enrolled = any(str(c.get("id")) == str(course_id) for c in profile.get("courses", []))
        student_list.append({
            "id": s_id,
            "name": profile.get("name"),
            "enrolled": is_enrolled
        })
    return student_list


@router.post("/{course_id}/students/{student_id}/toggle")
async def toggle_student_enrollment(
    course_id: UUID,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Toggle a student's enrollment in a course."""
    from services.auth_service import STUDENT_PROFILES
    from datetime import datetime
    
    # Verify course exists
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    profile = STUDENT_PROFILES.get(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    courses = profile.get("courses", [])
    existing_index = next((i for i, c in enumerate(courses) if str(c.get("id")) == str(course_id)), None)

    if existing_index is not None:
        # Remove course
        courses.pop(existing_index)
        enrolled = False
    else:
        # Add course
        # Calculate doc count for this course
        doc_result = await db.execute(
            select(func.count()).select_from(Document).where(Document.course_id == course_id)
        )
        doc_count = doc_result.scalar_one()
        
        courses.append({
            "id": str(course_id),
            "title": course.title,
            "description": course.description or "",
            "docs": f"{doc_count} docs",
            "date": datetime.utcnow().strftime("%d/%m/%Y"),
            "progress": 0
        })
        enrolled = True

    profile["courses"] = courses
    return {"enrolled": enrolled}

