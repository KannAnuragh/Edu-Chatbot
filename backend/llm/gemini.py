"""
Google Gemini LLM Integration.

Handles streaming and non-streaming responses using google-genai.
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
            print(f"🤖 [GEMINI API CALL] Model: {settings.LLM_MODEL} | Prompt length: {len(prompt)} chars")
            response_stream = client.models.generate_content_stream(
                model=settings.LLM_MODEL,
                contents=prompt,
                config=self._get_config()
            )
            
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
                    
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
            return response.text
        except Exception as e:
            print(f"Gemini Error: {e}")
            return f"Error generating response: {str(e)}"


# Global singleton instance
gemini_client = GeminiClient()
