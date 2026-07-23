"""
Retrieval Service.

Handles searching Qdrant and formatting sources.
"""

from typing import List, Dict, Any
import asyncio

from embeddings.model import embedding_model
from qdrant_module.client import QdrantService


class RetrievalService:
    """Service for retrieving relevant document chunks."""
    
    def __init__(self):
        self.qdrant = QdrantService()

    async def retrieve_relevant_chunks(
        self, 
        user_id: str, 
        course_id: str, 
        query: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and search Qdrant for relevant chunks.
        Strictly scoped to the user's isolated collection and filtered by course.
        """
        # 1. Embed query (Run CPU-bound task in a separate thread to prevent blocking event loop)
        query_vector = await asyncio.to_thread(embedding_model.encode_query, query)
        
        # 2. Search Qdrant
        results = await self.qdrant.search(
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
