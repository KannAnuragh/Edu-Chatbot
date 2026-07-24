import json
import uuid
import httpx
from typing import List, Dict, Any, AsyncGenerator

from core.config import settings
from llm.prompts import SYSTEM_PROMPT
from providers.base import BaseEmbeddingProvider, BaseVectorDBProvider, BaseLLMProvider


def _get_cf_headers():
    return {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }


class CloudflareEmbeddingProvider(BaseEmbeddingProvider):
    """Implementation for Cloudflare Workers AI Embeddings."""

    def _get_url(self):
        return f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/ai/run/{settings.CLOUDFLARE_EMBEDDING_MODEL}"

    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        all_embeddings = []
        with httpx.Client() as client:
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i+batch_size]
                response = client.post(
                    self._get_url(),
                    headers=_get_cf_headers(),
                    json={"text": batch},
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                shape = data.get("result", {}).get("shape", [])
                flat_data = data.get("result", {}).get("data", [])
                
                if len(shape) >= 2:
                    dim = shape[1]
                else:
                    dim = len(flat_data) // len(batch) if len(batch) > 0 else 768
                
                reshaped_data = [flat_data[j:j+dim] for j in range(0, len(flat_data), dim)]
                all_embeddings.extend(reshaped_data)
        return all_embeddings

    def encode_query(self, query: str) -> List[float]:
        with httpx.Client() as client:
            response = client.post(
                self._get_url(),
                headers=_get_cf_headers(),
                json={"text": [query]},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("result", {}).get("data", [])


class CloudflareVectorDBProvider(BaseVectorDBProvider):
    """Implementation for Cloudflare Vectorize."""

    def _get_base_url(self):
        index = settings.CLOUDFLARE_VECTORIZE_INDEX
        return f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/vectorize/v2/indexes/{index}"

    def ensure_collection(self, user_id: str):
        pass

    def upsert_chunks(
        self, 
        user_id: str, 
        course_id: str, 
        document_id: str, 
        filename: str,
        chunks: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ):
        url = f"{self._get_base_url()}/upsert"
        
        vectors = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}_chunk_{i}")).replace("-", ""),
                "values": embedding,
                "metadata": {
                    "course_id": str(course_id),
                    "document_id": str(document_id),
                    "filename": str(filename),
                    "page_number": int(chunk["page_number"]),
                    "text": str(chunk["text"]),
                    "chunk_index": int(i)
                }
            })

        with httpx.Client() as client:
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i+batch_size]
                
                ndjson_lines = [json.dumps(v, separators=(',', ':')) for v in batch]
                ndjson_content = "\n".join(ndjson_lines) + "\n"
                
                headers = _get_cf_headers()
                headers["Content-Type"] = "application/x-ndjson"
                
                response = client.post(
                    url,
                    headers=headers,
                    content=ndjson_content.encode("utf-8"),
                    timeout=30.0
                )
                if not response.is_success:
                    print(f"Cloudflare Vectorize Insert Error: {response.text}")

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        url = f"{self._get_base_url()}/query"
        payload = {
            "vector": query_vector,
            "topK": limit,
            "returnValues": False,
            "returnMetadata": "all",
            "filter": {"course_id": course_id}
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=_get_cf_headers(),
                json=payload,
                timeout=10.0
            )
            if not response.is_success:
                print(f"Cloudflare Vectorize Query Error: {response.text}")
                return []
                
            data = response.json()
            results = []
            for match in data.get("result", {}).get("matches", []):
                if "metadata" in match:
                    results.append(match["metadata"])
            return results

    async def delete_document_vectors(self, user_id: str, document_id: str):
        """Delete all chunk vectors belonging to a document from Cloudflare Vectorize."""
        url = f"{self._get_base_url()}/delete_by_ids"
        
        # Generate the deterministic IDs used during chunk upsert (up to max expected chunks, e.g., 500)
        ids_to_delete = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}_chunk_{i}")).replace("-", "")
            for i in range(500)
        ]

        async with httpx.AsyncClient() as client:
            batch_size = 100
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i:i + batch_size]
                response = await client.post(
                    url,
                    headers=_get_cf_headers(),
                    json={"ids": batch},
                    timeout=15.0
                )
                if response.is_success:
                    print(f"Successfully deleted vector batch for document {document_id}")
                else:
                    print(f"Cloudflare Vectorize Delete Error: {response.text}")


class CloudflareLLMProvider(BaseLLMProvider):
    """Implementation for Cloudflare Workers AI LLM."""
    
    def _get_url(self):
        return f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/ai/run/{settings.CLOUDFLARE_LLM_MODEL}"

    def _build_messages(self, prompt: str):
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        url = self._get_url()
        payload = {
            "messages": self._build_messages(prompt),
            "stream": True,
            "max_tokens": 2048
        }
        
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, headers=_get_cf_headers(), json=payload) as response:
                    if not response.is_success:
                        error_text = await response.aread()
                        yield f"\n\n[Cloudflare AI Error: {error_text.decode('utf-8')}]"
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                if "response" in data:
                                    yield data["response"]
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                yield f"\n\n[Streaming Error: {str(e)}]"

    def generate_response(self, prompt: str) -> str:
        url = self._get_url()
        payload = {
            "messages": self._build_messages(prompt),
            "stream": False,
            "max_tokens": 2048
        }
        with httpx.Client() as client:
            response = client.post(url, headers=_get_cf_headers(), json=payload)
            if response.is_success:
                data = response.json()
                return data.get("result", {}).get("response", "")
            return f"Error: {response.text}"
