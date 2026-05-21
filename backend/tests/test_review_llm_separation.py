"""测试审核 LLM 与创作 LLM 分离功能"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


def test_review_llm_config_id_in_state():
    """NovelState 应包含 review_llm_config_id 字段"""
    from app.agents.state import NovelState
    annotations = NovelState.__annotations__
    assert "review_llm_config_id" in annotations


@pytest.mark.asyncio
async def test_get_llm_for_review_uses_review_config():
    """for_review=True 且 review_llm_config_id 存在时，应使用审核模型配置"""
    from app.utils.llm import get_llm_from_state_async
    state = {
        "llm_config_id": 1,
        "llm_model_name": "model-a",
        "review_llm_config_id": 2,
    }
    with patch("app.utils.llm.get_llm_from_state") as mock_sync:
        mock_llm = MagicMock()
        mock_sync.return_value = mock_llm
        result = await get_llm_from_state_async(state, for_review=True)
        call_args = mock_sync.call_args
        assert call_args[0][0].get("llm_config_id") == 2


@pytest.mark.asyncio
async def test_get_llm_for_review_fallback_to_main():
    """for_review=True 但 review_llm_config_id 为 None 时，应回退到主模型"""
    from app.utils.llm import get_llm_from_state_async
    state = {
        "llm_config_id": 1,
        "llm_model_name": "model-a",
        "review_llm_config_id": None,
    }
    with patch("app.utils.llm.get_llm_from_state") as mock_sync:
        mock_llm = MagicMock()
        mock_sync.return_value = mock_llm
        result = await get_llm_from_state_async(state, for_review=True)
        call_args = mock_sync.call_args
        assert call_args[0][0].get("llm_config_id") == 1


@pytest.mark.asyncio
async def test_get_llm_for_review_invalid_config_fallback():
    """for_review=True 但审核模型配置加载失败时，应回退到主模型"""
    from app.utils.llm import get_llm_from_state_async
    state = {
        "llm_config_id": 1,
        "llm_model_name": "model-a",
        "review_llm_config_id": 999,  # 不存在的配置
    }
    call_count = 0
    original_state_ref = [None]

    def side_effect(s, db=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 第一次调用（审核配置）失败
            original_state_ref[0] = s
            raise ValueError("Model config not found")
        # 第二次调用（主模型）成功
        return MagicMock()

    with patch("app.utils.llm.get_llm_from_state", side_effect=side_effect):
        result = await get_llm_from_state_async(state, for_review=True)
        assert result is not None
        assert call_count == 2  # 审核配置失败后回退到主模型


@pytest.mark.asyncio
async def test_get_llm_not_for_review_ignores_review_config():
    """for_review=False 时，应忽略 review_llm_config_id，使用主模型"""
    from app.utils.llm import get_llm_from_state_async
    state = {
        "llm_config_id": 1,
        "llm_model_name": "model-a",
        "review_llm_config_id": 2,
    }
    with patch("app.utils.llm.get_llm_from_state") as mock_sync:
        mock_llm = MagicMock()
        mock_sync.return_value = mock_llm
        result = await get_llm_from_state_async(state, for_review=False)
        call_args = mock_sync.call_args
        assert call_args[0][0].get("llm_config_id") == 1


def test_workflow_run_request_has_review_llm_config_id():
    """WorkflowRunRequest 应包含 review_llm_config_id 字段"""
    from app.api.workflow import WorkflowRunRequest
    req = WorkflowRunRequest(llm_config_id=1, review_llm_config_id=2)
    assert req.review_llm_config_id == 2


def test_workflow_run_request_review_llm_config_id_default_none():
    """WorkflowRunRequest 的 review_llm_config_id 默认为 None"""
    from app.api.workflow import WorkflowRunRequest
    req = WorkflowRunRequest()
    assert req.review_llm_config_id is None
