"""回归测试：LLM chat_stream/chat 的 choices 空列表 IndexError 防护

bug-024: 某些 OpenAI 兼容 API 在流式响应中返回 choices=[] 的 chunk（如 usage chunk、ping chunk），
导致 chunk.choices[0] 抛出 IndexError，所有流式 LLM 调用（大纲生成、角色生成、章节生成等）全部失败。
chat() 方法的 response.choices[0] 同样缺少空列表防护。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_chat_stream_empty_choices_no_crash():
    """chat_stream 应安全跳过 choices=[] 的 chunk，不抛 IndexError"""
    from app.services.llm import LLMService

    # 构造模拟的流式响应：包含 choices=[] 的 chunk
    normal_chunk = MagicMock()
    normal_chunk.choices = [MagicMock(delta=MagicMock(content="Hello"), finish_reason=None)]

    empty_choices_chunk = MagicMock()
    empty_choices_chunk.choices = []

    # 某些 API 在流末尾发送 usage chunk，choices 为空
    usage_chunk = MagicMock()
    usage_chunk.choices = []

    final_chunk = MagicMock()
    final_chunk.choices = [MagicMock(delta=MagicMock(content=" world"), finish_reason="stop")]

    async def mock_stream(*args, **kwargs):
        for chunk in [normal_chunk, empty_choices_chunk, usage_chunk, final_chunk]:
            yield chunk

    with patch.object(
        LLMService, '__init__', lambda self, *a, **kw: setattr(self, 'client', AsyncMock())
    ):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.client.chat.completions.create = AsyncMock(return_value=mock_stream())
        service.model = "test-model"

        # 收集所有 yielded 内容
        chunks = []
        async for chunk in service.chat_stream([{"role": "user", "content": "test"}]):
            chunks.append(chunk)

        # 应只产出有效内容的 chunk，空 choices 不抛异常
        assert chunks == ["Hello", " world"]


@pytest.mark.asyncio
async def test_chat_stream_all_empty_choices_no_crash():
    """chat_stream 在所有 chunk 的 choices 都为空时，应返回空字符串而不崩溃"""
    from app.services.llm import LLMService

    empty_chunk = MagicMock()
    empty_chunk.choices = []

    async def mock_stream(*args, **kwargs):
        for _ in range(3):
            yield empty_chunk

    with patch.object(
        LLMService, '__init__', lambda self, *a, **kw: setattr(self, 'client', AsyncMock())
    ):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.client.chat.completions.create = AsyncMock(return_value=mock_stream())
        service.model = "test-model"

        chunks = []
        async for chunk in service.chat_stream([{"role": "user", "content": "test"}]):
            chunks.append(chunk)

        assert chunks == []


@pytest.mark.asyncio
async def test_chat_empty_choices_no_crash():
    """chat() 在 response.choices 为空时，应抛出有意义的错误而非 IndexError"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = []  # 空列表

    with patch.object(
        LLMService, '__init__', lambda self, *a, **kw: setattr(self, 'client', AsyncMock())
    ):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)
        service.model = "test-model"

        # 不应抛 IndexError，而应有更明确的错误信息
        with pytest.raises((ValueError, IndexError)) as exc_info:
            await service.chat([{"role": "user", "content": "test"}])

        # 确保不是裸 IndexError（应包含上下文信息）
        err_msg = str(exc_info.value)
        assert "choices" in err_msg or "response" in err_msg or "empty" in err_msg.lower() or "no content" in err_msg.lower()


@pytest.mark.asyncio
async def test_chat_normal_response_works():
    """chat() 在正常 response.choices 非空时正常工作"""
    from app.services.llm import LLMService

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="测试回复"))]

    with patch.object(
        LLMService, '__init__', lambda self, *a, **kw: setattr(self, 'client', AsyncMock())
    ):
        service = LLMService.__new__(LLMService)
        service.client = AsyncMock()
        service.client.chat.completions.create = AsyncMock(return_value=mock_response)
        service.model = "test-model"

        result = await service.chat([{"role": "user", "content": "test"}])
        assert result == "测试回复"
