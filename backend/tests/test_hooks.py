"""Hook 单元测试 — 覆盖 rhythm_quick_check + 注册表"""
import pytest
from unittest.mock import patch, MagicMock

from app.agents.tools.hooks import (
    TOOL_HOOKS,
    _HOOK_FUNCTIONS,
    _hook_rhythm_quick_check,
    run_post_hooks,
)


def _mock_kb_for_rhythm(expected_mood: str | None, tension_score: int | None):
    """构造一个 KnowledgeBaseService mock，覆盖 plots.get_current_plot_block + timelines.get_by_chapter_number"""
    kb = MagicMock()
    if expected_mood is None:
        kb.plots.get_current_plot_block.return_value = None
    else:
        kb.plots.get_current_plot_block.return_value = {
            "title": "第一幕",
            "expected_mood": expected_mood,
        }
    if tension_score is None:
        kb.timelines.get_by_chapter_number.return_value = None
    else:
        kb.timelines.get_by_chapter_number.return_value = {"tension_score": tension_score}
    return kb


@pytest.mark.asyncio
@patch("app.agents.tools.hooks.KnowledgeBaseService", create=True)
async def test_rhythm_quick_check_returns_warning_on_deviation(_unused):
    """偏差 > 1 时返回 warning + suggestion"""
    # 直接 patch 到模块内部 import 路径
    with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
        # expected_mood='高潮' → tension≈5；timeline tension_score=2 → 偏差 3
        MockKB.return_value = _mock_kb_for_rhythm("高潮", 2)
        result = await _hook_rhythm_quick_check(project_id=1, tool_result={"chapter_number": 3})
    assert result["checked"] is True
    assert "warning" in result
    assert "suggestion" in result
    assert result["deviation"] >= 2


@pytest.mark.asyncio
async def test_rhythm_quick_check_normal_when_aligned():
    with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
        # '平稳' → 张力≈3，actual=3 → 偏差 0
        MockKB.return_value = _mock_kb_for_rhythm("平稳", 3)
        result = await _hook_rhythm_quick_check(project_id=1, tool_result={"chapter_number": 1})
    assert result["checked"] is True
    assert result.get("status") == "normal"
    assert "warning" not in result


@pytest.mark.asyncio
async def test_rhythm_quick_check_skipped_without_timeline():
    with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
        MockKB.return_value = _mock_kb_for_rhythm("紧张", None)
        result = await _hook_rhythm_quick_check(project_id=1, tool_result={"chapter_number": 5})
    assert result["checked"] is False
    assert "无时间线" in result["reason"]


@pytest.mark.asyncio
async def test_rhythm_quick_check_skipped_without_plot_block():
    with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
        MockKB.return_value = _mock_kb_for_rhythm(None, 3)
        result = await _hook_rhythm_quick_check(project_id=1, tool_result={"chapter_number": 5})
    assert result["checked"] is False


@pytest.mark.asyncio
async def test_rhythm_quick_check_no_chapter_number():
    result = await _hook_rhythm_quick_check(project_id=1, tool_result={})
    assert result["checked"] is False
    assert "章节号" in result["reason"]


def test_tool_hooks_registers_record_chapter_meta():
    assert "record_chapter_meta" in TOOL_HOOKS
    assert "rhythm_quick_check" in TOOL_HOOKS["record_chapter_meta"]
    assert "rhythm_quick_check" in _HOOK_FUNCTIONS


def test_tool_hooks_preserves_existing_generate_chapter_content_hooks():
    """确保新增不破坏原有 generate_chapter_content 的 hook 列表"""
    hooks = TOOL_HOOKS.get("generate_chapter_content", [])
    assert "foreshadowing_check" in hooks
    assert "style_quick_check" in hooks


@pytest.mark.asyncio
async def test_run_post_hooks_attaches_auto_check_results_for_record_chapter_meta():
    """run_post_hooks 在 record_chapter_meta 工具上将 rhythm_quick_check 结果挂到 auto_check_results"""
    with patch("app.agents.services.knowledge_base.KnowledgeBaseService") as MockKB:
        MockKB.return_value = _mock_kb_for_rhythm("高潮", 2)
        tool_result = {"chapter_number": 3}
        out = await run_post_hooks("record_chapter_meta", tool_result, project_id=1)
    assert "auto_check_results" in out
    assert "rhythm_quick_check" in out["auto_check_results"]
