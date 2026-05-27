"""Unit tests for cognitive tools (agent_tools.py)

Tests tool registration, helper functions, and impact grading.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.agent_tools import (
    knowledge_search,
    foreshadowing_check,
    consistency_check,
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

    def test_writing_tools_has_13_tools(self):
        assert len(WRITING_TOOLS) == 13

    def test_incubation_tools_subset(self):
        assert len(INCUBATION_TOOLS) == 3
        assert knowledge_search in INCUBATION_TOOLS

    def test_structure_tools_subset(self):
        assert len(STRUCTURE_TOOLS) == 6
        assert propose_outline_adjustment in STRUCTURE_TOOLS

    def test_all_tools_have_names(self):
        for tool in AGENT_TOOLS:
            assert tool.name, f"Tool {tool} missing name"
            assert tool.description, f"Tool {tool.name} missing description"

    def test_perception_tools_are_present(self):
        names = [t.name for t in WRITING_TOOLS]
        for expected in ["knowledge_search", "foreshadowing_check", "consistency_check",
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
        from app.agents.agent_tools import _kb
        with pytest.raises(ValueError, match="project_id not set"):
            _kb()
