"""工作流阶段存储"""

import logging
from typing import Optional

from app.agents.services.stores.base import _BaseStore
from app.utils.workflow import get_or_create_workflow_state

logger = logging.getLogger(__name__)


class WorkflowStore(_BaseStore):
    """工作流阶段读写"""

    def get_current_phase(self) -> str:
        """获取当前阶段(无锁读取).

        返回阶段字符串, 如 "incubation".
        不存在时创建默认行(incubation).
        内部调用 get_or_create_workflow_state 复用现有 upsert 逻辑.
        """
        with self.session(readonly=True) as db:
            ws = get_or_create_workflow_state(db, self.project_id)
            return ws.stage

    def advance(
        self,
        direction: str,
        expected_current: str | None = None,
    ) -> dict:
        """推进或回退阶段(带行锁).

        Args:
            direction: "forward" | "backward"
            expected_current: 乐观锁 - 如果不为 None 且与实际阶段不同,
                              返回冲突错误而不写入

        Returns:
            {
                "current_phase": str,       # 变更前阶段
                "new_phase": str,           # 变更后阶段
                "advanced": bool,           # 是否实际发生阶段变更
                "conflict": bool,           # 是否检测到并发冲突
            }
        """
        with self.session() as db:
            ws = get_or_create_workflow_state(db, self.project_id)

            # 获取行锁后确认阶段
            db.refresh(ws, with_for_update=True)
            actual_phase = ws.stage

            if expected_current is not None and actual_phase != expected_current:
                # 并发冲突: rollback 后显式 commit 空事务
                # 原因: self.session() 正常退出时会 db.commit()
                # rollback 后的 commit 是 no-op, 但语义更清晰
                db.rollback()
                db.commit()
                return {
                    "current_phase": actual_phase,
                    "new_phase": actual_phase,
                    "advanced": False,
                    "conflict": True,
                }

            # 计算目标阶段
            current_phase = actual_phase
            if direction == "forward":
                forward_map = {
                    "incubation": "structure",
                    "structure": "writing",
                    "writing": "revision",
                }
                new_phase = forward_map.get(current_phase, current_phase)
            else:
                backward_map = {
                    "writing": "structure",
                    "structure": "incubation",
                }
                new_phase = backward_map.get(current_phase, current_phase)

            if new_phase != current_phase:
                ws.stage = new_phase
                # session 上下文管理器会在正常退出时 commit

            return {
                "current_phase": current_phase,
                "new_phase": new_phase,
                "advanced": new_phase != current_phase,
                "conflict": False,
            }
