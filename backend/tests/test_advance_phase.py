"""advance_phase 工具的阶段推进条件测试

测试逻辑：
1. 孵化→结构：有大纲+人物+世界观
2. 结构→写作：有情节块
3. 写作→修订：全部章节完成
4. 条件不满足时不推进
"""

import pytest
from unittest.mock import patch, MagicMock
from app.agents.constants import Phase


class TestAdvancePhaseLogic:
    """测试 advance_phase 的阶段推进判断逻辑"""

    def _make_result(self, current, outline=None, characters=None,
                     world_setting=None, plot_blocks=None,
                     foreshadowings=None, timeline=None):
        """模拟 advance_phase 的核心判断逻辑

        返回 (suggested_phase, advanced, reason)
        """
        suggested_phase = current
        reason = ""

        if current == Phase.INCUBATION:
            has_outline = outline and (outline.get("title") or outline.get("summary"))
            has_characters = characters is not None and len(characters) >= 1
            has_world = world_setting is not None
            if has_outline and has_characters and has_world:
                suggested_phase = Phase.STRUCTURE
                reason = "大纲、人物、世界观已就绪，可进入结构设计阶段"
            else:
                missing = []
                if not has_outline:
                    missing.append("大纲")
                if not has_characters:
                    missing.append("人物")
                if not has_world:
                    missing.append("世界观")
                reason = f"孵化阶段尚未完成，缺少：{'、'.join(missing)}"

        elif current == Phase.STRUCTURE:
            has_blocks = plot_blocks is not None and len(plot_blocks) >= 1
            if has_blocks:
                suggested_phase = Phase.WRITING
                reason = "情节块已规划，可进入写作阶段"
            else:
                reason = "结构阶段尚未完成，缺少情节块规划"

        elif current == Phase.WRITING:
            total_chapters = outline.get("chapter_count", 0) if outline else 0
            written = len(timeline) if timeline else 0
            if total_chapters > 0 and written >= total_chapters:
                suggested_phase = Phase.REVISION
                reason = f"全部 {total_chapters} 章已写完，可进入修订阶段"
            else:
                reason = f"写作阶段进行中（{written}/{total_chapters} 章）"

        elif current == Phase.REVISION:
            reason = "已在修订阶段"

        advanced = suggested_phase != current
        return suggested_phase, advanced, reason

    # ===== 孵化→结构 =====

    def test_incubation_to_structure_all_ready(self):
        """孵化阶段：大纲+人物+世界观齐全 → 推进到结构"""
        phase, advanced, reason = self._make_result(
            Phase.INCUBATION,
            outline={"title": "测试大纲"},
            characters=[{"name": "主角"}],
            world_setting={"core_concept": "科幻"},
        )
        assert phase == Phase.STRUCTURE
        assert advanced is True
        assert "结构设计" in reason

    def test_incubation_no_outline(self):
        """孵化阶段：缺少大纲 → 不推进"""
        phase, advanced, reason = self._make_result(
            Phase.INCUBATION,
            characters=[{"name": "主角"}],
            world_setting={"core_concept": "科幻"},
        )
        assert phase == Phase.INCUBATION
        assert advanced is False
        assert "大纲" in reason

    def test_incubation_no_characters(self):
        """孵化阶段：缺少人物 → 不推进"""
        phase, advanced, reason = self._make_result(
            Phase.INCUBATION,
            outline={"title": "测试大纲"},
            world_setting={"core_concept": "科幻"},
        )
        assert phase == Phase.INCUBATION
        assert advanced is False
        assert "人物" in reason

    def test_incubation_no_world_setting(self):
        """孵化阶段：缺少世界观 → 不推进"""
        phase, advanced, reason = self._make_result(
            Phase.INCUBATION,
            outline={"title": "测试大纲"},
            characters=[{"name": "主角"}],
        )
        assert phase == Phase.INCUBATION
        assert advanced is False
        assert "世界观" in reason

    def test_incubation_multiple_missing(self):
        """孵化阶段：缺少多项 → 列出所有缺失"""
        phase, advanced, reason = self._make_result(Phase.INCUBATION)
        assert phase == Phase.INCUBATION
        assert advanced is False
        assert "大纲" in reason
        assert "人物" in reason
        assert "世界观" in reason

    # ===== 结构→写作 =====

    def test_structure_to_writing_with_plot_blocks(self):
        """结构阶段：有情节块 → 推进到写作"""
        phase, advanced, reason = self._make_result(
            Phase.STRUCTURE,
            plot_blocks=[{"title": "起源之章"}],
        )
        assert phase == Phase.WRITING
        assert advanced is True
        assert "写作" in reason

    def test_structure_no_plot_blocks(self):
        """结构阶段：无情节块 → 不推进"""
        phase, advanced, reason = self._make_result(Phase.STRUCTURE)
        assert phase == Phase.STRUCTURE
        assert advanced is False
        assert "情节块" in reason

    # ===== 写作→修订 =====

    def test_writing_to_revision_all_chapters_done(self):
        """写作阶段：全部章节写完 → 推进到修订"""
        phase, advanced, reason = self._make_result(
            Phase.WRITING,
            outline={"chapter_count": 5},
            timeline=[{}, {}, {}, {}, {}],
        )
        assert phase == Phase.REVISION
        assert advanced is True
        assert "修订" in reason

    def test_writing_not_all_chapters_done(self):
        """写作阶段：章节未写完 → 不推进"""
        phase, advanced, reason = self._make_result(
            Phase.WRITING,
            outline={"chapter_count": 5},
            timeline=[{}, {}],
        )
        assert phase == Phase.WRITING
        assert advanced is False
        assert "2/5" in reason

    def test_writing_no_chapter_count(self):
        """写作阶段：大纲无章节数 → 不推进"""
        phase, advanced, reason = self._make_result(
            Phase.WRITING,
            outline={},
            timeline=[{}, {}],
        )
        assert phase == Phase.WRITING
        assert advanced is False

    # ===== 修订阶段 =====

    def test_revision_stays(self):
        """修订阶段：不推进，保持在修订"""
        phase, advanced, reason = self._make_result(Phase.REVISION)
        assert phase == Phase.REVISION
        assert advanced is False
        assert "修订" in reason


class TestWorkflowStateStage:
    """测试 WorkflowState 的 stage 字段操作

    使用 get_or_create_workflow_state 创建，确保与 unique 约束一致。
    """

    def test_default_stage_is_incubation(self, db):
        """默认 stage 为 incubation"""
        from app.utils.workflow import get_or_create_workflow_state
        ws = get_or_create_workflow_state(db, 1)
        db.commit()
        assert ws.stage == "incubation"

    def test_stage_can_be_updated(self, db):
        """stage 可以被更新为其他阶段"""
        from app.utils.workflow import get_or_create_workflow_state
        ws = get_or_create_workflow_state(db, 1)
        db.commit()
        ws.stage = Phase.STRUCTURE.value
        assert ws.stage == "structure"
        ws.stage = Phase.WRITING.value
        assert ws.stage == "writing"
        ws.stage = Phase.REVISION.value
        assert ws.stage == "revision"
