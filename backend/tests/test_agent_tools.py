"""Unit tests for cognitive tools (agent_tools.py)

Tests tool registration, helper functions, and impact grading.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.tools import (
    knowledge_search,
    foreshadowing_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
    AGENT_TOOLS,
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    _extract_keywords,
    _grade_impact,
)


class TestToolRegistration:
    """Verify all cognitive tools are properly registered."""

    def test_writing_tools_has_all_tools(self):
        assert len(WRITING_TOOLS) >= 20, f'Expected at least 20 tools, got {len(WRITING_TOOLS)}'

    def test_incubation_tools_subset(self):
        assert len(INCUBATION_TOOLS) >= 8, f'Expected at least 8 tools, got {len(INCUBATION_TOOLS)}'
        assert knowledge_search in INCUBATION_TOOLS

    def test_structure_tools_subset(self):
        assert len(STRUCTURE_TOOLS) >= 10, f'Expected at least 10 tools, got {len(STRUCTURE_TOOLS)}'
        assert propose_outline_adjustment in STRUCTURE_TOOLS

    def test_all_tools_have_names(self):
        for tool in AGENT_TOOLS:
            assert tool.name, f"Tool {tool} missing name"
            assert tool.description, f"Tool {tool.name} missing description"

    def test_perception_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["knowledge_search", "foreshadowing_check", "consistency_scan",
                         "style_analysis", "progress_report", "rhythm_analysis"]:
            assert expected in names, f"Missing perception tool: {expected}"

    def test_modification_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["propose_setting_change", "propose_outline_adjustment", "propose_chapter_rewrite"]:
            assert expected in names, f"Missing modification tool: {expected}"

    def test_creation_assist_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["writer_block_assist", "suggest_foreshadowing", "suggest_plot_twist", "expand_world_setting"]:
            assert expected in names, f"Missing creation assist tool: {expected}"


class TestHelperFunctions:
    """Test internal helper functions."""

    def test_extract_keywords_from_description(self):
        keywords = _extract_keywords({}, {}, "主角的魔法限制被修改")
        assert len(keywords) > 0

    def test_grade_impact_none(self):
        level, detail = _grade_impact([], "world_setting", {}, {})
        assert level == "none"

    def test_grade_impact_minor(self):
        affected = [{"matching_paragraphs": [{"index": 0, "text": "test"}]}]
        level, detail = _grade_impact(affected, "character", {}, {})
        assert level == "minor"

    def test_grade_impact_moderate(self):
        affected = [
            {"matching_paragraphs": [{"index": i, "text": f"para {i}"} for i in range(3)]},
            {"matching_paragraphs": [{"index": 0, "text": "test"}]},
        ]
        level, detail = _grade_impact(affected, "world_setting", {}, {})
        assert level == "moderate"

    def test_grade_impact_severe(self):
        affected = [{"matching_paragraphs": [{"index": i, "text": f"para {i}"} for i in range(10)]} for _ in range(5)]
        level, detail = _grade_impact(affected, "world_setting", {}, {})
        assert level == "severe"


class TestToolContext:
    """Test tool context integration."""

    def test_project_id_contextvar(self):
        from app.agents.tool_context import set_tool_context, reset_tool_context, get_project_id

        assert get_project_id() is None
        tokens = set_tool_context(project_id=42)
        assert get_project_id() == 42
        reset_tool_context(tokens)
        assert get_project_id() is None

    def test_kb_raises_without_project_id(self):
        from app.agents.tools import _kb
        with pytest.raises(ValueError, match="project_id not set"):
            _kb()


class TestPhaseSubsetRelation:
    """验证阶段工具集合满足递进子集关系。"""

    def test_incubation_subset_of_structure(self):
        """孵化阶段的所有工具在结构阶段也应可用。"""
        inc_names = {t.name for t in INCUBATION_TOOLS}
        str_names = {t.name for t in STRUCTURE_TOOLS}
        assert inc_names.issubset(str_names), f"孵化工具不在结构阶段中: {inc_names - str_names}"

    def test_structure_subset_of_writing(self):
        """结构阶段的所有工具在写作阶段也应可用。"""
        str_names = {t.name for t in STRUCTURE_TOOLS}
        wrt_names = {t.name for t in WRITING_TOOLS}
        assert str_names.issubset(wrt_names), f"结构工具不在写作阶段中: {str_names - wrt_names}"

    def test_no_duplicate_tool_names(self):
        """每个阶段内不应有重复工具。"""
        for name, tools in [("INCUBATION", INCUBATION_TOOLS), ("STRUCTURE", STRUCTURE_TOOLS), ("WRITING", WRITING_TOOLS)]:
            names = [t.name for t in tools]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"{name} 有重复工具: {dupes}"


class TestBudgetTrackerEnhancement:
    """BudgetTracker 增强功能测试"""

    def test_llm_tool_tokens_used_default_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        assert tracker.llm_tool_tokens_used == 0

    def test_should_throttle_below_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 7000  # 30% 剩余
        assert not tracker.should_throttle_llm_tool()

    def test_should_throttle_at_threshold(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=10000)
        tracker.used = 8200  # 18% 剩余
        assert tracker.should_throttle_llm_tool()

    def test_should_throttle_max_zero(self):
        from app.agents.agent_context import BudgetTracker
        tracker = BudgetTracker(max_tokens=0)
        assert not tracker.should_throttle_llm_tool()


class TestCostTier:
    """工具元数据分类测试"""

    def test_llm_tools_have_cost_tier(self):
        from app.agents.tools.registry import TOOL_COST_TIER, get_cost_tier
        assert get_cost_tier("review_chapter") == "llm"
        assert get_cost_tier("rewrite_chapter") == "llm"

    def test_rule_tools_have_cost_tier(self):
        from app.agents.tools.registry import get_cost_tier
        for name in ("consistency_scan", "rhythm_analysis", "style_analysis",
                     "foreshadowing_check", "progress_report"):
            assert get_cost_tier(name) == "rule", f"{name} should be rule"

    def test_db_tools_default(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("knowledge_search") == "db"
        assert get_cost_tier("create_character") == "db"
        assert get_cost_tier("generate_chapter_content") == "db"

    def test_unknown_tool_defaults_to_db(self):
        from app.agents.tools.registry import get_cost_tier
        assert get_cost_tier("nonexistent_tool") == "db"


class TestTruncateResult:
    """感知工具输出截短测试"""

    def test_truncate_dict_with_list(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": list(range(10)), "name": "test"}
        result = _truncate_result(data, max_items=3, max_str_len=100)
        # 前3项 + 1项提示
        assert result["items"][:3] == [0, 1, 2]
        assert result["items"][-1] == "... 还有 7 项"
        assert result["name"] == "test"

    def test_truncate_dict_with_long_string(self):
        from app.agents.tools.utils import _truncate_result
        data = {"text": "a" * 200}
        result = _truncate_result(data, max_items=5, max_str_len=50)
        # 截短到 max_str_len 字符 + "..."
        assert result["text"] == "a" * 50 + "..."
        assert result["text"].endswith("...")

    def test_truncate_nested_dict(self):
        from app.agents.tools.utils import _truncate_result
        data = {"outer": {"inner_list": [1, 2, 3, 4, 5], "inner_str": "hello"}}
        result = _truncate_result(data, max_items=2, max_str_len=100)
        assert result["outer"]["inner_list"][:2] == [1, 2]
        assert result["outer"]["inner_str"] == "hello"

    def test_truncate_list_directly(self):
        from app.agents.tools.utils import _truncate_result
        data = [1, 2, 3, 4, 5, 6, 7]
        result = _truncate_result(data, max_items=3, max_str_len=100)
        # 前3项 + 1项提示
        assert result[:3] == [1, 2, 3]
        assert result[-1] == "... 还有 4 项"

    def test_truncate_short_data_unchanged(self):
        from app.agents.tools.utils import _truncate_result
        data = {"items": [1, 2], "name": "hi"}
        result = _truncate_result(data, max_items=5, max_str_len=100)
        assert result == data

    def test_truncate_non_collection_passthrough(self):
        from app.agents.tools.utils import _truncate_result
        assert _truncate_result(42, max_items=5, max_str_len=100) == 42
        assert _truncate_result(None, max_items=5, max_str_len=100) is None


class TestConsistencyScanMerge:
    """consistency_scan 合并后三种模式测试"""

    def _make_mock_kb(self):
        """构建模拟 KB 对象"""
        kb = MagicMock()
        kb.timelines.list_timeline.return_value = [
            {"chapter_number": 1, "summary": "开场", "emotion_tag": "平静", "tension_score": 2},
            {"chapter_number": 2, "summary": "冲突", "emotion_tag": "紧张", "tension_score": 4},
            {"chapter_number": 3, "summary": "转折", "emotion_tag": "绝望", "tension_score": 5},
            {"chapter_number": 4, "summary": "缓和", "emotion_tag": "温馨", "tension_score": 2},
        ]
        kb.characters.list_characters.return_value = [
            {"id": 1, "name": "张三", "role": "主角", "core_motivation": "复仇", "deep_fear": "被遗弃"},
        ]
        kb.world_setting.get.return_value = {
            "tiered_settings": {"red": ["魔法不可逆转"]},
        }
        kb.foreshadowings.list_foreshadowings.return_value = []
        kb.chapters.get_by_number.return_value = {"content": "测试内容"}
        kb.outlines.get_chapter_outline.return_value = {
            "scene": "城市", "characters": "张三", "emotional_arc": "平静→紧张",
        }
        return kb

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_full_returns_issues(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.run(consistency_scan.ainvoke({"mode": "full"}))
        assert "issues" in result
        assert result["mode"] == "full"

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_transition_checks_chapter(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.run(consistency_scan.ainvoke({"mode": "transition", "chapter_number": 2}))
        assert "issues" in result
        assert result["mode"] == "transition"

    @patch("app.agents.tools.perception.consistency_scan._kb")
    def test_mode_compare_checks_cross_analysis(self, mock_kb_fn):
        mock_kb_fn.return_value = self._make_mock_kb()
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.run(consistency_scan.ainvoke({"mode": "compare", "chapter_a": 1, "chapter_b": 2}))
        assert "issues" in result
        assert result["mode"] == "compare"

    def test_mode_invalid_returns_error(self):
        from app.agents.tools.perception.consistency_scan import consistency_scan
        import asyncio
        result = asyncio.run(consistency_scan.ainvoke({"mode": "invalid"}))
        assert "error" in result
