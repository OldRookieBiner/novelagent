"""Agent 常量测试"""
import pytest


def test_forbidden_words_not_empty():
    from app.agents.constants import FORBIDDEN_WORDS
    assert len(FORBIDDEN_WORDS) > 0


def test_forbidden_words_no_duplicates():
    from app.agents.constants import FORBIDDEN_WORDS
    assert len(FORBIDDEN_WORDS) == len(set(FORBIDDEN_WORDS))


def test_forbidden_patterns_not_empty():
    from app.agents.constants import FORBIDDEN_PATTERNS
    assert len(FORBIDDEN_PATTERNS) > 0


def test_forbidden_rules_not_empty():
    from app.agents.constants import FORBIDDEN_RULES
    assert len(FORBIDDEN_RULES) > 0