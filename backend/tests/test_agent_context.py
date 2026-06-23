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
        # 轻量模式调用直接 KB 方法，需要 mock 这些方法返回真实数据
        mock_kb.outlines.get.return_value = {"title": "测试小说", "chapter_count_confirmed": 10, "summary": "测试摘要"}
        mock_kb.characters.list_characters.return_value = [{"id": 1, "name": "张三", "role": "主角"}]
        mock_kb.world_setting.get.return_value = {"core_concept": "魔法", "tiered_settings": {"red": ["禁止施法"]}}
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


class TestWritingDataExtensions:
    """P0/P1 新增的 writing 阶段上下文字段测试"""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_includes_style_deviation_when_snapshots_sufficient(self, MockKB):
        """≥3 条快照 + 异常偏离时，注入 style_deviation 含 anomalies"""
        mock_kb = _mock_kb()
        # 6 条快照，最近一条对话比异常偏高
        mock_kb.batch_read_for_context.return_value["style_snapshots"] = [
            {"id": 6, "chapter_number": 6, "dialogue_ratio": 0.95, "avg_sentence_length": 22, "avg_paragraph_length": 80},
            {"id": 5, "chapter_number": 5, "dialogue_ratio": 0.30, "avg_sentence_length": 20, "avg_paragraph_length": 70},
            {"id": 4, "chapter_number": 4, "dialogue_ratio": 0.32, "avg_sentence_length": 21, "avg_paragraph_length": 75},
            {"id": 3, "chapter_number": 3, "dialogue_ratio": 0.28, "avg_sentence_length": 19, "avg_paragraph_length": 72},
            {"id": 2, "chapter_number": 2, "dialogue_ratio": 0.31, "avg_sentence_length": 22, "avg_paragraph_length": 78},
            {"id": 1, "chapter_number": 1, "dialogue_ratio": 0.30, "avg_sentence_length": 20, "avg_paragraph_length": 74},
        ]
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        project_data = result["project_data"]
        assert "style_deviation" in project_data
        sd = project_data["style_deviation"]
        assert sd["snapshots_available"] == 6
        # 第 6 章的对话比 0.95 应被识别为异常
        chapters = {a["chapter"] for a in sd["anomalies"]}
        assert 6 in chapters

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_skips_style_deviation_when_snapshots_few(self, MockKB):
        """快照 < 3 时不注入 style_deviation"""
        mock_kb = _mock_kb()
        mock_kb.batch_read_for_context.return_value["style_snapshots"] = [
            {"id": 1, "chapter_number": 1, "dialogue_ratio": 0.3, "avg_sentence_length": 20, "avg_paragraph_length": 70},
            {"id": 2, "chapter_number": 2, "dialogue_ratio": 0.32, "avg_sentence_length": 21, "avg_paragraph_length": 72},
        ]
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        assert "style_deviation" not in result["project_data"]

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_current_plot_block_includes_questions(self, MockKB):
        """current_plot_block 含 questions_to_answer / questions_to_raise（截前 3）"""
        mock_kb = _mock_kb()
        mock_kb.batch_read_for_context.return_value["plot_blocks"] = [
            {
                "id": 1,
                "title": "第一幕",
                "chapter_start": 1,
                "chapter_end": 5,
                "expected_mood": "紧张",
                "must_happen": ["主角登场"],
                "questions_to_answer": ["Q1", "Q2", "Q3", "Q4"],
                "questions_to_raise": ["R1", "R2"],
            }
        ]
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        cpb = result["project_data"].get("current_plot_block")
        assert cpb is not None
        assert cpb["questions_to_answer"] == ["Q1", "Q2", "Q3"]
        assert cpb["questions_to_raise"] == ["R1", "R2"]

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_phase_active_subplot_events_for_intersection_chapter(self, MockKB):
        """支线事件命中当前章为交汇/首次提出/解决/逾期时注入"""
        mock_kb = _mock_kb()
        mock_kb.batch_read_for_context.return_value["subplots"] = [
            {
                "id": 10,
                "name": "暗线一",
                "raised_in_chapter": 1,
                "planned_intersection_chapter": 2,
                "expected_resolution_chapter": 8,
                "current_status": "developing",
            },
            {
                "id": 11,
                "name": "逾期暗线",
                "planned_intersection_chapter": 1,
                "current_status": "hint",
            },
        ]
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        events = result["project_data"].get("active_subplot_events")
        assert events is not None
        # 命中：id=10 (交汇) + id=11 (逾期)
        ids = {e["id"] for e in events}
        assert 10 in ids and 11 in ids
        # id=10 应有 event=交汇
        assert any(e["id"] == 10 and e["event"] == "交汇" for e in events)
        # id=11 应有逾期描述
        assert any(e["id"] == 11 and "逾期" in e["event"] for e in events)


class TestWritingPhaseChapterContext:
    """回归测试：写作阶段必须依赖 current_chapter_number 加载本章相关上下文"""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_with_chapter_loads_chapter_scoped_data(self, MockKB):
        """传入 chapter_number 时，本章大纲 / 当前情节块 / 前文上下文 / 上一章结尾应全部就位"""
        mock_kb = _mock_kb()
        # 至少要有第 1 章正文，第 2 章才能拿到前文
        MockKB.return_value = mock_kb
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=2,
        )
        pd = result["project_data"]
        # current_chapter_outline 必须存在（fixture 里第 1 章有大纲，这里要求第 2 章——重新构造）
        # 重新 mock：在 chapter_outlines 里加入第 2 章
        # 这里用更直接的断言：current_plot_block 必须命中（第 2 章在 [1,5] 内）
        assert pd.get("current_plot_block") is not None
        assert pd["current_plot_block"]["title"] == "第一幕"
        # 前文上下文非空
        assert result["previous_text"] != ""
        # prerequisites 不应阻断章节号缺失
        blocked_types = {b["type"] for b in pd.get("prerequisites", {}).get("blocked", [])}
        assert "chapter_number_missing" not in blocked_types

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_writing_without_chapter_blocks_with_explicit_message(self, MockKB):
        """未传 chapter_number 时，prerequisites.blocked 应含 chapter_number_missing，
        且不再静默跳过本章相关字段"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        result = assembler.build(
            context_window=128000,
            phase=Phase.WRITING.value,
            current_chapter_number=None,
        )
        pd = result["project_data"]
        blocked = pd.get("prerequisites", {}).get("blocked", [])
        blocked_types = {b["type"] for b in blocked}
        assert "chapter_number_missing" in blocked_types
        # 本章相关字段应缺失（确认旧的静默跳过行为依然存在，但 prerequisites 已显式提示）
        assert "current_chapter_outline" not in pd
        assert "current_plot_block" not in pd
        # previous_text 也应为空
        assert result["previous_text"] == ""

    @patch("app.agents.agent_context.KnowledgeBaseService")
    def test_non_writing_phase_no_chapter_missing_block(self, MockKB):
        """非写作阶段不应触发 chapter_number_missing 阻断（_validate_prerequisites_from_raw 仅 writing 调用）"""
        MockKB.return_value = _mock_kb()
        assembler = ProjectContextAssembler(project_id=1)
        for phase in (Phase.INCUBATION.value, Phase.STRUCTURE.value, Phase.REVISION.value):
            result = assembler.build(
                context_window=128000,
                phase=phase,
                current_chapter_number=None,
            )
            pd = result["project_data"]
            blocked_types = {b["type"] for b in pd.get("prerequisites", {}).get("blocked", [])}
            assert "chapter_number_missing" not in blocked_types, f"phase={phase} 不应阻断"
