from core.config import settings
from providers.base import BaseEmbeddingProvider, BaseVectorDBProvider, BaseLLMProvider


def get_embedding_client() -> BaseEmbeddingProvider:
    if settings.EMBEDDING_PROVIDER.lower() == "cloudflare":
        from providers.cloudflare import CloudflareEmbeddingProvider
        return CloudflareEmbeddingProvider()
    else:
        from providers.local_embeddings import LocalEmbeddingProvider
        return LocalEmbeddingProvider()


def get_vector_db_client() -> BaseVectorDBProvider:
    if settings.VECTOR_DB_PROVIDER.lower() == "cloudflare":
        from providers.cloudflare import CloudflareVectorDBProvider
        return CloudflareVectorDBProvider()
    else:
        from providers.qdrant_db import QdrantVectorDBProvider
        return QdrantVectorDBProvider()


def get_llm_client() -> BaseLLMProvider:
    if settings.LLM_PROVIDER.lower() == "cloudflare":
        from providers.cloudflare import CloudflareLLMProvider
        return CloudflareLLMProvider()
    else:
        from providers.gemini_llm import GeminiLLMProvider
        return GeminiLLMProvider()

# Singletons for generic use across the app
embedding_model = get_embedding_client()
llm_client = get_llm_client()
