"""LangGraph checkpointer using PostgreSQL"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional, Iterator
from sqlalchemy import and_

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.checkpoint import WorkflowCheckpoint
from app.utils.logger import get_logger

logger = get_logger(__name__)


# 检查点保留策略配置
MAX_CHECKPOINTS_PER_PROJECT = 20  # 每个项目保留的最大检查点数
CLEANUP_INTERVAL = 10  # 每保存 N 个检查点后执行一次清理


class PostgresCheckpointSaver(BaseCheckpointSaver):
    """
    LangGraph checkpoint saver using PostgreSQL.

    用于持久化工作流状态，支持暂停/恢复功能。

    每次 get/put 操作都创建独立的数据库会话，操作完成后立即关闭。
    避免与其他组件（LangGraph 节点、API 端点）共享会话导致并发冲突。
    """

    def __init__(
        self, project_id: int, thread_id: str = "default"
    ):
        """
        初始化检查点保存器。

        Args:
            project_id: 项目 ID
            thread_id: 线程 ID（默认 "default"）
        """
        self.project_id = project_id
        self.thread_id = thread_id
        self._put_count = 0  # 记录保存次数，用于定期清理

    def _get_db(self) -> Session:
        """每次操作创建独立的数据库会话"""
        db = SessionLocal()
        logger.debug(
            "Checkpointer: created DB session for project %s",
            self.project_id,
        )
        return db

    def _close_db(self, db: Session):
        """关闭数据库会话"""
        if db:
            logger.debug(
                "Checkpointer: closing DB session for project %s",
                self.project_id,
            )
            db.close()

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
                WorkflowCheckpoint.thread_id == thread_id,
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
            self._close_db(db)

    def _record_to_tuple(
        self, record: WorkflowCheckpoint, config: dict
    ) -> CheckpointTuple:
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
            "ts": record.checkpoint.get(
                "ts", datetime.now(timezone.utc).isoformat()
            ),  # 时间戳
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
                "checkpoint_id": checkpoint_id,
            }
        }

        return CheckpointTuple(
            config=result_config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,  # 简化实现，暂不追踪父检查点
            pending_writes=[],
        )

    def put(self, config: dict, checkpoint: dict, metadata: dict, new_versions: dict = None) -> dict:
        """
        保存检查点（自动清理旧记录）

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
                "metadata": metadata,
            }

            # 创建新记录
            record = WorkflowCheckpoint(
                project_id=self.project_id,
                thread_id=thread_id,
                checkpoint_id=checkpoint_id,
                checkpoint=checkpoint_data,
            )
            db.add(record)
            db.commit()
            logger.debug(
                f"Checkpoint saved: project_id={self.project_id}, thread_id={thread_id}, checkpoint_id={checkpoint_id}"
            )

            # 定期清理旧检查点
            self._put_count += 1
            if self._put_count % CLEANUP_INTERVAL == 0:
                self._cleanup_old_checkpoints(db, thread_id)

            # 返回更新后的配置
            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": "",
                    "checkpoint_id": checkpoint_id,
                }
            }
        finally:
            self._close_db(db)

    def _cleanup_old_checkpoints(self, db: Session, thread_id: str) -> int:
        """
        清理旧检查点（内部方法）

        Args:
            db: 数据库会话
            thread_id: 线程 ID

        Returns:
            删除的记录数
        """
        # 获取该组合的所有记录，按创建时间倒序
        all_checkpoints = (
            db.query(WorkflowCheckpoint)
            .filter(
                and_(
                    WorkflowCheckpoint.project_id == self.project_id,
                    WorkflowCheckpoint.thread_id == thread_id,
                )
            )
            .order_by(WorkflowCheckpoint.created_at.desc())
            .all()
        )

        deleted_count = 0

        # 如果超过保留数量，删除旧的
        if len(all_checkpoints) > MAX_CHECKPOINTS_PER_PROJECT:
            to_delete = all_checkpoints[MAX_CHECKPOINTS_PER_PROJECT:]
            for checkpoint in to_delete:
                db.delete(checkpoint)
            deleted_count = len(to_delete)
            db.commit()
            logger.info(
                f"Cleaned up {deleted_count} old checkpoints for project_id={self.project_id}, thread_id={thread_id}"
            )

        return deleted_count

    async def aget_tuple(self, config: dict) -> Optional[CheckpointTuple]:
        """异步获取检查点（LangGraph v1 要求）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.get_tuple, config)

    async def aput(self, config: dict, checkpoint: dict, metadata: dict, new_versions: dict = None) -> dict:
        """异步保存检查点（LangGraph v1 要求，new_versions 为 channel 版本号）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.put, config, checkpoint, metadata, new_versions)

    def list(self, config: dict) -> Iterator[CheckpointTuple]:
        """
        列出所有检查点。

        注意：使用 eager loading（.all()）而非 yield + lazy session，
        确保在生成器返回前所有数据已从 DB 加载，避免 session 提前关闭
        导致的 DetachedInstanceError。

        Args:
            config: 配置

        Returns:
            CheckpointTuple 迭代器
        """
        db = self._get_db()
        try:
            configurable = config.get("configurable", {})
            thread_id = configurable.get("thread_id", self.thread_id)

            records = (
                db.query(WorkflowCheckpoint)
                .filter(
                    WorkflowCheckpoint.project_id == self.project_id,
                    WorkflowCheckpoint.thread_id == thread_id,
                )
                .order_by(WorkflowCheckpoint.created_at.desc())
                .all()
            )

            # Eagerly convert all records to tuples before closing session
            tuples = [self._record_to_tuple(record, config) for record in records]
        finally:
            self._close_db(db)

        for t in tuples:
            yield t

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
            self._close_db(db)

    def cleanup_old_checkpoints(self, keep_latest: int = 10) -> int:
        """
        清理旧检查点，保留最新的 N 个记录

        防止检查点表无限增长。每次 put 操作后可调用此方法。

        Args:
            keep_latest: 每个 project_id + thread_id 组合保留的检查点数量

        Returns:
            删除的记录数
        """
        db = self._get_db()
        try:
            # 获取需要清理的项目/线程组合
            from sqlalchemy import and_

            # 对每个超标的组合，删除旧的记录
            deleted_count = 0

            # 获取所有 project_id + thread_id 组合
            combinations = (
                db.query(WorkflowCheckpoint.project_id, WorkflowCheckpoint.thread_id)
                .distinct()
                .all()
            )

            for project_id, thread_id in combinations:
                # 获取该组合的所有记录，按创建时间倒序
                all_checkpoints = (
                    db.query(WorkflowCheckpoint)
                    .filter(
                        and_(
                            WorkflowCheckpoint.project_id == project_id,
                            WorkflowCheckpoint.thread_id == thread_id,
                        )
                    )
                    .order_by(WorkflowCheckpoint.created_at.desc())
                    .all()
                )

                # 如果超过保留数量，删除旧的
                if len(all_checkpoints) > keep_latest:
                    to_delete = all_checkpoints[keep_latest:]
                    for checkpoint in to_delete:
                        db.delete(checkpoint)
                    deleted_count += len(to_delete)

            if deleted_count > 0:
                db.commit()

            return deleted_count
        finally:
            self._close_db(db)


def get_checkpoint_saver(
    project_id: int, thread_id: str = "default"
) -> PostgresCheckpointSaver:
    """
    获取检查点保存器实例。

    Args:
        project_id: 项目 ID
        thread_id: 线程 ID（默认 "default"）

    Returns:
        PostgresCheckpointSaver 实例
    """
    return PostgresCheckpointSaver(project_id, thread_id)
