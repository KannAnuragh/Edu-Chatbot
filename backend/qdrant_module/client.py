"""
Qdrant Client wrapper for Vector Database operations.
"""

from typing import List, Dict, Any, Optional
import uuid
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client import models

from core.config import settings


class QdrantService:
    """Service for interacting with Qdrant vector database."""

    def __init__(self):
        # We use the sync client for Celery workers and async for FastAPI
        self.sync_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self._async_client = None
        
    async def get_async_client(self):
        """Get an async client instance."""
        if self._async_client is None:
            self._async_client = AsyncQdrantClient(url=f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        return self._async_client

    def _get_collection_name(self, user_id: str) -> str:
        """Get the global collection name for course documents."""
        return "course_documents"

    def ensure_collection(self, user_id: str):
        """Ensure the user's collection exists (sync for ingestion)."""
        collection_name = self._get_collection_name(user_id)
        
        try:
            self.sync_client.get_collection(collection_name)
        except Exception:
            # Create collection if it doesn't exist
            self.sync_client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=models.Distance.COSINE,
                ),
                # Optimize for hybrid search and payload filtering
                optimizers_config=models.OptimizersConfigDiff(
                    default_segment_number=2,
                )
            )
            # Create index on course_id for faster filtering
            self.sync_client.create_payload_index(
                collection_name=collection_name,
                field_name="course_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    def upsert_chunks(
        self, 
        user_id: str, 
        course_id: str, 
        document_id: str, 
        filename: str,
        chunks: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ):
        """Upsert document chunks and embeddings into Qdrant."""
        self.ensure_collection(user_id)
        collection_name = self._get_collection_name(user_id)
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}_chunk_{i}"))
            
            payload = {
                "course_id": course_id,
                "document_id": document_id,
                "filename": filename,
                "page_number": chunk["page_number"],
                "text": chunk["text"],
                "chunk_index": i,
            }
            
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload,
                )
            )

        # Batch upsert in chunks of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.sync_client.upsert(
                collection_name=collection_name,
                points=batch
            )

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks asynchronously."""
        collection_name = self._get_collection_name(user_id)
        client = await self.get_async_client()
        
        try:
            # Check if collection exists first
            await client.get_collection(collection_name)
            
            search_result = await client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="course_id",
                            match=models.MatchValue(value=course_id)
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
            )
            # DEBUG: Print the filter we are using and what we found
            print(f"DEBUG: Searching Qdrant with course_id={course_id}")
            for hit in search_result:
                if hit.payload:
                    print(f"DEBUG: Found chunk from course_id={hit.payload.get('course_id')}")

            return [hit.payload for hit in search_result if hit.payload]
            
        except Exception as e:
            print(f"Qdrant search error: {e}")
            return []

    async def delete_document_vectors(self, user_id: str, document_id: str):
        """Delete all vectors for a specific document."""
        collection_name = self._get_collection_name(user_id)
        client = await self.get_async_client()
        
        try:
            await client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id)
                            )
                        ]
                    )
                )
            )
        except Exception:
            pass  # Collection might not exist yet
