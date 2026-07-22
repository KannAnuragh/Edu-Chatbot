"""
PDF Chatbot Backend — FastAPI Application Entry Point.
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import engine, Base, get_db
from api.v1.router import router as v1_router
from schemas.common import HealthResponse

# --- Create FastAPI app ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- CORS middleware ---
frontend_origins = [o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()]
origins = []
has_wildcard = False

for origin in frontend_origins:
    if origin == "*":
        has_wildcard = True
    else:
        origins.append(origin.rstrip("/"))

# Add common local development origins
for local_origin in ["http://localhost:3000", "http://localhost:3001"]:
    if local_origin not in origins:
        origins.append(local_origin)

if has_wildcard:
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# --- Include API routes ---
app.include_router(v1_router)


# --- Health check ---
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", version=settings.APP_VERSION)

@app.get("/debug/qdrant")
async def debug_qdrant(db: AsyncSession = Depends(get_db)):
    from qdrant_client import AsyncQdrantClient
    from sqlalchemy import select
    from models.document import Document
    
    # Check DB first
    docs_result = await db.execute(select(Document))
    db_docs = [{"id": str(d.id), "course_id": str(d.course_id), "status": d.status, "pages": d.page_count} for d in docs_result.scalars().all()]
    
    client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    try:
        res = await client.scroll(
            collection_name="course_documents",
            limit=5,
            with_payload=True
        )
        points = []
        for p in res[0]:
            payload = p.payload.copy() if p.payload else {}
            if "text" in payload:
                payload["text"] = payload["text"][:50] + "..."
            points.append({"id": p.id, "payload": payload})
        return {"status": "ok", "db_docs": db_docs, "qdrant_points": points}
    except Exception as e:
        return {"status": "error", "db_docs": db_docs, "error": str(e)}

# --- Validation Error Logger ---
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    import traceback
    with open("app_validation_error.log", "a") as f:
        f.write(f"Validation Error on {request.url}:\n{exc.errors()}\n")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

async def ensure_default_users():
    from sqlalchemy import select
    from core.database import async_session_factory
    from models.user import User, UserRole
    from auth.hashing import hash_password
    
    async with async_session_factory() as session:
        # Create Admin
        admin_email = "admin@gmail.com"
        admin_query = await session.execute(select(User).where(User.email == admin_email))
        admin = admin_query.scalar_one_or_none()
        
        if not admin:
            admin = User(
                name="Admin User",
                email=admin_email,
                password_hash=hash_password("asdfasdf"),
                role=UserRole.ADMIN
            )
            session.add(admin)
            print(f"Created admin user: {admin_email}")
        else:
            admin.password_hash = hash_password("asdfasdf")
            admin.role = UserRole.ADMIN
            print(f"Admin user password verified/updated on startup.")

        # Create Student
        student_email = "student@example.com"
        student_query = await session.execute(select(User).where(User.email == student_email))
        student = student_query.scalar_one_or_none()
        
        if not student:
            student = User(
                name="Student User",
                email=student_email,
                password_hash=hash_password("password123"),
                role=UserRole.STUDENT
            )
            session.add(student)
            print(f"Created student user: {student_email}")
            
        await session.commit()


# --- Startup event ---
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    # Create upload directory
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Initialize database tables
    # Import all models to register them with Base
    import models  # noqa: F401
    from sqlalchemy import text
    import asyncio
    
    max_retries = 10
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
                # Automatically add badge_color if missing
                try:
                    await conn.execute(text("ALTER TABLE courses ADD COLUMN badge_color VARCHAR(50) DEFAULT 'emerald'"))
                except Exception:
                    pass
            print("Database successfully initialized during startup.")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to connect to DB during Uvicorn startup: {e}")
                raise
            print(f"Database not ready, retrying in 3 seconds... ({attempt+1}/{max_retries})")
            await asyncio.sleep(3)

    # Ensure default users exist
    try:
        await ensure_default_users()
    except Exception as e:
        print(f"Error ensuring default users: {e}")


# --- Serve uploaded files (development only) ---
@app.on_event("startup")
async def mount_uploads():
    """Mount uploads directory for serving PDF files."""
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
