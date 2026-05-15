"""LLM service for interacting with AI models"""

import asyncio
import logging
from typing import AsyncIterator
from openai import AsyncOpenAI, APIError

from app.config import settings

logger = logging.getLogger(__name__)

# 重试配置
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 秒


class LLMService:
    """LLM service for generating content"""

    # Model configurations for presets
    MODEL_CONFIGS = {
        "deepseek": {
            "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
            "model": "deepseek-v3-241227",
        },
        "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
        "deepseek-official": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
    }

    def __init__(
        self,
        provider: str = None,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        temperature: float = 0.7,
        reasoning_effort: str = None,
    ):
        """
        初始化 LLM 服务

        Args:
            provider: 预设提供商标识 (deepseek, openai, deepseek-official)
            api_key: API Key
            base_url: 自定义 API 地址 (当 provider 为 "custom" 时使用)
            model: 自定义模型名称
            temperature: 生成温度 (默认 0.7)
            reasoning_effort: 推理努力程度 (如 "low"/"medium"/"high"，None 或 "none" 表示不传)
        """
        self.provider = provider or settings.default_model_provider
        self.api_key = api_key
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort

        if not self.api_key:
            raise ValueError("API key is required")

        # 获取配置
        if base_url:
            # 使用了自定义配置的 base_url，优先使用（不依赖预设）
            self.base_url = base_url
            self.model = model or settings.default_model
        else:
            # 使用预设配置
            config = self.MODEL_CONFIGS.get(
                self.provider, self.MODEL_CONFIGS["deepseek"]
            )
            self.base_url = config["base_url"]
            self.model = config["model"]

        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _should_retry(self, error: APIError, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= MAX_RETRIES:
            return False
        status_code = getattr(error, "status_code", None)
        if status_code in RETRYABLE_STATUS_CODES:
            return True
        # 网络错误也重试
        error_str = str(error).lower()
        if any(
            kw in error_str
            for kw in ["timeout", "connection", "network", "reset"]
        ):
            return True
        return False

    async def chat(
        self, messages: list[dict], temperature: float = None,
        max_tokens: int = 4096, reasoning_effort: str = None
    ) -> str:
        """Send a chat request and get response with retry"""
        # 使用实例默认值回退
        temp = temperature if temperature is not None else self.temperature
        effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": max_tokens,
                }
                if effort and effort != "none":
                    kwargs["reasoning_effort"] = effort
                response = await self.client.chat.completions.create(**kwargs)
                if not response.choices:
                    raise ValueError("LLM response has empty choices, no content available")
                return response.choices[0].message.content
            except APIError as e:
                last_error = e
                if not self._should_retry(e, attempt):
                    break
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"LLM chat attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
        raise last_error

    async def chat_stream(
        self, messages: list[dict], temperature: float = None,
        max_tokens: int = 4096, reasoning_effort: str = None
    ) -> AsyncIterator[str]:
        """Send a chat request and stream response with retry

        当输出因 max_tokens 截断时（finish_reason="length"），
        在日志中记录警告。调用方应根据 target_words 计算足够的 max_tokens。
        """
        # 使用实例默认值回退
        temp = temperature if temperature is not None else self.temperature
        effort = reasoning_effort if reasoning_effort is not None else self.reasoning_effort

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if effort and effort != "none":
                    kwargs["reasoning_effort"] = effort
                stream = await self.client.chat.completions.create(**kwargs)

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield delta.content

                    # 检测截断：finish_reason="length" 表示 max_tokens 不够
                    if chunk.choices and chunk.choices[0].finish_reason == "length":
                        logger.warning(
                            f"LLM output truncated (finish_reason=length). "
                            f"max_tokens={max_tokens} may be too low. "
                            f"Consider increasing max_tokens."
                        )
                return  # 成功，退出
            except APIError as e:
                last_error = e
                if not self._should_retry(e, attempt):
                    break
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"LLM chat_stream attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
        raise last_error

    async def chat_with_system(
        self, system_prompt: str, messages: list[dict], temperature: float = None,
        reasoning_effort: str = None
    ) -> str:
        """Chat with system prompt"""
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        return await self.chat(full_messages, temperature=temperature, reasoning_effort=reasoning_effort)


def get_llm_service_from_config(model_config, user_id: int, model_override: str = None) -> LLMService:
    """从模型配置获取 LLM 服务

    Args:
        model_config: 模型配置
        user_id: 用户 ID
        model_override: 可选，用户指定的模型名（覆盖 model_config.model_name）
    """
    from app.services.crypto import decrypt_api_key

    api_key = (
        decrypt_api_key(model_config.api_key_encrypted, user_id)
        if model_config.api_key_encrypted
        else None
    )

    if not api_key:
        raise ValueError("API key not configured for this model")

    # 确定模型名和参数：优先 model_override > model_name > models 列表第一个启用模型
    model = model_override or model_config.model_name
    target_item = None

    if model_config.models:
        for m in model_config.models:
            if m.get("is_enabled", True):
                if not model or m.get("id") == model or m.get("name") == model:
                    model = m.get("id") or m.get("name")
                    target_item = m
                    break

    # 从匹配的 ModelItem 读取 temperature/reasoning_effort
    temperature = target_item.get("temperature", 0.7) if target_item else 0.7
    reasoning_effort = target_item.get("reasoning_effort") if target_item else None

    return LLMService(
        provider=model_config.provider,
        api_key=api_key,
        base_url=model_config.base_url,
        model=model,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )


def get_llm_service(user_settings) -> LLMService:
    """从用户设置获取 LLM 服务 (兼容旧版本)"""
    from app.services.crypto import decrypt_api_key

    api_key = (
        decrypt_api_key(user_settings.api_key_encrypted, user_settings.user_id)
        if user_settings.api_key_encrypted
        else None
    )

    return LLMService(provider=user_settings.model_provider, api_key=api_key)
