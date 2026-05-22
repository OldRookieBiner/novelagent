"""章节自检-精修流程测试"""

import asyncio
import pytest


def test_self_check_prompt_format():
    """自检 prompt 可正确 format"""
    from app.agents.prompts import DEFAULT_PROMPTS
    template = DEFAULT_PROMPTS.get("chapter_self_check", "")
    assert template, "chapter_self_check prompt missing"
    formatted = template.format(chapter_content="测试内容")
    assert "测试内容" in formatted
    assert "JSON" in formatted


def test_refine_prompt_format():
    """精修 prompt 可正确 format"""
    from app.agents.prompts import DEFAULT_PROMPTS
    template = DEFAULT_PROMPTS.get("chapter_refine", "")
    assert template, "chapter_refine prompt missing"
    formatted = template.format(check_result='{"paragraphs": []}', draft_content="测试初稿")
    assert "测试初稿" in formatted


def test_refinement_enabled_in_state():
    """NovelState 包含 refinement_enabled 字段"""
    from app.agents.state import NovelState
    annotations = NovelState.__annotations__
    assert "refinement_enabled" in annotations


def test_node_temperatures_self_check_and_refine():
    """NODE_TEMPERATURES 包含自检和精修的温度配置"""
    from app.agents.constants import NODE_TEMPERATURES
    assert "chapter_content_self_check" in NODE_TEMPERATURES
    assert "chapter_content_refine" in NODE_TEMPERATURES
    # 自检温度应较低（分析任务），精修温度适中
    assert NODE_TEMPERATURES["chapter_content_self_check"] < NODE_TEMPERATURES["chapter_content_refine"]


async def test_self_check_json_parsing_code_block():
    """_self_check_chapter 能解析代码块包裹的 JSON"""
    from app.agents.nodes.chapter_generation import _self_check_chapter
    from unittest.mock import MagicMock

    llm_response = '```json\n{"paragraphs": [{"index": 0, "issue": "AI味", "suggestion": "修改"}]}\n```'

    async def mock_chat_stream(*args, **kwargs):
        for chunk in [llm_response]:
            yield chunk

    llm = MagicMock()
    llm.chat_stream = mock_chat_stream

    result = await _self_check_chapter(llm, "测试初稿内容")
    assert "paragraphs" in result
    assert len(result["paragraphs"]) == 1
    assert result["paragraphs"][0]["index"] == 0


async def test_self_check_json_parsing_bare_json():
    """_self_check_chapter 能解析裸 JSON"""
    from app.agents.nodes.chapter_generation import _self_check_chapter
    from unittest.mock import MagicMock

    bare_json = '{"paragraphs": []}'

    async def mock_chat_stream(*args, **kwargs):
        for chunk in [bare_json]:
            yield chunk

    llm = MagicMock()
    llm.chat_stream = mock_chat_stream

    result = await _self_check_chapter(llm, "测试初稿内容")
    assert "paragraphs" in result
    assert len(result["paragraphs"]) == 0


async def test_self_check_json_parsing_invalid():
    """_self_check_chapter 对无效 JSON 返回空 paragraphs"""
    from app.agents.nodes.chapter_generation import _self_check_chapter
    from unittest.mock import MagicMock

    invalid_response = "这不是JSON"

    async def mock_chat_stream(*args, **kwargs):
        for chunk in [invalid_response]:
            yield chunk

    llm = MagicMock()
    llm.chat_stream = mock_chat_stream

    result = await _self_check_chapter(llm, "测试初稿内容")
    assert "paragraphs" in result
    assert len(result["paragraphs"]) == 0
