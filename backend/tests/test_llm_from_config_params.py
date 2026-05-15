"""测试 get_llm_service_from_config 从 ModelItem 读取 temperature/reasoning_effort"""
import pytest
from unittest.mock import MagicMock, patch


def _make_config(models=None, model_name=None, provider="custom",
                 base_url="https://api.test.com/v1", api_key_encrypted=None):
    """创建模拟的 ModelConfig 对象"""
    config = MagicMock()
    config.provider = provider
    config.base_url = base_url
    config.model_name = model_name
    config.models = models
    config.api_key_encrypted = api_key_encrypted
    return config


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_reads_temperature_from_model_item(mock_decrypt):
    """从 models 列表中读取 temperature"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.3, "reasoning_effort": None}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.temperature == 0.3


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_reads_reasoning_effort_from_model_item(mock_decrypt):
    """从 models 列表中读取 reasoning_effort"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.7, "reasoning_effort": "high"}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.reasoning_effort == "high"


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_uses_default_when_model_item_missing_fields(mock_decrypt):
    """ModelItem 缺少 temperature/reasoning_effort 时使用默认值"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[{"id": "m1", "name": "model-1", "is_enabled": True}],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.temperature == 0.7
    assert service.reasoning_effort is None


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_matches_model_by_override(mock_decrypt):
    """model_override 匹配特定 ModelItem 读取参数"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[
            {"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.7, "reasoning_effort": None},
            {"id": "m2", "name": "model-2", "is_enabled": True, "temperature": 0.3, "reasoning_effort": "high"},
        ],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1, model_override="m2")
    assert service.temperature == 0.3
    assert service.reasoning_effort == "high"
    assert service.model == "m2"


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_matches_model_by_name(mock_decrypt):
    """model_override 通过 name 也能匹配 ModelItem"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        models=[
            {"id": "m1", "name": "model-1", "is_enabled": True, "temperature": 0.7, "reasoning_effort": None},
            {"id": "m2", "name": "model-2", "is_enabled": True, "temperature": 0.3, "reasoning_effort": "high"},
        ],
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1, model_override="model-2")
    assert service.temperature == 0.3
    assert service.reasoning_effort == "high"


@patch("app.services.crypto.decrypt_api_key", return_value="test-key")
def test_fallback_to_model_name_when_no_models(mock_decrypt):
    """无 models 列表时回退到 model_name，使用默认 temperature"""
    from app.services.llm import get_llm_service_from_config

    config = _make_config(
        model_name="fallback-model",
        api_key_encrypted=b"encrypted"
    )

    service = get_llm_service_from_config(config, user_id=1)
    assert service.model == "fallback-model"
    assert service.temperature == 0.7
    assert service.reasoning_effort is None
