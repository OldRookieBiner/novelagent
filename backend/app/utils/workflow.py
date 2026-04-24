"""Workflow utilities"""

from sqlalchemy.orm import Session

from app.models.workflow_state import WorkflowState


def get_or_create_workflow_state(
    db: Session,
    project_id: int,
    thread_id: str = "main"
) -> WorkflowState:
    """获取或创建工作流状态

    Args:
        db: 数据库会话
        project_id: 项目 ID
        thread_id: 工作流线程 ID，默认为 'main'

    Returns:
        WorkflowState 实例
    """
    state = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id,
        WorkflowState.thread_id == thread_id
    ).first()

    if not state:
        state = WorkflowState(project_id=project_id, thread_id=thread_id)
        db.add(state)
        db.flush()

    return state
