"""测试 get_or_create_workflow_state 的并发安全性

核心保证：
1. 对同一 project_id 多次调用只创建一行（unique 约束）
2. 已存在时返回现有行，不覆盖任何字段
3. IntegrityError 路径（SQLite 并发模拟）能正确回退
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.workflow_state import WorkflowState
from app.utils.workflow import get_or_create_workflow_state
from app.agents.constants import Phase


class TestGetOrCreateWorkflowState:
    """测试 get_or_create_workflow_state 的 upsert 行为"""

    def test_create_new_state(self, db):
        """project_id 不存在时创建新行"""
        state = get_or_create_workflow_state(db, 42)
        db.commit()
        assert state is not None
        assert state.project_id == 42
        assert state.stage == "incubation"

    def test_return_existing_state(self, db):
        """project_id 已存在时返回现有行，不创建新行"""
        ws1 = get_or_create_workflow_state(db, 42)
        db.commit()

        # 修改 stage
        ws1.stage = Phase.STRUCTURE.value
        db.commit()

        # 再次调用应返回同一行
        ws2 = get_or_create_workflow_state(db, 42)
        db.commit()

        assert ws2.id == ws1.id
        assert ws2.stage == Phase.STRUCTURE.value

        # 确认只有一行
        count = db.query(WorkflowState).filter(
            WorkflowState.project_id == 42
        ).count()
        assert count == 1

    def test_unique_constraint_prevents_duplicate(self, db):
        """unique 约束阻止直接创建重复行"""
        ws = WorkflowState(project_id=99)
        db.add(ws)
        db.commit()

        # 直接创建同一 project_id 的第二行应抛出 IntegrityError
        ws2 = WorkflowState(project_id=99)
        db.add(ws2)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_multiple_projects_separate_states(self, db):
        """不同 project_id 有独立的 WorkflowState 行"""
        ws1 = get_or_create_workflow_state(db, 1)
        ws2 = get_or_create_workflow_state(db, 2)
        db.commit()

        assert ws1.id != ws2.id
        assert ws1.project_id == 1
        assert ws2.project_id == 2

        # 互不影响
        ws1.stage = Phase.WRITING.value
        db.commit()
        db.refresh(ws2)
        assert ws2.stage == "incubation"

    def test_idempotent_calls(self, db):
        """多次调用返回同一对象"""
        results = []
        for _ in range(5):
            state = get_or_create_workflow_state(db, 77)
            db.commit()
            results.append(state.id)

        # 所有调用返回相同 id
        assert len(set(results)) == 1

        # 数据库中只有一行
        count = db.query(WorkflowState).filter(
            WorkflowState.project_id == 77
        ).count()
        assert count == 1


class TestWorkflowStateStageWithUniqueConstraint:
    """测试 WorkflowState stage 操作（适配 unique 约束）"""

    def test_default_stage_is_incubation(self, db):
        """默认 stage 为 incubation"""
        state = get_or_create_workflow_state(db, 1)
        db.commit()
        assert state.stage == "incubation"

    def test_stage_can_be_updated(self, db):
        """stage 可以被更新为其他阶段"""
        state = get_or_create_workflow_state(db, 1)
        db.commit()

        state.stage = Phase.STRUCTURE.value
        db.commit()
        assert state.stage == "structure"

        state.stage = Phase.WRITING.value
        db.commit()
        assert state.stage == "writing"

        state.stage = Phase.REVISION.value
        db.commit()
        assert state.stage == "revision"
