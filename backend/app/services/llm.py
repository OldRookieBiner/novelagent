"""LLM service for interacting with AI models"""

from typing import AsyncIterator, Optional
import httpx
from openai import AsyncOpenAI

from app.config import settings


class LLMService:
    """LLM service for generating content"""

    # Model configurations
    MODEL_CONFIGS = {
        "deepseek": {
            "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "model": "deepseek-v3-241227"
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o"
        },
        "deepseek-official": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat"
        }
    }

    def __init__(self, provider: str = None, api_key: str = None):
        self.provider = provider or settings.default_model_provider
        self.api_key = api_key or settings.default_api_key

        if not self.api_key:
            raise ValueError("API key is required")

        config = self.MODEL_CONFIGS.get(self.provider, self.MODEL_CONFIGS["deepseek"])

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=config["base_url"]
        )
        self.model = config["model"]

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Send a chat request and get response"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> AsyncIterator[str]:
        """Send a chat request and stream response"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_with_system(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7
    ) -> str:
        """Chat with system prompt"""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        return await self.chat(full_messages, temperature)


def get_llm_service(user_settings) -> LLMService:
    """Get LLM service from user settings"""
    from app.services.crypto import decrypt_api_key

    api_key = decrypt_api_key(user_settings.api_key_encrypted) if user_settings.api_key_encrypted else None

    return LLMService(
        provider=user_settings.model_provider,
        api_key=api_key
    )