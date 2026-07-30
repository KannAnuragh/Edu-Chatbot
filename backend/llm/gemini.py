"""
Google Gemini LLM Integration.

Handles streaming and non-streaming responses using google-genai.
Includes token usage tracking for observability.
"""

import os
from typing import AsyncGenerator
from google import genai
from google.genai import types

from core.config import settings
from llm.prompts import SYSTEM_PROMPT


class GeminiClient:
    """Singleton wrapper for Google Gemini API."""
    _instance = None
    _client = None
    _current_api_key = None
    _last_error = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GeminiClient, cls).__new__(cls)
        return cls._instance

    def _get_client(self):
        # Retrieve fresh key from env or settings
        raw_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY or ""
        api_key = raw_key.strip()
        
        if not api_key:
            self._client = None
            self._current_api_key = ""
            self._last_error = "GEMINI_API_KEY is empty in backend/.env"
            return None

        # Re-initialize client if key changed or client is None
        if self._client is None or self._current_api_key != api_key:
            try:
                self._client = genai.Client(api_key=api_key)
                self._current_api_key = api_key
                self._last_error = None
            except Exception as e:
                print(f"Error initializing genai.Client: {e}")
                self._client = None
                self._last_error = str(e)
                return None

        return self._client
        
    def _get_config(self) -> types.GenerateContentConfig:
        """Get standard generation config."""
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2, # Low temperature for more factual responses
            max_output_tokens=2048,
        )

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream response chunks from Gemini asynchronously."""
        client = self._get_client()
        if not client:
            error_details = self._last_error or "GEMINI_API_KEY is missing or invalid."
            yield f"\n\n[Gemini API Error: {error_details}\n\nPlease ensure you are using a valid Google AI Studio API Key (starting with 'AIzaSy...') in your `backend/.env` file and restart the backend container using `docker compose restart backend`.]"
            return
        
        try:
            print(f"🤖 [GEMINI API CALL] Model: {settings.LLM_MODEL} | Prompt length: {len(prompt)} chars (~{len(prompt) // 4} tokens)", flush=True)
            
            response_stream = client.aio.models.generate_content_stream(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=self._get_config()
            )
            
            total_output_chars = 0
            last_chunk = None
            async for chunk in response_stream:
                if chunk.text:
                    total_output_chars += len(chunk.text)
                    yield chunk.text
                last_chunk = chunk
            
            # Extract and log token usage from the final chunk's usage_metadata
            if last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                usage = last_chunk.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
                total_tokens = getattr(usage, 'total_token_count', 0) or (input_tokens + output_tokens)
                
                print(f"📊 [GEMINI TOKEN USAGE]", flush=True)
                print(f"   Input tokens:  {input_tokens}", flush=True)
                print(f"   Output tokens: {output_tokens}", flush=True)
                print(f"   Total tokens:  {total_tokens}", flush=True)
            else:
                # Fallback to character-based estimation
                input_tokens_est = len(prompt) // 4
                output_tokens_est = total_output_chars // 4
                print(f"📊 [GEMINI TOKEN USAGE (estimated)]", flush=True)
                print(f"   Input:  ~{input_tokens_est} tokens ({len(prompt)} chars)", flush=True)
                print(f"   Output: ~{output_tokens_est} tokens ({total_output_chars} chars)", flush=True)
                print(f"   Total:  ~{input_tokens_est + output_tokens_est} tokens", flush=True)
                    
        except Exception as e:
            print(f"Gemini Streaming Error: {e}")
            yield f"\n\n[Error generating response: {str(e)}]"

    def generate_response(self, prompt: str) -> str:
        """Generate a complete response synchronously."""
        client = self._get_client()
        if not client:
            error_details = self._last_error or "GEMINI_API_KEY is missing or invalid."
            return f"Error: {error_details}. Please ensure you are using a valid Google AI Studio API Key starting with 'AIzaSy...' in backend/.env."
        
        try:
            response = client.models.generate_content(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=self._get_config()
            )
            
            # Log token usage
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                print(f"📊 [GEMINI TOKEN USAGE] Input: {getattr(usage, 'prompt_token_count', '?')} | Output: {getattr(usage, 'candidates_token_count', '?')} | Total: {getattr(usage, 'total_token_count', '?')}", flush=True)
            
            return response.text
        except Exception as e:
            print(f"Gemini Error: {e}")
            return f"Error generating response: {str(e)}"


# Global singleton instance
gemini_client = GeminiClient()
