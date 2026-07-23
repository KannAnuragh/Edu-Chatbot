"""
Embeddings Model Singleton.

Uses Google GenAI (Gemini) to generate dense vector embeddings.
"""

from typing import List
from google.genai import types

from core.config import settings
from llm.gemini import gemini_client

class EmbeddingModel:
    """Singleton wrapper for the embedding model."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
        return cls._instance

    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Encode a list of texts into embeddings using Gemini."""
        client = gemini_client._get_client()
        if not client:
            raise ValueError("Gemini API Client not initialized. Please set GEMINI_API_KEY.")
            
        all_embeddings = []
        # Process in batches to avoid API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            result = client.models.embed_content(
                model='text-embedding-004',
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIMENSION)
            )
            all_embeddings.extend([embedding.values for embedding in result.embeddings])
            
        return all_embeddings

    def encode_query(self, query: str) -> List[float]:
        """Encode a single search query."""
        client = gemini_client._get_client()
        if not client:
            raise ValueError("Gemini API Client not initialized. Please set GEMINI_API_KEY.")
            
        result = client.models.embed_content(
            model='text-embedding-004',
            contents=[query],
            config=types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIMENSION)
        )
        return result.embeddings[0].values

# Global singleton instance
embedding_model = EmbeddingModel()
