from app.agents.token_budget import (
    estimate_tokens,
    get_context_window,
    calculate_context_budget,
    DEFAULT_CONTEXT_WINDOW,
)


def test_estimate_tokens_chinese():
    text = "你好世界"  # 4 个中文字
    result = estimate_tokens(text)
    assert result == max(int(4 * 0.72), 1)  # 2


def test_estimate_tokens_mixed():
    text = "Hello 你好"
    result = estimate_tokens(text)
    assert result > 0


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_get_context_window_no_config():
    """无 model_config 时返回默认值"""
    result = get_context_window()
    assert result == DEFAULT_CONTEXT_WINDOW


def test_get_context_window_config_level():
    """配置级别 context_window 优先"""
    class MockConfig:
        context_window = 200000
        models = None
    result = get_context_window(model_config=MockConfig())
    assert result == 200000


def test_get_context_window_sub_model():
    """coding_plan 子模型 context_window 最高优先"""
    class MockConfig:
        context_window = 200000
        models = [
            {"id": "model-a", "name": "Model A", "is_enabled": True, "context_window": 128000},
            {"id": "model-b", "name": "Model B", "is_enabled": True, "context_window": 512000},
        ]
    result = get_context_window(model_config=MockConfig(), model_name="model-b")
    assert result == 512000


def test_get_context_window_sub_model_fallback_to_config():
    """子模型未设 context_window 时回退到配置级别"""
    class MockConfig:
        context_window = 200000
        models = [
            {"id": "model-a", "name": "Model A", "is_enabled": True},
        ]
    result = get_context_window(model_config=MockConfig(), model_name="model-a")
    assert result == 200000


def test_get_context_window_config_none():
    """配置 context_window 为 None 时返回默认值"""
    class MockConfig:
        context_window = None
        models = None
    result = get_context_window(model_config=MockConfig())
    assert result == DEFAULT_CONTEXT_WINDOW


def test_get_context_window_default_value():
    """默认值应为 256K"""
    assert DEFAULT_CONTEXT_WINDOW == 262144


def test_calculate_context_budget():
    result = calculate_context_budget(
        model_max_tokens=128000,
        target_output_tokens=10000,
        system_prompt_tokens=3000,
    )
    # (128000 - 10000 - 3000) * 0.9 = 103500
    assert result == 103500


def test_calculate_context_budget_no_negative():
    result = calculate_context_budget(
        model_max_tokens=8192,
        target_output_tokens=8192,
        system_prompt_tokens=5000,
    )
    assert result >= 0
