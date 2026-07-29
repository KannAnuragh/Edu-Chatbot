import json
import uuid
import time
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
                
                # Retry logic for 429 / other transient errors
                response = None
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        response = client.post(
                            self._get_url(),
                            headers=_get_cf_headers(),
                            json={"text": batch},
                            timeout=45.0
                        )
                        if response.status_code == 429:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Cloudflare rate limit hit (429). Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        response.raise_for_status()
                        break
                    except (httpx.HTTPError, Exception) as e:
                        if attempt == max_retries - 1:
                            raise e
                        wait_time = 2 ** attempt
                        print(f"⚠️ Cloudflare API call failed ({e}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)

                data = response.json()
                
                data_result = data.get("result", {}).get("data", [])
                if len(data_result) > 0 and isinstance(data_result[0], list):
                    # Data is already 2D (list of list of floats)
                    all_embeddings.extend(data_result)
                else:
                    # Data is flat, reshape it
                    shape = data.get("result", {}).get("shape", [])
                    default_dim = 1024 if "bge-m3" in settings.CLOUDFLARE_EMBEDDING_MODEL.lower() else 768
                    if len(shape) >= 2:
                        dim = shape[1]
                    else:
                        dim = len(data_result) // len(batch) if len(batch) > 0 else default_dim
                    
                    if dim <= 0:
                        dim = default_dim
                    
                    reshaped_data = [data_result[j:j+dim] for j in range(0, len(data_result), dim)]
                    all_embeddings.extend(reshaped_data)
        return all_embeddings

    def encode_query(self, query: str) -> List[float]:
        with httpx.Client() as client:
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    response = client.post(
                        self._get_url(),
                        headers=_get_cf_headers(),
                        json={"text": [query]},
                        timeout=15.0
                    )
                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Cloudflare rate limit hit (429) for query. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    response.raise_for_status()
                    break
                except (httpx.HTTPError, Exception) as e:
                    if attempt == max_retries - 1:
                        raise e
                    wait_time = 2 ** attempt
                    print(f"⚠️ Cloudflare query embedding failed ({e}). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
            
            data = response.json()
            data_result = data.get("result", {}).get("data", [])
            if len(data_result) > 0 and isinstance(data_result[0], list):
                return data_result[0]
            return data_result


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
        clean_course_id = str(course_id).lower().strip()
        clean_doc_id = str(document_id).lower().strip()
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vectors.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{clean_doc_id}_chunk_{i}")).replace("-", ""),
                "values": embedding,
                "metadata": {
                    "course_id": clean_course_id,
                    "document_id": clean_doc_id,
                    "filename": str(filename),
                    "page_number": int(chunk["page_number"]),
                    "text": str(chunk["text"]),
                    "chunk_index": int(i)
                }
            })

        with httpx.Client() as client:
            batch_size = 50  # Smaller batch size to prevent HTTP payload timeouts on Cloudflare
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i+batch_size]
                
                ndjson_lines = [json.dumps(v, separators=(',', ':')) for v in batch]
                ndjson_content = "\n".join(ndjson_lines) + "\n"
                
                headers = _get_cf_headers()
                headers["Content-Type"] = "application/x-ndjson"
                
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        response = client.post(
                            url,
                            headers=headers,
                            content=ndjson_content.encode("utf-8"),
                            timeout=45.0
                        )
                        if response.status_code == 429:
                            wait_time = 2 ** attempt
                            print(f"⚠️ Cloudflare Vectorize upsert rate limit hit (429). Retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        if not response.is_success:
                            error_msg = f"Cloudflare Vectorize Insert Error for {filename}: {response.status_code} - {response.text}"
                            print(error_msg)
                            raise ValueError(error_msg)
                        break
                    except (httpx.HTTPError, Exception) as e:
                        if attempt == max_retries - 1:
                            raise e
                        wait_time = 2 ** attempt
                        print(f"⚠️ Cloudflare Vectorize upsert failed ({e}). Retrying in {wait_time}s...")
                        time.sleep(wait_time)

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 7
    ) -> List[Dict[str, Any]]:
        url = f"{self._get_base_url()}/query"
        payload = {
            "vector": query_vector,
            "topK": limit,
            "returnValues": False,
            "returnMetadata": "all",
            "filter": {"course_id": str(course_id).lower().strip()}
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
                                    yield str(data["response"])
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
