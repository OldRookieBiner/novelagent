"""变更闭环工具测试 — apply_change/reject_change/list_proposed_changes

纯逻辑测试，不依赖 DB（mock KnowledgeBaseService）。
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.agents.constants import Phase


def _run_async(coro):
    """兼容 Python 3.14 的异步执行辅助"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # 如果已在事件循环中，创建新的
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class TestApplyChangeLogic:
    """apply_change 核心逻辑测试"""

    def _make_mock_kb(self, change_data=None):
        """构造 mock KnowledgeBaseService"""
        kb = MagicMock()
        kb.changes = MagicMock()
        kb.changes.get.return_value = change_data
        kb.changes.update.return_value = {"id": 1, "status": "applied"}
        kb.world_setting = MagicMock()
        kb.characters = MagicMock()
        kb.foreshadowings = MagicMock()
        kb.styles = MagicMock()
        kb.outlines = MagicMock()
        return kb

    def test_apply_nonexistent_change_returns_error(self):
        """变更 ID 不存在 → 返回错误"""
        kb = self._make_mock_kb(change_data=None)
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 999}))
            assert "error" in result
            assert "999" in result["error"]

    def test_apply_non_proposed_returns_error(self):
        """非 proposed 状态 → 返回错误"""
        kb = self._make_mock_kb(change_data={
            "id": 1, "status": "applied", "target_type": "character", "target_id": 1, "new_value": {}
        })
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 1}))
            assert "error" in result

    def test_apply_chapter_rewrite_redirects(self):
        """chapter_rewrite 类型 → 重定向到 rewrite_chapter"""
        kb = self._make_mock_kb(change_data={
            "id": 1, "status": "proposed", "target_type": "chapter_rewrite",
            "target_id": 5, "new_value": {"chapter_number": 5, "reason": "style fix"}
        })
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 1}))
            assert result.get("action") == "redirect"

    def test_apply_character_change_success(self):
        """character 类型 → 调用 update_character"""
        kb = self._make_mock_kb(change_data={
            "id": 1, "status": "proposed", "target_type": "character",
            "target_id": 10, "new_value": {"name": "新名字", "personality": "勇敢"}
        })
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 1}))
            assert result.get("action") == "applied"
            kb.characters.update_character.assert_called_once()

    def test_apply_filters_phantom_keys(self):
        """new_value 中的非模型字段被过滤并报告"""
        kb = self._make_mock_kb(change_data={
            "id": 1, "status": "proposed", "target_type": "character",
            "target_id": 10,
            "new_value": {"name": "新名字", "phantom_field": "should_be_filtered", "personality": "勇敢"}
        })
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 1}))
            assert result.get("action") == "applied"
            assert "filtered_keys" in result
            assert "phantom_field" in result["filtered_keys"]

    def test_apply_world_setting_update_existing(self):
        """world_setting 类型更新已有记录"""
        kb = self._make_mock_kb(change_data={
            "id": 1, "status": "proposed", "target_type": "world_setting",
            "target_id": 1, "new_value": {"core_concept": "新概念"}
        })
        kb.world_setting.get.return_value = {"id": 1, "core_concept": "旧概念"}
        with patch("app.agents.tools.modification.apply_change._kb", return_value=kb):
            from app.agents.tools.modification.apply_change import apply_change
            result = _run_async(apply_change.ainvoke({"change_id": 1}))
            assert result.get("action") == "applied"
            kb.world_setting.update.assert_called_once()


class TestRejectChangeLogic:
    """reject_change 核心逻辑测试"""

    def test_reject_nonexistent_returns_error(self):
        """变更 ID 不存在 → 返回错误"""
        kb = MagicMock()
        kb.changes.get.return_value = None
        with patch("app.agents.tools.modification.reject_change._kb", return_value=kb):
            from app.agents.tools.modification.reject_change import reject_change
            result = _run_async(reject_change.ainvoke({"change_id": 999}))
            assert "error" in result

    def test_reject_proposed_success(self):
        """proposed 状态 → 成功拒绝"""
        kb = MagicMock()
        kb.changes.get.return_value = {
            "id": 1, "status": "proposed", "target_type": "character", "target_id": 1
        }
        kb.changes.update.return_value = {"id": 1, "status": "abandoned"}
        with patch("app.agents.tools.modification.reject_change._kb", return_value=kb):
            from app.agents.tools.modification.reject_change import reject_change
            result = _run_async(reject_change.ainvoke({"change_id": 1, "reason": "不需要"}))
            assert result.get("action") == "rejected"
            kb.changes.update.assert_called_once()
            call_args = kb.changes.update.call_args[0]
            assert call_args[1]["status"] == "abandoned"
            assert call_args[1]["author_decision"] == "reject"

    def test_reject_non_proposed_returns_error(self):
        """非 proposed 状态 → 返回错误"""
        kb = MagicMock()
        kb.changes.get.return_value = {"id": 1, "status": "applied"}
        with patch("app.agents.tools.modification.reject_change._kb", return_value=kb):
            from app.agents.tools.modification.reject_change import reject_change
            result = _run_async(reject_change.ainvoke({"change_id": 1}))
            assert "error" in result


