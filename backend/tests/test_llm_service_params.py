"""测试 LLMService temperature 和 reasoning_effort 参数透传"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_chat_uses_instance_temperature_by_default():
    """chat() 不传 temperature 时使用实例的 self.temperature"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.3
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_chat_uses_instance_reasoning_effort():
    """chat() 不传 reasoning_effort 时使用实例的 self.reasoning_effort"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = "high"
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_chat_skips_reasoning_effort_when_none():
    """chat() 在 reasoning_effort 为 None 时不传该参数"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs


@pytest.mark.asyncio
async def test_chat_skips_reasoning_effort_when_none_string():
    """chat() 在 reasoning_effort 为 'none' 时不传该参数"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.7
        service.reasoning_effort = "none"
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}])

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert "reasoning_effort" not in call_kwargs


@pytest.mark.asyncio
async def test_chat_allows_temperature_override():
    """chat() 显式传 temperature 时覆盖实例值"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ok"))]

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.3
        service.reasoning_effort = None
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)

        await service.chat([{"role": "user", "content": "test"}], temperature=0.9)

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.9


@pytest.mark.asyncio
async def test_chat_stream_uses_instance_params():
    """chat_stream() 同样使用实例 temperature 和 reasoning_effort"""
    from app.services.llm import LLMService

    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content="hi"), finish_reason=None)]
    final = MagicMock()
    final.choices = [MagicMock(delta=MagicMock(content=""), finish_reason="stop")]

    async def mock_stream(*args, **kwargs):
        for c in [chunk, final]:
            yield c

    with patch.object(LLMService, '__init__', lambda self, *a, **kw: None):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.model = "test"
        service.temperature = 0.5
        service.reasoning_effort = "medium"
        service.client.chat.completions.create = AsyncMock(return_value=mock_stream())

        result = []
        async for c in service.chat_stream([{"role": "user", "content": "test"}]):
            result.append(c)

        call_kwargs = service.client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["reasoning_effort"] == "medium"
        assert "stream" in call_kwargs and call_kwargs["stream"] is True
