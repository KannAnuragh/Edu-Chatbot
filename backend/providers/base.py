from typing import List, Dict, Any, AsyncGenerator

class BaseEmbeddingProvider:
    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        raise NotImplementedError

    def encode_query(self, query: str) -> List[float]:
        raise NotImplementedError

class BaseVectorDBProvider:
    def ensure_collection(self, user_id: str):
        raise NotImplementedError

    def upsert_chunks(
        self, 
        user_id: str, 
        course_id: str, 
        document_id: str, 
        filename: str,
        chunks: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ):
        raise NotImplementedError

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def delete_document_vectors(self, user_id: str, document_id: str):
        raise NotImplementedError

class BaseLLMProvider:
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    def generate_response(self, prompt: str) -> str:
        raise NotImplementedError