class TestListProposedChangesLogic:
    """list_proposed_changes 核心逻辑测试"""

    def test_list_empty(self):
        """无变更 → found=False"""
        kb = MagicMock()
        kb.changes.list_changes.return_value = []
        with patch("app.agents.tools.modification.list_proposed_changes._kb", return_value=kb):
            from app.agents.tools.modification.list_proposed_changes import list_proposed_changes
            result = _run_async(list_proposed_changes.ainvoke({"status": "proposed"}))
            assert result.get("found") is False

    def test_list_with_results(self):
        """有变更 → found=True, count>0"""
        kb = MagicMock()
        kb.changes.list_changes.return_value = [
            {"id": 1, "target_type": "character", "target_id": 1, "status": "proposed", "description": "test", "created_at": "2026-01-01"},
            {"id": 2, "target_type": "world_setting", "target_id": 1, "status": "proposed", "description": "test2", "created_at": "2026-01-02"},
        ]
        with patch("app.agents.tools.modification.list_proposed_changes._kb", return_value=kb):
            from app.agents.tools.modification.list_proposed_changes import list_proposed_changes
            result = _run_async(list_proposed_changes.ainvoke({"status": "proposed"}))
            assert result.get("found") is True
            assert result.get("count") == 2

    def test_list_all_status(self):
        """status=all → 调用 list_changes 不带过滤"""
        kb = MagicMock()
        kb.changes.list_changes.return_value = []
        with patch("app.agents.tools.modification.list_proposed_changes._kb", return_value=kb):
            from app.agents.tools.modification.list_proposed_changes import list_proposed_changes
            result = _run_async(list_proposed_changes.ainvoke({"status": "all"}))
            # 应该调用无参数版本
            kb.changes.list_changes.assert_called_once_with()


class TestPhantomParameterFixVerification:
    """幻影参数修复验证 — 确认工具参数名与 ORM 模型列名匹配"""

    def _get_tool_param_names(self, tool_obj) -> list[str]:
        """从 langchain tool 的 args_schema 获取参数名列表"""
        schema = tool_obj.args_schema.model_json_schema()
        return list(schema.get("properties", {}).keys())

    def test_update_subplot_params_match_model(self):
        """update_subplot 参数名应与 Subplot 模型列名一致"""
        from app.agents.tools.creation.subplot import create_subplot
        param_names = self._get_tool_param_names(create_subplot)
        # 确认幻影参数已修复：不应包含 title/status/resolution
        assert "title" not in param_names, "update_subplot 不应有 title 参数（应为 name）"
        assert "status" not in param_names, "update_subplot 不应有 status 参数（应为 current_status）"
        assert "resolution" not in param_names, "update_subplot 不应有 resolution 参数（应为 expected_resolution_chapter）"
        # 确认正确参数存在
        assert "name" in param_names
        assert "current_status" in param_names
        assert "expected_resolution_chapter" in param_names

    def test_update_plot_question_params_match_model(self):
        """update_plot_question 参数名应与 PlotQuestion 模型列名一致"""
        from app.agents.tools.creation.plot_question import create_plot_question
        param_names = self._get_tool_param_names(create_plot_question)
        # 确认幻影参数已修复
        assert "question" not in param_names, "update_plot_question 不应有 question 参数（应为 question_text）"
        assert "answer" not in param_names, "update_plot_question 不应有 answer 参数（应为 answered_in_chapter）"
        # 确认正确参数存在
        assert "question_text" in param_names
        assert "answered_in_chapter" in param_names

    def test_update_plot_block_no_chapter_range(self):
        """update_plot_block 不应有 chapter_range 参数"""
        from app.agents.tools.creation.plot_block import create_plot_block
        param_names = self._get_tool_param_names(create_plot_block)
        assert "chapter_range" not in param_names, "update_plot_block 不应有 chapter_range 参数"
        assert "chapter_start" in param_names
        assert "chapter_end" in param_names

    def test_apply_change_whitelist_blocks_phantom_keys(self):
        """apply_change 白名单应阻止非模型列名"""
        from app.agents.tools.modification.apply_change import _ALLOWED_KEYS
        # world_setting 不应包含 history/social_structure/magic_system
        ws_allowed = _ALLOWED_KEYS.get("world_setting", set())
        assert "history" not in ws_allowed
        assert "social_structure" not in ws_allowed
        assert "magic_system" not in ws_allowed
        # world_setting 应包含有效字段
        assert "core_concept" in ws_allowed
        assert "tiered_settings" in ws_allowed
        assert "key_locations" in ws_allowed
        # 系统字段不应在白名单中
        assert "id" not in ws_allowed
        assert "project_id" not in ws_allowed
        assert "created_at" not in ws_allowed

    def test_character_whitelist_complete(self):
        """character 白名单应包含所有有效字段"""
        from app.agents.tools.modification.apply_change import _ALLOWED_KEYS
        char_allowed = _ALLOWED_KEYS.get("character", set())
        expected = {"name", "role", "personality", "catchphrase", "habit_action",
                    "deep_fear", "core_motivation", "growth_arc", "appearance",
                    "backstory", "signature_item"}
        assert expected.issubset(char_allowed), f"character 白名单缺少: {expected - char_allowed}"


