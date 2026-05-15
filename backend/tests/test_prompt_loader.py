"""测试 prompt loader 的有效性检查逻辑"""

from app.services.prompt_loader import get_system_prompt, MIN_PROMPT_LENGTH, _prompt_cache
from app.agents.prompts import DEFAULT_PROMPTS


def test_min_prompt_length_threshold():
    """MIN_PROMPT_LENGTH 应为合理阈值"""
    assert MIN_PROMPT_LENGTH >= 50


def test_default_prompts_are_long_enough():
    """DEFAULT_PROMPTS 中所有 prompt 都应超过最小长度"""
    for agent_type, prompt in DEFAULT_PROMPTS.items():
        # dict 格式（如 chapter_content_generation）检查 user 部分
        if isinstance(prompt, dict):
            text = prompt.get("user", "")
        else:
            text = prompt
        assert len(text.strip()) >= MIN_PROMPT_LENGTH, (
            f"DEFAULT_PROMPTS['{agent_type}'] is too short ({len(text.strip())} < {MIN_PROMPT_LENGTH})"
        )


def test_get_system_prompt_returns_default_when_db_empty():
    """数据库中无 prompt 时应返回 DEFAULT_PROMPTS"""
    # 清除缓存确保走 fallback 逻辑
    _prompt_cache.clear()

    class MockQuery:
        def filter(self, *args):
            return self
        def first(self):
            return None

    class MockDb:
        def query(self, model):
            return MockQuery()

    result = get_system_prompt(MockDb(), "outline_generation")
    assert result == DEFAULT_PROMPTS.get("outline_generation", "")
    assert len(result) > MIN_PROMPT_LENGTH


def test_get_system_prompt_falls_back_on_short_prompt():
    """数据库中 prompt 过短时应 fallback 到 DEFAULT_PROMPTS"""
    _prompt_cache.clear()

    class MockConfig:
        value = "Test prompt"

    class MockQuery:
        def filter(self, *args):
            return self
        def first(self):
            return MockConfig()

    class MockDb:
        def query(self, model):
            return MockQuery()

    result = get_system_prompt(MockDb(), "outline_generation")
    assert result == DEFAULT_PROMPTS.get("outline_generation", "")
    assert "Test prompt" not in result


def test_get_system_prompt_dict_type_returns_string():
    """dict 格式的 prompt（chapter_content_generation/review/rewrite）
    在 DB 无记录时应返回 user 模板字符串，而非整个 dict。

    回归测试：修复 'dict' object has no attribute 'format' 错误。
    """
    _prompt_cache.clear()

    class MockQuery:
        def filter(self, *args):
            return self
        def first(self):
            return None

    class MockDb:
        def query(self, model):
            return MockQuery()

    for key in ("chapter_content_generation", "review", "rewrite"):
        result = get_system_prompt(MockDb(), key)
        assert isinstance(result, str), (
            f"get_system_prompt('{key}') returned {type(result).__name__}, expected str"
        )
        assert len(result) > MIN_PROMPT_LENGTH, (
            f"get_system_prompt('{key}') returned too short: {len(result)}"
        )


def test_get_system_prompt_all_keys_return_string():
    """所有 agent_type 的 get_system_prompt 都应返回字符串"""
    _prompt_cache.clear()

    class MockQuery:
        def filter(self, *args):
            return self
        def first(self):
            return None

    class MockDb:
        def query(self, model):
            return MockQuery()

    for agent_type in DEFAULT_PROMPTS:
        result = get_system_prompt(MockDb(), agent_type)
        assert isinstance(result, str), (
            f"get_system_prompt('{agent_type}') returned {type(result).__name__}, expected str"
        )
