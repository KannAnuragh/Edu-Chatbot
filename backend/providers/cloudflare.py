"""
Cloudflare Providers.

Implementations for Cloudflare Workers AI (Embeddings, LLM) and Cloudflare Vectorize (Vector DB).
"""

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

    def encode(self, texts: List[str], batch_size: int = 5) -> List[List[float]]:
        # Pre-allocate results array to guarantee 1:1 mapping with input texts
        results = [None] * len(texts)
        
        # Build batches of valid indices and texts
        batches = []
        current_batch_indices = []
        current_batch_texts = []
        
        for idx, text in enumerate(texts):
            if text and str(text).strip():
                current_batch_indices.append(idx)
                current_batch_texts.append(text)
                
                if len(current_batch_texts) == batch_size:
                    batches.append((current_batch_indices, current_batch_texts))
                    current_batch_indices = []
                    current_batch_texts = []
                    
        if current_batch_texts:
            batches.append((current_batch_indices, current_batch_texts))

        default_dim = 1024 if "bge-m3" in settings.CLOUDFLARE_EMBEDDING_MODEL.lower() else 768

        with httpx.Client() as client:
            for indices, batch in batches:
                response = None
                max_retries = 3
                success = False

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
                            print(f"⚠️ Cloudflare rate limit hit (429). Retrying in {wait_time}s...", flush=True)
                            time.sleep(wait_time)
                            continue

                        if not response.is_success:
                            print(f"❌ Cloudflare Embedding Error ({response.status_code}): {response.text}", flush=True)
                            if response.status_code in [400, 500]:
                                # Non-retryable 400 or 500 — break retry loop to trigger single-item fallback
                                break
                            response.raise_for_status()

                        success = True
                        break
                    except (httpx.HTTPError, Exception) as e:
                        if attempt == max_retries - 1:
                            print(f"⚠️ Cloudflare embedding batch attempt failed: {e}", flush=True)
                        else:
                            time.sleep(1)

                if success and response and response.is_success:
                    data = response.json()
                    data_result = data.get("result", {}).get("data", [])
                    if len(data_result) > 0 and isinstance(data_result[0], list):
                        for j, emb in enumerate(data_result):
                            if j < len(indices):
                                results[indices[j]] = emb
                    else:
                        # Data is flat, reshape it
                        shape = data.get("result", {}).get("shape", [])
                        dim = shape[1] if len(shape) >= 2 else (len(data_result) // len(batch) if len(batch) > 0 else default_dim)
                        if dim <= 0:
                            dim = default_dim
                        
                        for j in range(len(batch)):
                            start = j * dim
                            if start + dim <= len(data_result) and j < len(indices):
                                results[indices[j]] = data_result[start:start+dim]
                else:
                    # Fallback: Process items individually for this batch if batching returned 400/500 or failed
                    print(f"⚠️ Batch of {len(batch)} items failed on Cloudflare AI. Falling back to single-item encoding...", flush=True)
                    for j, single_text in enumerate(batch):
                        try:
                            single_emb = self.encode_query(single_text)
                            results[indices[j]] = single_emb
                        except Exception as single_err:
                            print(f"❌ Single-item encoding failed for index {indices[j]}: {single_err}", flush=True)
                            # Leaves it as None in the results array

        return results

    def encode_query(self, query: str) -> List[float]:
        clean_query = query.strip() if query and query.strip() else " "
        with httpx.Client() as client:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.post(
                        self._get_url(),
                        headers=_get_cf_headers(),
                        json={"text": clean_query},
                        timeout=15.0
                    )
                    if response.status_code == 429:
                        wait_time = 2 ** attempt
                        print(f"⚠️ Cloudflare rate limit hit (429) for query. Retrying in {wait_time}s...", flush=True)
                        time.sleep(wait_time)
                        continue
                    
                    if not response.is_success:
                        print(f"❌ Cloudflare Query Embedding Error ({response.status_code}): {response.text}", flush=True)
                        response.raise_for_status()
                    
                    break
                except (httpx.HTTPError, Exception) as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(1)
            
            data = response.json()
            data_result = data.get("result", {}).get("data", [])
            
            # Handle both 2D [[vec]] and flat [vec] response formats
            if len(data_result) > 0 and isinstance(data_result[0], list):
                vector = data_result[0]
            else:
                # Flat array — this IS the vector for a single query
                vector = data_result
            
            print(f"📐 [EMBEDDING] Query vector dimension: {len(vector)}", flush=True)
            return vector


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
            batch_size = 50  # Balanced batch size for faster insertions but avoiding limits
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
                            if attempt == max_retries - 1:
                                print(f"⚠️ Cloudflare Vectorize upsert rate limit hit (429). Max retries exceeded.", flush=True)
                                response.raise_for_status()
                            wait_time = 2 ** attempt
                            print(f"⚠️ Cloudflare Vectorize upsert rate limit hit (429). Retrying in {wait_time}s...", flush=True)
                            time.sleep(wait_time)
                            continue
                        if not response.is_success:
                            error_msg = f"Cloudflare Vectorize Insert Error for {filename}: {response.status_code} - {response.text}"
                            print(error_msg, flush=True)
                            raise ValueError(error_msg)
                        break
                    except (httpx.HTTPError, Exception) as e:
                        if attempt == max_retries - 1:
                            raise e
                        wait_time = 2 ** attempt
                        print(f"⚠️ Cloudflare Vectorize upsert failed ({e}). Retrying in {wait_time}s...", flush=True)
                        time.sleep(wait_time)

    async def search(
        self, 
        user_id: str, 
        course_id: str, 
        query_vector: List[float], 
        limit: int = 7
    ) -> List[Dict[str, Any]]:
        url = f"{self._get_base_url()}/query"
        
        # NOTE: Cloudflare Vectorize requires explicit metadata indexes to be
        # created before filters work. Without a metadata index on 'course_id',
        # filtering silently returns 0 results. We do course filtering in Python
        # (in chat_service.py) instead.
        payload = {
            "vector": query_vector,
            "topK": limit,
            "returnValues": False,
            "returnMetadata": "all"
        }
        
        print(f"🔎 [VECTORIZE SEARCH] Index: {settings.CLOUDFLARE_VECTORIZE_INDEX} | topK: {limit} | course_id: {course_id}", flush=True)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=_get_cf_headers(),
                json=payload,
                timeout=15.0
            )
            if not response.is_success:
                print(f"❌ [VECTORIZE QUERY ERROR] Status: {response.status_code} | Body: {response.text}", flush=True)
                return []
                
            data = response.json()
            
            # Debug: Log raw response structure
            matches_raw = data.get("result", {}).get("matches", [])
            print(f"🔎 [VECTORIZE RAW] Got {len(matches_raw)} raw matches from Cloudflare Vectorize", flush=True)
            
            if matches_raw:
                # Log first match structure for debugging
                first = matches_raw[0]
                print(f"🔎 [VECTORIZE FIRST MATCH] id={first.get('id')} score={first.get('score')} metadata_keys={list(first.get('metadata', {}).keys())}", flush=True)
            
            results = []
            for match in matches_raw:
                if "metadata" in match:
                    result = dict(match["metadata"])
                    # CRITICAL: Include the similarity score in results
                    result["score"] = match.get("score", 0.0)
                    results.append(result)
                    
            # Sort by score descending (highest relevance first)
            results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            
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
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        
        print(f"🤖 [CLOUDFLARE LLM] Model: {settings.CLOUDFLARE_LLM_MODEL} | Prompt length: {len(prompt)} chars (~{len(prompt) // 4} tokens)", flush=True)
        
        total_output_chars = 0
        accumulated_text = ""
        async with httpx.AsyncClient() as client:
            try:
                async with client.stream("POST", url, headers=_get_cf_headers(), json=payload, timeout=60.0) as response:
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
                                    text = str(data["response"])
                                    accumulated_text += text
                                    total_output_chars += len(text)
                                    
                                    # Repetition detection: check every 200 chars
                                    if len(accumulated_text) > 400 and len(accumulated_text) % 50 < len(text):
                                        # Check if the last 200 chars repeat earlier in the output
                                        tail = accumulated_text[-200:]
                                        earlier = accumulated_text[:-200]
                                        if tail in earlier:
                                            print(f"⚠️ [LOOP DETECTED] Output repeating at {len(accumulated_text)} chars. Truncating.", flush=True)
                                            break
                                    
                                    yield text
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                yield f"\n\n[Streaming Error: {str(e)}]"
        
        # Log token usage estimate
        input_tokens_est = len(prompt) // 4
        output_tokens_est = total_output_chars // 4
        print(f"📊 [CLOUDFLARE LLM TOKEN USAGE]", flush=True)
        print(f"   Input:  ~{input_tokens_est} tokens ({len(prompt)} chars)", flush=True)
        print(f"   Output: ~{output_tokens_est} tokens ({total_output_chars} chars)", flush=True)
        print(f"   Total:  ~{input_tokens_est + output_tokens_est} tokens", flush=True)

    def generate_response(self, prompt: str) -> str:
        url = self._get_url()
        payload = {
            "messages": self._build_messages(prompt),
            "stream": False,
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        with httpx.Client() as client:
            response = client.post(url, headers=_get_cf_headers(), json=payload)
            if response.is_success:
                data = response.json()
                return data.get("result", {}).get("response", "")
            return f"Error: {response.text}"
