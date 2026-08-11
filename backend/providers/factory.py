"""
Provider Factory.

Reads provider settings from config and returns the correct implementation.
Supports: cloudflare, gemini (LLM), local (embeddings), qdrant (vector DB).
"""

from core.config import settings
from providers.base import BaseEmbeddingProvider, BaseVectorDBProvider, BaseLLMProvider


def get_embedding_client() -> BaseEmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower().strip()
    if provider == "cloudflare":
        from providers.cloudflare import CloudflareEmbeddingProvider
        return CloudflareEmbeddingProvider()
    elif provider == "local":
        from providers.local_embeddings import LocalEmbeddingProvider
        return LocalEmbeddingProvider()
    else:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER: '{provider}'. Use 'cloudflare' or 'local'.")


def get_vector_db_client() -> BaseVectorDBProvider:
    provider = settings.VECTOR_DB_PROVIDER.lower().strip()
    if provider == "cloudflare":
        from providers.cloudflare import CloudflareVectorDBProvider
        return CloudflareVectorDBProvider()
    elif provider == "qdrant":
        from providers.qdrant_db import QdrantVectorDBProvider
        return QdrantVectorDBProvider()
    else:
        raise ValueError(f"Unknown VECTOR_DB_PROVIDER: '{provider}'. Use 'cloudflare' or 'qdrant'.")


def get_llm_client() -> BaseLLMProvider:
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "cloudflare":
        from providers.cloudflare import CloudflareLLMProvider
        return CloudflareLLMProvider()
    elif provider == "gemini":
        from llm.gemini import GeminiClient
        return GeminiClient()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Use 'cloudflare' or 'gemini'.")


# Singletons for generic use across the app
embedding_model = get_embedding_client()
llm_client = get_llm_client()
