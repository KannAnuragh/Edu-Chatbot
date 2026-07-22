"""
Celery Tasks for Background Processing.

Handles long-running operations like PDF ingestion.
"""

import os
import traceback
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from workers.celery_app import celery_app
from models.document import Document, DocumentStatus
from ingestion.pipeline import run_ingestion_pipeline

# Create a synchronous database engine for Celery
# Celery runs in a synchronous context, so we can't easily use AsyncSession
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def _get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str):
    """
    Background task to process an uploaded PDF document.
    Extracts text, chunks it, generates embeddings, and saves to vector DB.
    """
    db = next(_get_sync_db())
    
    try:
        # 1. Fetch document
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            print(f"Task processing failed: Document {document_id} not found.")
            return False
            
        print(f"Starting processing for document {document.filename} ({document_id})")
        
        # 2. Update status to PROCESSING
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        db.commit()
        
        # 3. Verify file exists
        if not document.file_path or not os.path.exists(document.file_path):
            raise FileNotFoundError(f"PDF file not found at {document.file_path}")
            
        # 4. Run ingestion pipeline
        page_count, language = run_ingestion_pipeline(
            file_path=document.file_path,
            filename=document.filename,
            user_id=str(document.user_id),
            course_id=str(document.course_id),
            document_id=str(document.id)
        )
        
        # 5. Update document with success
        document.page_count = page_count
        document.language = language
        document.status = DocumentStatus.READY
        db.commit()
        
        print(f"Successfully processed {document.filename}: {page_count} pages, {language} language.")
        return True
        
    except Exception as exc:
        print(f"Error processing document {document_id}: {exc}")
        traceback.print_exc()
        
        # Update document with error state
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = str(exc)[:2000]  # Truncate to fit column
                db.commit()
        except Exception as db_exc:
            print(f"Failed to update document error status: {db_exc}")
            
        # Retry logic for transient errors
        # (Only retry if it's not a clear unrecoverable error like FileNotFoundError)
        if not isinstance(exc, (FileNotFoundError, ValueError)):
            raise self.retry(exc=exc, countdown=60) # Retry after 1 minute
            
        return False
        
    finally:
        db.close()
