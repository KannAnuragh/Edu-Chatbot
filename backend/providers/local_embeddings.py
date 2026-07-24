from typing import List
import torch
from sentence_transformers import SentenceTransformer

from core.config import settings
from providers.base import BaseEmbeddingProvider

class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Implementation for local SentenceTransformers embeddings."""
    
    def __init__(self):
        self._model = None

    def _load_model(self):
        """Lazy load the model to save memory."""
        if self._model is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL, device=device)
            self._model.eval()

    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        self._load_model()
        # Ensure documents are prefixed with 'passage: ' if using e5 models
        if "e5" in settings.EMBEDDING_MODEL.lower():
            texts = [f"passage: {t}" for t in texts]
            
        embeddings = self._model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return embeddings.tolist()

    def encode_query(self, query: str) -> List[float]:
        self._load_model()
        # Prefix query with 'query: ' if using e5 models
        if "e5" in settings.EMBEDDING_MODEL.lower():
            query = f"query: {query}"
            
        embedding = self._model.encode([query], convert_to_numpy=True)
        return embedding[0].tolist()
