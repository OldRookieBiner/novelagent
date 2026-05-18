"""弧纲生成节点和弧路由集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.nodes.arc_outline_generation import (
    arc_outline_generation_node,
    _build_arc_outline_messages,
)
from app.agents.state import STAGE_ARC_OUTLINES, STAGE_CHAPTER_OUTLINES


# ==================== _build_arc_outline_messages 测试 ====================


def test_build_arc_outline_messages_contains_arc_info():
    """验证 prompt 包含弧结构信息"""
    state = {
        "outline_title": "测试小说",
        "outline_summary": "测试概要",
        "outline_plot_points": [{"event": "主角出场"}],
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
        "_prompts": {},
    }
    arc = {"arc_number": 1, "title": "起始之弧", "chapter_count": 10, "volume_number": 1}
    messages = _build_arc_outline_messages(state, arc, [])
    assert len(messages) == 1
    assert "起始之弧" in messages[0]["content"]
    assert "第1弧" in messages[0]["content"]


def test_build_arc_outline_messages_includes_other_arcs():
    """验证 prompt 包含已生成弧纲的上下文"""
    state = {
        "outline_title": "测试小说",
        "outline_summary": "测试概要",
        "outline_plot_points": [],
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
        "_prompts": {},
    }
    arc = {"arc_number": 2, "title": "第二弧", "chapter_count": 15, "volume_number": 1}
    generated = [{"arc_number": 1, "outline": "第一弧的概要内容"}]
    messages = _build_arc_outline_messages(state, arc, generated)
    assert "第一弧的概要内容" in messages[0]["content"]


def test_build_arc_outline_messages_empty_plot_points():
    """验证无情节节点时不崩溃"""
    state = {
        "outline_title": "测试小说",
        "outline_summary": "",
        "outline_plot_points": [],
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
        "_prompts": {},
    }
    arc = {"arc_number": 1, "title": "弧", "chapter_count": 5, "volume_number": 1}
    messages = _build_arc_outline_messages(state, arc, [])
    assert len(messages) == 1


# ==================== arc_outline_generation_node 测试 ====================


@pytest.mark.asyncio
async def test_arc_outline_generation_node_sets_stage():
    """验证节点返回正确的 stage 和 confirmation_type"""
    state = {
        "outline_title": "测试小说",
        "outline_summary": "测试概要",
        "outline_plot_points": [],
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
        "arcs": [
            {"arc_number": 1, "title": "弧1", "chapter_count": 5, "volume_number": 1},
            {"arc_number": 2, "title": "弧2", "chapter_count": 8, "volume_number": 1},
        ],
        "_prompts": {},
    }

    # Mock LLM: chat_stream 返回 async generator
    async def mock_chat_stream(*args, **kwargs):
        yield "核心冲突：测试冲突"

    mock_llm = AsyncMock()
    mock_llm.chat_stream = mock_chat_stream

    with patch("app.utils.llm.get_llm_from_state_async", return_value=mock_llm), \
         patch("langgraph.config.get_stream_writer", return_value=lambda x: None):
        result = await arc_outline_generation_node(state)

    assert result["stage"] == STAGE_ARC_OUTLINES
    assert result["waiting_for_confirmation"] is True
    assert result["confirmation_type"] == "arc_outlines"


@pytest.mark.asyncio
async def test_arc_outline_generation_node_updates_arcs():
    """验证节点更新 arcs 中的 outline 字段"""
    state = {
        "outline_title": "测试小说",
        "outline_summary": "测试概要",
        "outline_plot_points": [],
        "characters": [],
        "relations": [],
        "evolution_plans": [],
        "evolution_records": [],
        "arcs": [
            {"arc_number": 1, "title": "弧1", "chapter_count": 5, "volume_number": 1},
        ],
        "_prompts": {},
    }

    # Mock LLM: 多 chunk 流式输出
    async def mock_chat_stream(*args, **kwargs):
        yield "核心冲突：测试"
        yield "冲突内容"

    mock_llm = AsyncMock()
    mock_llm.chat_stream = mock_chat_stream

    with patch("app.utils.llm.get_llm_from_state_async", return_value=mock_llm), \
         patch("langgraph.config.get_stream_writer", return_value=lambda x: None):
        result = await arc_outline_generation_node(state)

    assert result["arcs"][0]["outline"] == "核心冲突：测试冲突内容"


# ==================== 图路由测试 ====================


def test_route_after_relations_long_novel_with_arcs():
    """验证长篇有弧时路由到 arc_outlines"""
    from app.agents.graph import route_after_relations

    state = {
        "chapter_count": 50,
        "characters": [{"name": "主角"}],
        "waiting_for_confirmation": False,
        "novel_length": "long",
        "arcs": [{"arc_number": 1, "title": "弧1", "chapter_count": 10}],
    }
    assert route_after_relations(state) == "arc_outlines"


def test_route_after_relations_short_novel():
    """验证短篇路由到 chapter_outlines"""
    from app.agents.graph import route_after_relations

    state = {
        "chapter_count": 10,
        "characters": [{"name": "主角"}],
        "waiting_for_confirmation": False,
        "novel_length": "short",
        "arcs": [],
    }
    assert route_after_relations(state) == "chapter_outlines"


def test_route_after_arc_outlines_waiting():
    """验证弧纲生成后暂停等确认"""
    from app.agents.graph import route_after_arc_outlines

    state = {
        "waiting_for_confirmation": True,
        "arcs": [{"arc_number": 1}],
    }
    assert route_after_arc_outlines(state) == "wait_confirm"


def test_route_after_arc_outlines_confirmed():
    """验证弧纲确认后进入章节大纲"""
    from app.agents.graph import route_after_arc_outlines

    state = {
        "waiting_for_confirmation": False,
        "arcs": [{"arc_number": 1}],
    }
    assert route_after_arc_outlines(state) == "chapter_outlines"


def test_route_after_chapter_outlines_arc_loop():
    """验证长篇按弧模式中章节大纲循环回自身"""
    from app.agents.graph import route_after_chapter_outlines

    state = {
        "chapter_outlines": [{"chapter_number": 1}],
        "waiting_for_confirmation": False,
        "novel_length": "long",
        "arcs": [{"arc_number": 1}, {"arc_number": 2}],
        "current_arc_index": 1,
    }
    assert route_after_chapter_outlines(state) == "chapter_outlines"


def test_route_after_chapter_outlines_all_arcs_done():
    """验证长篇所有弧完成后进入章节正文"""
    from app.agents.graph import route_after_chapter_outlines

    state = {
        "chapter_outlines": [{"chapter_number": 1}],
        "waiting_for_confirmation": False,
        "novel_length": "long",
        "arcs": [{"arc_number": 1}],
        "current_arc_index": 1,
    }
    # current_arc_index (1) >= len(arcs) (1), 所有弧完成
    # 应走 wait_for_confirmation 逻辑，返回 chapter_content
    result = route_after_chapter_outlines(state)
    assert result == "chapter_content"
