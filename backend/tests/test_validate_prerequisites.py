"""validate_prerequisites 函数的单元测试

测试 KnowledgeBaseService.validate_prerequisites() 方法，
通过 mock 各 Store 的返回值来验证前置条件检查逻辑。
"""

import pytest
from unittest.mock import MagicMock, patch

from app.agents.services.knowledge_base import KnowledgeBaseService


@pytest.fixture
def kb():
    """创建 KB 实例并 mock 所有 Store"""
    with patch("app.agents.services.knowledge_base.SessionLocal"):
        kb = KnowledgeBaseService(project_id=1)
        # Mock all stores
        kb.outlines = MagicMock()
        kb.characters = MagicMock()
        kb.world_setting = MagicMock()
        kb.foreshadowings = MagicMock()
        kb.styles = MagicMock()
        kb.plots = MagicMock()
        kb.chapters = MagicMock()
        kb.timelines = MagicMock()
        return kb


def _setup_all_pass(kb):
    """设置所有检查通过"""
    kb.outlines.get_chapter_outline.return_value = {"confirmed": True}
    kb.characters.list_characters.return_value = [{"id": 1, "name": "测试角色"}]
    kb.world_setting.get.return_value = {"id": 1, "core_concept": "测试世界观"}
    kb.foreshadowings.list_foreshadowings.return_value = [{"id": 1, "content": "伏笔"}]
    kb.styles.get_constraints.return_value = {"id": 1, "style_anchor": "测试"}
    kb.plots.list_plot_blocks.return_value = [{"id": 1, "title": "情节块"}]
    kb.chapters.get_by_number.return_value = {"id": 1, "content": "上一章内容"}
    kb.characters.list_relations_with_plans.return_value = [{"id": 1, "plans": [{"id": 1}]}]
    kb.timelines.list_timeline.return_value = [{"id": 1, "summary": "时间线"}]


class TestAllPrerequisitesMet:
    """测试所有前置条件都满足的情况"""

    def test_all_prerequisites_met(self, kb):
        """所有前置条件满足时，blocked 和 warnings 为空"""
        _setup_all_pass(kb)
        result = kb.validate_prerequisites(current_chapter=1)
        assert result["blocked"] == []
        assert result["warnings"] == []
        assert result["validated"] is True


class TestCharacterMissing:
    """测试角色缺失场景"""

    def test_missing_characters_blocked(self, kb):
        """角色缺失时，应加入 blocked"""
        _setup_all_pass(kb)
        kb.characters.list_characters.return_value = []
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(b["type"] == "character_missing" for b in result["blocked"])


class TestOutlineUnconfirmed:
    """测试大纲未确认场景"""

    def test_outline_unconfirmed_blocked(self, kb):
        """大纲未确认时，应加入 blocked"""
        _setup_all_pass(kb)
        kb.outlines.get_chapter_outline.return_value = {"confirmed": False}
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(b["type"] == "outline_unconfirmed" for b in result["blocked"])


class TestOutlineMissing:
    """测试大纲不存在场景"""

    def test_outline_missing_blocked(self, kb):
        """大纲不存在时，应加入 blocked"""
        _setup_all_pass(kb)
        kb.outlines.get_chapter_outline.return_value = None
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(b["type"] == "chapter_outline_missing" for b in result["blocked"])


class TestWorldSettingMissing:
    """测试世界观缺失场景"""

    def test_world_setting_missing_blocked_no_ws(self, kb):
        """世界观不存在时，应加入 blocked"""
        _setup_all_pass(kb)
        kb.world_setting.get.return_value = None
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(b["type"] == "world_setting_missing" for b in result["blocked"])

    def test_world_setting_missing_blocked_empty_core(self, kb):
        """世界观存在但 core_concept 为空时，应加入 blocked"""
        _setup_all_pass(kb)
        kb.world_setting.get.return_value = {"id": 1, "core_concept": ""}
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(b["type"] == "world_setting_missing" for b in result["blocked"])


class TestNoCurrentChapter:
    """测试 current_chapter 为 None 的场景"""

    def test_no_current_chapter_skips_chapter_checks(self, kb):
        """current_chapter 为 None 时，应跳过章节相关检查"""
        _setup_all_pass(kb)
        result = kb.validate_prerequisites(current_chapter=None)
        chapter_types = {"chapter_outline_missing", "outline_unconfirmed", "previous_chapter_empty"}
        assert not any(b["type"] in chapter_types for b in result["blocked"])
        assert not any(w["type"] in chapter_types for w in result["warnings"])


class TestWarnings:
    """测试次要项警告"""

    def test_foreshadowing_empty_warning(self, kb):
        """伏笔为空时，应加入 warnings"""
        _setup_all_pass(kb)
        kb.foreshadowings.list_foreshadowings.return_value = []
        result = kb.validate_prerequisites(current_chapter=1)
        assert any(w["type"] == "foreshadowing_empty" for w in result["warnings"])


class TestErrorIsolation:
    """测试错误隔离"""

    def test_single_check_failure_does_not_affect_others(self, kb):
        """单项查询异常时，不影响其他检查项"""
        _setup_all_pass(kb)
        kb.characters.list_characters.side_effect = Exception("DB error")
        result = kb.validate_prerequisites(current_chapter=1)
        assert result["validated"] is True
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestPreviousChapterEmpty:
    """测试上一章内容为空"""

    def test_previous_chapter_empty_warning(self, kb):
        """上一章没有正文时，应加入 warning"""
        _setup_all_pass(kb)
        kb.chapters.get_by_number.return_value = None
        result = kb.validate_prerequisites(current_chapter=2)
        assert any(w["type"] == "previous_chapter_empty" for w in result["warnings"])
