"""LLM service for interacting with AI models"""

import asyncio
import logging
from typing import AsyncIterator
import httpx
from openai import AsyncOpenAI, APIError

from app.config import settings

logger = logging.getLogger(__name__)

# 重试配置
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 秒


def _is_model_not_found_error(error: APIError) -> bool:
    """判断是否为模型不存在错误（404 且包含 model not found 语义）"""
    status_code = getattr(error, "status_code", None)
    if status_code != 404:
        return False
    error_str = str(error).lower()
    return "does not exist" in error_str or "model_not_found" in error_str or "not found" in error_str


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
        fallback_models: list[str] = None,
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
            fallback_models: 模型回退列表，当主模型 404 时依次尝试
        """
        self.provider = provider or settings.default_model_provider
        self.api_key = api_key
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.fallback_models = fallback_models or []

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

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(300.0, connect=30.0),  # 5分钟总超时，30秒连接超时
        )

    def _should_retry(self, error: APIError, attempt: int) -> bool:
        """判断是否应该重试同一模型"""
        if attempt >= MAX_RETRIES:
            return False
        # 模型不存在错误不重试同一模型（交给 fallback 机制处理）
        if _is_model_not_found_error(error):
            return False
        # 服务端超时(504)只重试1次，避免长时间阻塞（60s超时×3次=180s+）
        # 重试1次后仍504则切换到 fallback 模型
        status_code = getattr(error, "status_code", None)
        if status_code == 504 and attempt >= 1:
            return False
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

        # 尝试模型列表：主模型 + 回退模型
        models_to_try = [self.model] + self.fallback_models
        last_error = None

        for model_name in models_to_try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    kwargs = {
                        "model": model_name,
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
                    # 模型不存在 → 切换下一个模型
                    if _is_model_not_found_error(e) and self.fallback_models:
                        logger.warning(
                            f"Model '{model_name}' not found on provider, "
                            f"trying fallback models"
                        )
                        break
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

        # 尝试模型列表：主模型 + 回退模型
        models_to_try = [self.model] + self.fallback_models
        last_error = None

        for model_name in models_to_try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    kwargs = {
                        "model": model_name,
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
                    # 模型不存在 → 切换下一个模型
                    if _is_model_not_found_error(e) and self.fallback_models:
                        logger.warning(
                            f"Model '{model_name}' not found on provider, "
                            f"trying fallback models"
                        )
                        break
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

    模型选择优先级：
    1. model_override（前端传入的具体模型名）
    2. model_config.model_name（配置的默认模型名）
    3. models 列表中第一个 healthy 的模型
    4. models 列表中第一个 enabled 的模型

    回退模型列表：除主模型外的其他 healthy 模型，按顺序排列。
    当主模型在提供商端 404 时，自动切换到回退模型。
    """
    from app.services.crypto import decrypt_api_key

    api_key = (
        decrypt_api_key(model_config.api_key_encrypted, user_id)
        if model_config.api_key_encrypted
        else None
    )

    if not api_key:
        raise ValueError("API key not configured for this model")

    model = model_override or model_config.model_name
    target_item = None

    if model_config.models:
        # 尝试精确匹配指定的模型名
        for m in model_config.models:
            if m.get("is_enabled", True):
                if m.get("id") == model or m.get("name") == model:
                    target_item = m
                    model = m.get("id") or m.get("name")
                    break

        # 匹配到但 unhealthy 时，尝试回退到 healthy 模型
        if target_item and target_item.get("health_status") != "healthy":
            for m in model_config.models:
                if m.get("is_enabled", True) and m.get("health_status") == "healthy":
                    logger.warning(
                        f"Model '{model}' is unhealthy, falling back to healthy model '{m.get('id') or m.get('name')}'"
                    )
                    target_item = m
                    model = m.get("id") or m.get("name")
                    break

        # 未匹配到时，按 healthy > enabled 顺序回退
        if target_item is None:
            for m in model_config.models:
                if m.get("is_enabled", True) and m.get("health_status") == "healthy":
                    target_item = m
                    model = m.get("id") or m.get("name")
                    break
        if target_item is None:
            for m in model_config.models:
                if m.get("is_enabled", True):
                    target_item = m
                    model = m.get("id") or m.get("name")
                    break

    # 从匹配的 ModelItem 读取 temperature/reasoning_effort
    temperature = target_item.get("temperature", 0.7) if target_item else 0.7
    reasoning_effort = target_item.get("reasoning_effort") if target_item else None

    # 构建回退模型列表：除主模型外的其他 enabled 模型，healthy 优先
    fallback_models = []
    if model_config.models:
        healthy = []
        other = []
        for m in model_config.models:
            if not m.get("is_enabled", True):
                continue
            m_id = m.get("id") or m.get("name")
            if not m_id or m_id == model:
                continue
            if m.get("health_status") == "healthy":
                healthy.append(m_id)
            else:
                other.append(m_id)
        fallback_models = healthy + other

    logger.info(
        f"LLM model resolved: {model} "
        f"(override={model_override}, config_default={model_config.model_name}, "
        f"healthy={'yes' if target_item and target_item.get('health_status') == 'healthy' else 'no'}, "
        f"fallbacks={fallback_models})"
    )

    return LLMService(
        provider=model_config.provider,
        api_key=api_key,
        base_url=model_config.base_url,
        model=model,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        fallback_models=fallback_models,
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
