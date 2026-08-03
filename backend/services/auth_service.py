import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.course import Course
from core.config import settings

# Organization Admin API Keys
ORG_API_KEYS = {
    "org_key_trogon_admin_9901": {"org_id": "org_trogon", "name": "Trogon Education"},
}

# 5 Distinct Student Personas mapped to actual courses ("Course 2" and "Social Science")
# The "id" inside the courses list will be dynamically replaced with real DB UUIDs during startup
STUDENT_PROFILES = {
    "usr_1001": {
        "name": "Arjun K.",
        "org_id": "Trogon",
        "allowed_key": "org_key_trogon_admin_9901",
        "courses": [
            {"id": "course-2", "title": "Course 2", "description": "A new learning course", "docs": "1 docs", "date": "01/08/2026", "progress": 85},
            {"id": "social-science", "title": "Social Science", "description": "A new learning course", "docs": "4 docs", "date": "01/08/2026", "progress": 60}
        ],
        "history": [
            {"lesson_id": "c2-01", "title": "Course 2 - Module 1", "status": "Completed", "score": 92},
            {"lesson_id": "ss-01", "title": "Social Science - Chapter 1", "status": "In Progress", "score": None}
        ]
    },
    "usr_1002": {
        "name": "Meera S.",
        "org_id": "Trogon",
        "allowed_key": "org_key_trogon_admin_9901",
        "courses": [
            {"id": "social-science", "title": "Social Science", "description": "A new learning course", "docs": "4 docs", "date": "01/08/2026", "progress": 40}
        ],
        "history": [
            {"lesson_id": "ss-01", "title": "Social Science - Chapter 1", "status": "In Progress", "score": 70}
        ]
    },
    "usr_1003": {
        "name": "Rahul V.",
        "org_id": "Trogon",
        "allowed_key": "org_key_trogon_admin_9901",
        "courses": [
            {"id": "course-2", "title": "Course 2", "description": "A new learning course", "docs": "1 docs", "date": "01/08/2026", "progress": 100}
        ],
        "history": [
            {"lesson_id": "c2-01", "title": "Course 2 - Final Assessment", "status": "Completed", "score": 98}
        ]
    },
    "usr_1004": {
        "name": "Ananya P.",
        "org_id": "Trogon",
        "allowed_key": "org_key_trogon_admin_9901",
        "courses": [
            {"id": "course-2", "title": "Course 2", "description": "A new learning course", "docs": "1 docs", "date": "01/08/2026", "progress": 30},
            {"id": "social-science", "title": "Social Science", "description": "A new learning course", "docs": "4 docs", "date": "01/08/2026", "progress": 20}
        ],
        "history": [
            {"lesson_id": "c2-01", "title": "Course 2 - Introduction", "status": "In Progress", "score": None}
        ]
    },
    "usr_1005": {
        "name": "Karthik M.",
        "org_id": "Trogon",
        "allowed_key": "org_key_trogon_admin_9901",
        "courses": [
            {"id": "social-science", "title": "Social Science", "description": "A new learning course", "docs": "4 docs", "date": "01/08/2026", "progress": 95}
        ],
        "history": [
            {"lesson_id": "ss-01", "title": "Social Science - Final Exam", "status": "Completed", "score": 95}
        ]
    }
}


async def init_mock_courses(db: AsyncSession):
    """
    Ensure the mock courses exist in the DB, get their UUIDs,
    and dynamically patch STUDENT_PROFILES to use valid UUIDs.
    """
    from models.user import User
    
    # Need an admin to be the creator
    admin_query = await db.execute(select(User).where(User.email == settings.DEFAULT_ADMIN_EMAIL))
    admin = admin_query.scalar_one_or_none()
    
    if not admin:
        print("Warning: Admin user not found, skipping mock course init.")
        return

    query = await db.execute(select(Course).order_by(Course.created_at.asc()))
    existing_courses = query.scalars().all()
    
    id_mapping = {}

    # Map first course to "course-2"
    if len(existing_courses) > 0:
        id_mapping["course-2"] = str(existing_courses[0].id)
    else:
        c1 = Course(title="Course 2", description="A new learning course", created_by=admin.id)
        db.add(c1)
        await db.flush()
        id_mapping["course-2"] = str(c1.id)
        
    # Map second course to "social-science"
    if len(existing_courses) > 1:
        id_mapping["social-science"] = str(existing_courses[1].id)
    else:
        c2 = Course(title="Social Science", description="A new learning course", created_by=admin.id)
        db.add(c2)
        await db.flush()
        id_mapping["social-science"] = str(c2.id)
        
    await db.commit()

    # Patch the STUDENT_PROFILES with actual UUIDs
    for uid, profile in STUDENT_PROFILES.items():
        for course_dict in profile.get("courses", []):
            # Prefer mock_id if it exists (for hot reloads), otherwise fallback to id
            mock_id = course_dict.get("mock_id", course_dict["id"])
            if mock_id in id_mapping:
                course_dict["id"] = id_mapping[mock_id]
                course_dict["mock_id"] = mock_id  # keep old ID for reference
