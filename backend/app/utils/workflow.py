"""Workflow utilities

核心函数 get_or_create_workflow_state 使用数据库层面的 unique 约束
确保 project_id 唯一性，从根源杜绝并发创建多行 WorkflowState 的问题。

PostgreSQL: 使用 INSERT ... ON CONFLICT DO NOTHING 原子 upsert
SQLite(测试): 使用 query + insert + IntegrityError 回退
"""

import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def _is_postgresql(db: Session) -> bool:
    """判断当前数据库是否为 PostgreSQL"""
    return db.bind.dialect.name == "postgresql"


def get_or_create_workflow_state(
    db: Session, project_id: int
) -> WorkflowState:
    """获取或创建工作流状态（并发安全）

    PostgreSQL: 使用 INSERT ... ON CONFLICT DO NOTHING 原子操作，
    即使并发调用也不会创建多行（project_id unique 约束保证）。
    SQLite: 使用 query + insert + IntegrityError 回退模式
    （SQLite 不支持 ON CONFLICT DO NOTHING 语法）。

    Args:
        db: 数据库会话
        project_id: 项目 ID

    Returns:
        WorkflowState 实例
    """
    if _is_postgresql(db):
        return _upsert_postgresql(db, project_id)
    else:
        return _upsert_sqlite(db, project_id)


def _upsert_postgresql(db: Session, project_id: int) -> WorkflowState:
    """PostgreSQL 原子 upsert: INSERT ... ON CONFLICT DO NOTHING"""
    stmt = pg_insert(WorkflowState).values(
        project_id=project_id,
    ).on_conflict_do_nothing(
        index_elements=['project_id']
    )
    db.execute(stmt)
    db.flush()

    # 冲突或新建后都能查到唯一行
    state = (
        db.query(WorkflowState)
        .filter(WorkflowState.project_id == project_id)
        .first()
    )
    return state


def _upsert_sqlite(db: Session, project_id: int) -> WorkflowState:
    """SQLite 兼容 upsert: query → insert → 捕获 IntegrityError → re-query

    unique 约束保证了即使并发 insert 也只会有一行。
    IntegrityError 是并发写入时的正常路径，回退到 re-query 即可。
    """
    state = (
        db.query(WorkflowState)
        .filter(WorkflowState.project_id == project_id)
        .first()
    )
    if state:
        return state

    # 不存在则创建，unique 约束防止并发重复
    state = WorkflowState(project_id=project_id)
    db.add(state)
    try:
        db.flush()
    except IntegrityError:
        # 并发插入导致唯一约束冲突，回退到查询
        db.rollback()
        state = (
            db.query(WorkflowState)
            .filter(WorkflowState.project_id == project_id)
            .first()
        )

    return state
