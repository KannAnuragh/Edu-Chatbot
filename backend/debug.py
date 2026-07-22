import asyncio
import os
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from core.config import settings
from qdrant_client import AsyncQdrantClient
from models.document import Document
from models.course import Course

sync_engine = create_engine(settings.DATABASE_URL_SYNC)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

async def check_qdrant():
    print("=== CHECKING QDRANT AND POSTGRES ===")
    
    # 1. Postgres Database
    db = SessionLocal()
    print("\n[POSTGRES] Courses in DB:")
    courses = db.query(Course).all()
    for c in courses:
        print(f"  - Course: {c.title} (ID: {c.id})")
        
    print("\n[POSTGRES] Documents in DB:")
    documents = db.query(Document).all()
    if not documents:
        print("  - No documents found in database.")
    for d in documents:
        print(f"  - Document: {d.filename} (ID: {d.id}) | Course ID: {d.course_id} | Status: {d.status.value}")
    db.close()
    
    # 2. Qdrant Database
    print("\n[QDRANT] Vector Database:")
    client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    try:
        col = await client.get_collection("course_documents")
        print(f"  - Collection 'course_documents' exists. Points count: {col.points_count}")
        
        if col.points_count > 0:
            course_counts = {}
            offset = None
            while True:
                res, next_offset = await client.scroll(
                    collection_name="course_documents",
                    limit=100,
                    with_payload=True,
                    offset=offset
                )
                for p in res:
                    cid = p.payload.get('course_id')
                    course_counts[cid] = course_counts.get(cid, 0) + 1
                if next_offset is None:
                    break
                offset = next_offset
            
            print("\n  - Points per course_id in Qdrant:")
            for cid, count in course_counts.items():
                print(f"    Course ID {cid}: {count} points")
        else:
            print("  - No points exist in Qdrant collection!")
            
    except Exception as e:
        print(f"  - Qdrant error: {e}")
        
    print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(check_qdrant())
