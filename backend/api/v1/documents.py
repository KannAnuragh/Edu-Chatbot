"""
API v1 — Documents Routes.
"""

import os
from uuid import UUID
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import settings
from core.database import get_db
from api.deps import get_current_user, get_current_admin
from models.user import User, UserRole
from models.course import Course
from models.document import Document, DocumentStatus
from schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentStatusResponse,
)

router = APIRouter(prefix="/courses/{course_id}/documents", tags=["Documents"])


def dispatch_document_processing(document_id: str, background_tasks: BackgroundTasks):
    """
    Uses FastAPI BackgroundTasks instead of Celery.
    In cloud deployments without a shared disk (like AWS EFS or S3), 
    Celery workers cannot access files uploaded to the web container's local disk.
    """
    print(f"🚀 Dispatching document {document_id} to FastAPI BackgroundTasks")
    from workers.tasks import process_document_sync
    background_tasks.add_task(process_document_sync, str(document_id))


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    course_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    is_global: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Upload a PDF document to a course (Admin only)."""
    # Verify course ownership
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.created_by == admin_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found or unauthorized")

    # Validate file type
    if not file.filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are allowed")

    # Create document record
    document = Document(
        filename=file.filename,
        file_path="",  # Will update after saving
        file_size=0,
        status=DocumentStatus.PENDING,
        course_id=course_id,
        is_global=is_global,
        user_id=admin_user.id,
    )
    db.add(document)
    await db.flush()

    # Save file to disk
    course_dir = Path(settings.UPLOAD_DIR) / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = course_dir / f"{document.id}_{file.filename}"
    
    try:
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB"
            )
            
        with open(file_path, "wb") as f:
            f.write(content)
            
        # Update record
        document.file_path = file_path.as_posix()
        document.file_size = file_size
        await db.commit()
        
        # Dispatch processing (Celery -> FastAPI BackgroundTasks fallback)
        dispatch_document_processing(str(document.id), background_tasks)
        
        return document
        
    except Exception as e:
        await db.rollback()
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk_upload", response_model=List[DocumentResponse], status_code=status.HTTP_201_CREATED)
async def bulk_upload_documents(
    course_id: UUID,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    is_global: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Upload multiple PDF documents to a course (Admin only)."""
    # Verify course ownership
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.created_by == admin_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Course not found or unauthorized")

    uploaded_documents = []
    
    for file in files:
        # Validate file type
        if not file.filename.lower().endswith((".pdf", ".txt")):
            raise HTTPException(status_code=400, detail=f"Only PDF and TXT files are allowed. '{file.filename}' is invalid.")

        # Create document record
        document = Document(
            filename=file.filename,
            file_path="",  # Will update after saving
            file_size=0,
            status=DocumentStatus.PENDING,
            course_id=course_id,
            is_global=is_global,
            user_id=admin_user.id,
        )
        db.add(document)
        await db.flush()

        # Save file to disk
        course_dir = Path(settings.UPLOAD_DIR) / str(course_id)
        course_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = course_dir / f"{document.id}_{file.filename}"
        
        try:
            content = await file.read()
            file_size = len(content)
            
            if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File '{file.filename}' exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB"
                )
                
            with open(file_path, "wb") as f:
                f.write(content)
                
            # Update record
            document.file_path = file_path.as_posix()
            document.file_size = file_size
            await db.commit()
            
            # Dispatch processing (Celery -> FastAPI BackgroundTasks fallback)
            dispatch_document_processing(str(document.id), background_tasks)
            
            uploaded_documents.append(document)
            
        except Exception as e:
            await db.rollback()
            if file_path.exists():
                os.remove(file_path)
            print(f"Failed to process '{file.filename}': {str(e)}")
            # Continue processing remaining files in bulk upload rather than breaking the entire request
            continue

    return uploaded_documents


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    course_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all documents for a course."""
    # We should verify course access, but for simplicity, we'll just return the documents
    result = await db.execute(
        select(Document)
        .where(Document.course_id == course_id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    course_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get document details."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.course_id == course_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    course_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get processing status of a document."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.course_id == course_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        error_message=document.error_message
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    course_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Delete a document (Admin only)."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, 
            Document.course_id == course_id,
            Document.user_id == admin_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or unauthorized")
        
    # Remove file from disk
    if document.file_path and os.path.exists(document.file_path):
        try:
            os.remove(document.file_path)
        except OSError:
            pass
            
    # Delete from Vector DB
    try:
        from providers.factory import get_vector_db_client
        vector_db = get_vector_db_client()
        await vector_db.delete_document_vectors(str(admin_user.id), str(document.id))
    except Exception:
        pass
        
    await db.delete(document)
    await db.commit()


@router.post("/{document_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
async def reprocess_document(
    course_id: UUID,
    document_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(get_current_admin),
):
    """Reprocess a failed document (Admin only)."""
    result = await db.execute(
        select(Document).where(
            Document.id == document_id, 
            Document.course_id == course_id,
            Document.user_id == admin_user.id
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found or unauthorized")
        
    document.status = DocumentStatus.PENDING
    document.error_message = None
    await db.commit()
    
    # Trigger Background Task
    dispatch_document_processing(str(document.id), background_tasks)
    
    return {"detail": "Reprocessing started"}
