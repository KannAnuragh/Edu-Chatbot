from typing import List, Dict, Any
from qdrant_client import QdrantClient, AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
import uuid

from core.config import settings
from providers.base import BaseVectorDBProvider

class QdrantVectorDBProvider(BaseVectorDBProvider):
    """Implementation for Qdrant Vector DB."""
    
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.async_client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    def ensure_collection(self, user_id: str):
        collection_name = f"user_{user_id.replace('-', '_')}"
        if not self.client.collection_exists(collection_name):
            self.client.create_collection(
                collection_name=collection_name,
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
        embeddings: List[List[float]]
    ):
        collection_name = f"user_{user_id.replace('-', '_')}"
        self.ensure_collection(user_id)
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}_chunk_{i}")),
                    vector=embedding,
                    payload={
                        "course_id": str(course_id),
                        "document_id": str(document_id),
                        "filename": str(filename),
                        "page_number": int(chunk["page_number"]),
                        "text": str(chunk["text"]),
                        "chunk_index": int(i)
                    }
                )
            )
            
        self.client.upsert(
            collection_name=collection_name,
            points=points
        )

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        collection_name = f"user_{user_id.replace('-', '_')}"
        
        try:
            results = await self.async_client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="course_id",
                            match=MatchValue(value=str(course_id))
                        )
                    ]
                )
            )
            
            return [hit.payload for hit in results]
        except Exception as e:
            print(f"Qdrant Search Error: {e}")
            return []

    async def delete_document_vectors(self, user_id: str, document_id: str):
        collection_name = f"user_{user_id.replace('-', '_')}"
        try:
            await self.async_client.delete(
                collection_name=collection_name,
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
