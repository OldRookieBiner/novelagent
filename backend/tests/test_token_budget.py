from app.agents.token_budget import estimate_tokens, get_context_window, calculate_context_budget
from app.agents.constants import MODEL_CONTEXT_WINDOWS, DEFAULT_CONTEXT_WINDOW


def test_estimate_tokens_chinese():
    text = "你好世界"  # 4 个中文字
    result = estimate_tokens(text)
    assert result == 4 * 2  # 8


def test_estimate_tokens_mixed():
    text = "Hello 你好"
    result = estimate_tokens(text)
    assert result > 0


def test_get_context_window_known_model():
    result = get_context_window("deepseek-chat")
    assert result == MODEL_CONTEXT_WINDOWS["deepseek-chat"]


def test_get_context_window_unknown_model():
    result = get_context_window("some-unknown-model-v1")
    assert result == DEFAULT_CONTEXT_WINDOW


def test_get_context_window_db_config_priority():
    class MockConfig:
        context_window = 999999
    result = get_context_window("deepseek-chat", model_config=MockConfig())
    assert result == 999999


def test_get_context_window_db_config_none():
    class MockConfig:
        context_window = None
    result = get_context_window("deepseek-chat", model_config=MockConfig())
    assert result == MODEL_CONTEXT_WINDOWS["deepseek-chat"]


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
