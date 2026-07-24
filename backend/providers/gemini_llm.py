import google.generativeai as genai
from typing import AsyncGenerator
from core.config import settings
from llm.prompts import SYSTEM_PROMPT
from providers.base import BaseLLMProvider

class GeminiLLMProvider(BaseLLMProvider):
    """Implementation for Google Gemini LLM."""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(settings.LLM_MODEL)

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser Query:\n{prompt}"
        
        try:
            response = await self.model.generate_content_async(
                full_prompt,
                stream=True
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            yield f"\n\n[Error generating response: {str(e)}]"

    def generate_response(self, prompt: str) -> str:
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser Query:\n{prompt}"
        response = self.model.generate_content(full_prompt)
        return response.text
