"""ProjectContextAssembler 集成测试"""
import pytest
from unittest.mock import patch, MagicMock
from app.agents.agent_context import ProjectContextAssembler, build_agent_context
from app.agents.constants import Phase


def _mock_kb():
    """创建模拟 KnowledgeBaseService"""
    kb = MagicMock()
    kb.batch_read_for_context.return_value = {
        "world_setting": {"core_concept": "魔法世界", "tiered_settings": {"red": ["禁止施法"]}, "key_locations": ["王城"]},
        "characters": [{"id": 1, "name": "张三", "role": "主角", "core_motivation": "复仇", "personality": "坚韧"}],
        "relations": [],
        "style_constraints": {"taboo_words": ["不禁"], "forbidden_patterns": [], "abstract_rules": []},
        "outline": {"title": "测试小说", "chapter_count_confirmed": 10, "summary": "测试摘要"},
        "chapter_outlines": [{"chapter_number": 1, "title": "第一章", "plot": "起风了", "scene": "", "characters": "", "conflict": "", "hook": "", "turning_point": "", "transition": "", "ending": "", "opening_state": "", "emotional_arc": "", "key_scenes": [], "pacing_note": "", "target_words": 3000, "confirmed": True}],
        "plot_blocks": [{"id": 1, "title": "第一幕", "chapter_start": 1, "chapter_end": 5, "expected_mood": "紧张"}],
        "plot_questions": [],
        "subplots": [],
        "foreshadowings": [{"id": 1, "content": "伏笔", "planted_chapter": 1, "expected_resolve_chapter": 5, "status": "planted"}],
        "timeline": [{"chapter_number": 1, "summary": "第一章概要", "emotion_tag": "紧张"}],
        "style_snapshots": [],
        "chapters": [{"chapter_number": 1, "title": "第一章", "content": "风起了。" * 100}],
        "changes": [],
        "previous_closing": "风起了。" * 50,
    }
    kb.characters.list_evolution_plans_triggering_at.return_value = []
    kb.validate_prerequisites.return_value = {"blocked": [], "warnings": [], "validated": True}
    return kb


class TestProjectContextAssembler:
    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_includes_previous_text(self, MockKB):
        """WRITING 阶段输出包含 previous_text"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert "project_data" in result
        assert "previous_text" in result
        assert result["previous_text"] != ""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_incubation_phase_no_previous_text(self, MockKB):
        """INCUBATION 阶段前文预算为 0，不加载 previous_text"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.INCUBATION.value,
            current_chapter_number=None,
        )
        assert result.get("previous_text", "") == ""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_output_contains_loaded_keys(self, MockKB):
        """输出包含 loaded_keys 列表"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=1,
        )
        assert "loaded_keys" in result
        assert isinstance(result["loaded_keys"], list)
        assert len(result["loaded_keys"]) > 0

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_revision_phase_includes_all_fields(self, MockKB):
        """REVISION 阶段包含 outline、plot_questions、subplots、style_snapshots"""
        mock_kb = _mock_kb()
        mock_kb.batch_read_for_context.return_value["plot_questions"] = [
            {"id": 1, "question_text": "谁杀了知更鸟", "status": "pending", "chapter_number": 1}
        ]
        mock_kb.batch_read_for_context.return_value["subplots"] = [
            {"id": 1, "title": "暗线", "current_status": "active"}
        ]
        mock_kb.batch_read_for_context.return_value["style_snapshots"] = [
            {"id": 1, "description": "第一段快照"}
        ]
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.REVISION.value,
            current_chapter_number=None,
        )
        project_data = result["project_data"]
        assert "outline" in project_data
        assert "plot_questions" in project_data
        assert "subplots" in project_data
        assert "style_snapshots" in project_data

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_structure_phase_includes_outline(self, MockKB):
        """STRUCTURE 阶段包含完整 outline"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.STRUCTURE.value,
            current_chapter_number=None,
        )
        project_data = result["project_data"]
        assert "outline" in project_data

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_dedup_previous_chapter_closing(self, MockKB):
        """有 previous_text 时自动去重 previous_chapter_closing"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        # previous_text 非空时，project_data 中不应有 previous_chapter_closing
        if result.get("previous_text"):
            assert "previous_chapter_closing" not in result["project_data"]

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_lightweight_mode_small_window(self, MockKB):
        """极小窗口触发轻量模式"""
        mock_kb = _mock_kb()
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=8000,
            phase=Phase.INCUBATION.value,
            current_chapter_number=None,
        )
        assert result.get("_mode") == "lightweight"

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_backward_compat_build_agent_context(self, MockKB):
        """向后兼容函数 build_agent_context 返回旧格式"""
        MockKB.return_value = _mock_kb()
        result = build_agent_context(
            project_id=1,
            phase=Phase.WRITING.value,
            current_chapter_number=1,
            context_window=128000,
        )
        # 旧格式：展平的 dict
        assert isinstance(result, dict)
        assert "_budget_used" in result
        assert "_budget_max" in result
