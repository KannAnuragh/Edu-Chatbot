"""
Embeddings Model Singleton.

Uses sentence-transformers to generate dense vector embeddings.
"""

from typing import List
import torch
from sentence_transformers import SentenceTransformer

from core.config import settings

class EmbeddingModel:
    """Singleton wrapper for the embedding model."""
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingModel, cls).__new__(cls)
        return cls._instance

    def _load_model(self):
        """Lazy load the model to save memory during simple API requests."""
        if self._model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL, device=device)
            # Optimize for inference
            self._model.eval()

    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Encode a list of texts into embeddings."""
        self._load_model()
        
        # Determine prefix if needed (for models like bge-m3)
        # Using a general prefix or none for MiniLM
        embeddings = self._model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def encode_query(self, query: str) -> List[float]:
        """Encode a single search query."""
        self._load_model()
        # Some models benefit from a query prefix
        embedding = self._model.encode([query], convert_to_numpy=True)
        return embedding[0].tolist()


# Global singleton instance
embedding_model = EmbeddingModel()