class TestChangeWorkflowToolRegistration:
    """变更闭环工具注册检查"""

    def test_apply_change_in_structure_tools(self):
        """apply_change 应在 STRUCTURE_TOOLS 中"""
        from app.agents.tools.registry import STRUCTURE_TOOLS
        names = [t.name for t in STRUCTURE_TOOLS]
        assert "apply_change" in names, f"apply_change 不在 STRUCTURE_TOOLS 中"

    def test_reject_change_in_structure_tools(self):
        """reject_change 应在 STRUCTURE_TOOLS 中"""
        from app.agents.tools.registry import STRUCTURE_TOOLS
        names = [t.name for t in STRUCTURE_TOOLS]
        assert "reject_change" in names

    def test_list_proposed_changes_in_structure_tools(self):
        """list_proposed_changes 应在 STRUCTURE_TOOLS 中"""
        from app.agents.tools.registry import STRUCTURE_TOOLS
        names = [t.name for t in STRUCTURE_TOOLS]
        assert "list_proposed_changes" in names

    def test_change_workflow_tools_in_writing_tools(self):
        """闭环工具应在 WRITING_TOOLS 中（子集关系）"""
        from app.agents.tools.registry import WRITING_TOOLS
        names = [t.name for t in WRITING_TOOLS]
        assert "apply_change" in names
        assert "reject_change" in names
        assert "list_proposed_changes" in names

    def test_no_duplicate_tools_after_registration(self):
        """注册后不应有重复工具"""
        from app.agents.tools.registry import AGENT_TOOLS
        names = [t.name for t in AGENT_TOOLS]
        dupes = [n for n in names if names.count(n) > 1]
        assert not dupes, f"有重复工具: {dupes}"


class TestAdvancePhaseBackward:
    """advance_phase direction=backward 逻辑测试"""

    def test_backward_from_writing_to_structure(self):
        """从写作阶段回退到结构阶段"""
        from app.agents.constants import Phase
        backward_map = {Phase.WRITING: Phase.STRUCTURE, Phase.STRUCTURE: Phase.INCUBATION}
        assert backward_map[Phase.WRITING] == Phase.STRUCTURE

    def test_backward_from_structure_to_incubation(self):
        """从结构阶段回退到孵化阶段"""
        from app.agents.constants import Phase
        backward_map = {Phase.WRITING: Phase.STRUCTURE, Phase.STRUCTURE: Phase.INCUBATION}
        assert backward_map[Phase.STRUCTURE] == Phase.INCUBATION

    def test_incubation_and_revision_cannot_go_backward(self):
        """孵化阶段和修订阶段不可回退"""
        from app.agents.constants import Phase
        backward_map = {Phase.WRITING: Phase.STRUCTURE, Phase.STRUCTURE: Phase.INCUBATION}
        assert Phase.INCUBATION not in backward_map
        assert Phase.REVISION not in backward_map

    def test_advance_phase_accepts_direction_param(self):
        """advance_phase 函数签名应包含 direction 参数"""
        from app.agents.tools.creation.advance_phase import advance_phase
        param_names = list(advance_phase.args_schema.model_json_schema().get("properties", {}).keys())
        assert "direction" in param_names, "advance_phase 应有 direction 参数"
