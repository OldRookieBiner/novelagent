"""LangGraph checkpointer using PostgreSQL"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Iterator, Union

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.checkpoint import WorkflowCheckpoint


class PostgresCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph checkpoint saver using PostgreSQL.

    用于持久化工作流状态，支持暂停/恢复功能。

    支持外部传入数据库会话，实现会话复用，避免频繁创建/销毁连接。
    """

    def __init__(
        self,
        project_id: int,
        thread_id: str = "default",
        db: Optional[Session] = None
    ):
        """
        初始化检查点保存器。

        Args:
            project_id: 项目 ID
            thread_id: 线程 ID（默认 "default"）
            db: 可选的外部数据库会话，如果提供则复用该会话
        """
        self.project_id = project_id
        self.thread_id = thread_id
        self._external_db = db  # 外部传入的会话
        self._internal_db: Optional[Session] = None  # 内部创建的会话

    def _get_db(self) -> Session:
        """获取数据库会话，优先使用外部会话"""
        if self._external_db is not None:
            return self._external_db
        if self._internal_db is None:
            self._internal_db = SessionLocal()
        return self._internal_db

    def _should_close_db(self) -> bool:
        """判断是否应该关闭会话（仅关闭内部创建的会话）"""
        return self._internal_db is not None

    def _close_db(self):
        """关闭内部数据库会话，不影响外部会话"""
        if self._internal_db:
            self._internal_db.close()
            self._internal_db = None

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


def get_checkpoint_saver(
    project_id: int,
    thread_id: str = "default",
    db: Optional[Session] = None
) -> PostgresCheckpointSaver:
    """
    获取检查点保存器实例。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID（默认 "default"）
        db: 可选的外部数据库会话，用于会话复用

    Returns:
        PostgresCheckpointSaver 实例
    """
    return PostgresCheckpointSaver(project_id, thread_id, db)
