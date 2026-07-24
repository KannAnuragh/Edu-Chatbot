from providers.base import BaseEmbeddingProvider, BaseVectorDBProvider, BaseLLMProvider
from providers.cloudflare import CloudflareEmbeddingProvider, CloudflareVectorDBProvider, CloudflareLLMProvider

def get_embedding_client() -> BaseEmbeddingProvider:
    return CloudflareEmbeddingProvider()

def get_vector_db_client() -> BaseVectorDBProvider:
    return CloudflareVectorDBProvider()

def get_llm_client() -> BaseLLMProvider:
    return CloudflareLLMProvider()

# Singletons for generic use across the app
embedding_model = get_embedding_client()
llm_client = get_llm_client()
