"""LangGraph checkpointer using PostgreSQL"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Iterator

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.checkpoint import WorkflowCheckpoint


class PostgresCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph checkpoint saver using PostgreSQL.

    用于持久化工作流状态，支持暂停/恢复功能。
    """

    def __init__(self, project_id: int, thread_id: str = "default"):
        self.project_id = project_id
        self.thread_id = thread_id
        self.db: Optional[Session] = None

    def _get_db(self) -> Session:
        """获取数据库会话"""
        if self.db is None:
            self.db = SessionLocal()
        return self.db

    def _close_db(self):
        """关闭数据库会话"""
        if self.db:
            self.db.close()
            self.db = None

    def get_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """
        获取检查点元组。

        Args:
            config: 包含 thread_id 的配置

        Returns:
            CheckpointTuple 或 None
        """
        db = self._get_db()
        try:
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id", self.thread_id)
            checkpoint_id = configurable.get("checkpoint_id")

            query = db.query(WorkflowCheckpoint).filter(
                WorkflowCheckpoint.project_id == self.project_id,
                WorkflowCheckpoint.thread_id == thread_id
            )

            # 如果指定了 checkpoint_id，按 ID 查找
            if checkpoint_id:
                record = query.filter(
                    WorkflowCheckpoint.checkpoint_id == checkpoint_id
                ).first()
            else:
                # 否则获取最新的检查点
                record = query.order_by(WorkflowCheckpoint.updated_at.desc()).first()

            if record:
                return self._record_to_tuple(record, config)
            return None
        finally:
            self._close_db()

    def _record_to_tuple(self, record: WorkflowCheckpoint, config: dict) -> CheckpointTuple:
        """
        将数据库记录转换为 CheckpointTuple。

        Args:
            record: WorkflowCheckpoint 数据库记录
            config: 原始配置

        Returns:
            CheckpointTuple 对象
        """
        configurable = config.get("configurable", {})
        thread_id = configurable.get("thread_id", self.thread_id)
        checkpoint_id = record.checkpoint_id or str(uuid.uuid4())

        # 构建检查点数据，使用 LangGraph 要求的格式
        checkpoint = {
            "v": record.checkpoint.get("v", 3),  # 版本号
            "ts": record.checkpoint.get("ts", datetime.now(timezone.utc).isoformat()),  # 时间戳
            "id": checkpoint_id,  # UUID 字符串
            "channel_values": record.checkpoint.get("channel_values", {}),
            "channel_versions": record.checkpoint.get("channel_versions", {}),
            "versions_seen": record.checkpoint.get("versions_seen", {}),
        }

        # 构建元数据
        metadata = record.checkpoint.get("metadata", {})
        metadata.setdefault("thread_id", thread_id)
        metadata.setdefault("source", "loop")
        metadata.setdefault("step", 0)
        metadata.setdefault("parents", {})

        # 构建返回配置
        result_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
                "checkpoint_id": checkpoint_id
            }
        }

        return CheckpointTuple(
            config=result_config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,  # 简化实现，暂不追踪父检查点
            pending_writes=[]
        )

    def put(self, config: dict, checkpoint: dict, metadata: dict) -> dict:
        """
        保存检查点。

        Args:
            config: 包含 thread_id 的配置
            checkpoint: 检查点数据（字典格式）
            metadata: 元数据

        Returns:
            更新后的配置，包含新的 checkpoint_id
        """
        db = self._get_db()
        try:
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id", self.thread_id)

            # 生成新的 checkpoint_id（UUID）
            checkpoint_id = str(uuid.uuid4())

            # 确保检查点包含必需字段
            checkpoint_data = {
                "v": checkpoint.get("v", 3),
                "ts": checkpoint.get("ts", datetime.now(timezone.utc).isoformat()),
                "id": checkpoint_id,
                "channel_values": checkpoint.get("channel_values", {}),
                "channel_versions": checkpoint.get("channel_versions", {}),
                "versions_seen": checkpoint.get("versions_seen", {}),
                "metadata": metadata
            }

            # 创建新记录（每次保存都创建新记录，支持历史追踪）
            record = WorkflowCheckpoint(
                project_id=self.project_id,
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                checkpoint=checkpoint_data
            )
            db.add(record)
            db.commit()

            # 返回更新后的配置
            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": "",
                    "checkpoint_id": checkpoint_id
                }
            }
        finally:
            self._close_db()

    def list(self, config: dict) -> Iterator[CheckpointTuple]:
        """
        列出所有检查点。

        Args:
            config: 配置

        Returns:
            CheckpointTuple 迭代器
        """
        db = self._get_db()
        try:
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id", self.thread_id)

            records = db.query(WorkflowCheckpoint).filter(
                WorkflowCheckpoint.project_id == self.project_id,
                WorkflowCheckpoint.thread_id == thread_id
            ).order_by(WorkflowCheckpoint.created_at.desc()).all()

            for record in records:
                yield self._record_to_tuple(record, config)
        finally:
            self._close_db()

    def delete(self, config: dict, checkpoint_id: str) -> None:
        """
        删除检查点。

        Args:
            config: 配置
            checkpoint_id: 检查点 ID（UUID 字符串）
        """
        db = self._get_db()
        try:
            db.query(WorkflowCheckpoint).filter(
                WorkflowCheckpoint.checkpoint_id == checkpoint_id
            ).delete()
            db.commit()
        finally:
            self._close_db()


def get_checkpoint_saver(project_id: int, thread_id: str = "default") -> PostgresCheckpointSaver:
    """
    获取检查点保存器实例。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID（默认 "default"）

    Returns:
        PostgresCheckpointSaver 实例
    """
    return PostgresCheckpointSaver(project_id, thread_id)
