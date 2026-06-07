"""Workflow utilities"""

from sqlalchemy.orm import Session

from app.models.workflow_state import WorkflowState


def get_or_create_workflow_state(
    db: Session, project_id: int
) -> WorkflowState:
    """获取或创建工作流状态

    Args:
        db: 数据库会话
        project_id: 项目 ID

    Returns:
        WorkflowState 实例
    """
    state = (
        db.query(WorkflowState)
        .filter(WorkflowState.project_id == project_id)
        .first()
    )

    if not state:
        state = WorkflowState(project_id=project_id)
        db.add(state)
        db.flush()

    return state
