"""LLM service for interacting with AI models"""

from typing import AsyncIterator, Optional
import httpx
from openai import AsyncOpenAI

from app.config import settings


class LLMService:
    """LLM service for generating content"""

    # Model configurations for presets
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

    def __init__(
        self,
        provider: str = None,
        api_key: str = None,
        base_url: str = None,
        model: str = None
    ):
        """
        初始化 LLM 服务

        Args:
            provider: 预设提供商标识 (deepseek, openai, deepseek-official)
            api_key: API Key
            base_url: 自定义 API 地址 (当 provider 为 "custom" 时使用)
            model: 自定义模型名称
        """
        self.provider = provider or settings.default_model_provider
        self.api_key = api_key

        if not self.api_key:
            raise ValueError("API key is required")

        # 获取配置
        if base_url and model:
            # 使用自定义配置
            self.base_url = base_url
            self.model = model
        else:
            # 使用预设配置
            config = self.MODEL_CONFIGS.get(self.provider, self.MODEL_CONFIGS["deepseek"])
            self.base_url = config["base_url"]
            self.model = config["model"]

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

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


def get_llm_service_from_config(model_config, user_id: int) -> LLMService:
    """从模型配置获取 LLM 服务"""
    from app.services.crypto import decrypt_api_key

    api_key = decrypt_api_key(model_config.api_key_encrypted, user_id) if model_config.api_key_encrypted else None

    if not api_key:
        raise ValueError("API key not configured for this model")

    return LLMService(
        provider=model_config.provider,
        api_key=api_key,
        base_url=model_config.base_url,
        model=model_config.model_name
    )


def get_llm_service(user_settings) -> LLMService:
    """从用户设置获取 LLM 服务 (兼容旧版本)"""
    from app.services.crypto import decrypt_api_key

    api_key = decrypt_api_key(user_settings.api_key_encrypted, user_settings.user_id) if user_settings.api_key_encrypted else None

    return LLMService(
        provider=user_settings.model_provider,
        api_key=api_key
    )
