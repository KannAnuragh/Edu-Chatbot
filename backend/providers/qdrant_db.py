from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import uuid

from core.config import settings
from providers.base import BaseVectorDBProvider

class QdrantVectorDBProvider(BaseVectorDBProvider):
    """Implementation for Qdrant Vector DB."""
    
    COLLECTION_NAME = "courses_collection"
    
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.async_client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    def ensure_collection(self, user_id: str):
        if not self.client.collection_exists(self.COLLECTION_NAME):
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION, 
                    distance=Distance.COSINE
                ),
            )

    def upsert_chunks(
        self, 
        user_id: str, 
        course_id: str, 
        document_id: str, 
        filename: str,
        chunks: List[Dict[str, Any]], 
        embeddings: List[List[float]],
        is_global: bool = False
    ):
        self.ensure_collection(user_id)
        
        points = []
        effective_course_id = "GLOBAL" if is_global else str(course_id)
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}_chunk_{i}")),
                    vector=embedding,
                    payload={
                        "course_id": effective_course_id,
                        "document_id": str(document_id),
                        "filename": str(filename),
                        "page_number": int(chunk["page_number"]),
                        "text": str(chunk["text"]),
                        "chunk_index": int(i)
                    }
                )
            )
            
        self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points
        )

    async def search(
        self, 
        course_id: str, 
        query_vector: List[float], 
        user_id: Optional[str] = None, 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        
        try:
            # DEBUG: Check collection count
            try:
                count_result = await self.async_client.count(collection_name=self.COLLECTION_NAME)
                print(f"🐛 [QDRANT DEBUG] Total points in {self.COLLECTION_NAME}: {count_result.count}", flush=True)
                
                # DEBUG: Check points for this specific course_id
                course_count = await self.async_client.count(
                    collection_name=self.COLLECTION_NAME,
                    count_filter=Filter(
                        must=[FieldCondition(key="course_id", match=MatchValue(value=str(course_id)))]
                    )
                )
                print(f"🐛 [QDRANT DEBUG] Total points for course {course_id}: {course_count.count}", flush=True)
            except Exception as e:
                print(f"🐛 [QDRANT DEBUG] Failed to get count: {e}", flush=True)

            print(f"🐛 [QDRANT DEBUG] Searching vector of size {len(query_vector)} with limit {limit}", flush=True)

            results = await self.async_client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=query_vector,
                limit=limit
            )
            
            print(f"🐛 [QDRANT DEBUG] Search returned {len(results)} hits.", flush=True)
            
            # Include similarity score in results
            return [
                {**hit.payload, "score": hit.score}
                for hit in results
            ]
        except Exception as e:
            print(f"Qdrant Search Error: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return []

    async def delete_document_vectors(self, user_id: str, document_id: str):
        try:
            await self.async_client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id))
                        )
                    ]
                )
            )
        except Exception as e:
            print(f"Qdrant Delete Error: {e}")
