"""
Retrieval Service.

Handles searching Qdrant and formatting sources.
"""

from typing import List, Dict, Any, Optional
import asyncio
from functools import lru_cache

from core.config import settings
from providers.factory import embedding_model, get_vector_db_client


@lru_cache(maxsize=256)
def _cached_encode_query(query: str):
    """Cache repeated embeddings for the same query string to avoid re-encoding identical prompts."""
    return embedding_model.encode_query(query)


class RetrievalService:
    """Service for retrieving relevant document chunks."""
    
    def __init__(self):
        self.vector_db = get_vector_db_client()

    async def retrieve_relevant_chunks(
        self, 
        course_id: str, 
        query: str, 
        user_id: Optional[str] = None,
        top_k: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and search Qdrant for relevant chunks.
        Strictly scoped to the user's isolated collection and filtered by course.
        """
        if not query or not query.strip():
            return []

        # 1. Embed the query with a small in-memory cache to avoid re-encoding repeated prompts.
        query_text = query.strip()
        query_vector = await asyncio.to_thread(_cached_encode_query, query_text)

        # 2. Search Vector DB
        results = await self.vector_db.search(
            user_id=user_id,
            course_id=course_id,
            query_vector=query_vector,
            limit=top_k
        )

        return results

    def format_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format and deduplicate source references for the frontend.
        """
        sources = []
        seen = set()
        
        for chunk in chunks:
            # Create a unique key to prevent duplicate references to the same page
            key = f"{chunk['document_id']}_{chunk['page_number']}"
            
            if key not in seen:
                seen.add(key)
                sources.append({
                    "document_id": chunk["document_id"],
                    "filename": chunk["filename"],
                    "page_number": chunk["page_number"],
                    "chunk_text": chunk["text"]
                })
                
        return sources
