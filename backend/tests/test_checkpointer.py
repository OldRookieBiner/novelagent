"""Tests for PostgreSQL checkpoint saver"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.agents.checkpointer import PostgresCheckpointSaver, MAX_CHECKPOINTS_PER_PROJECT, CLEANUP_INTERVAL


class TestPostgresCheckpointSaver:
    """Tests for PostgreSQL checkpoint saver"""

    def test_init_with_defaults(self):
        """Should initialize with default values"""
        saver = PostgresCheckpointSaver(project_id=1)
        assert saver.project_id == 1
        assert saver.thread_id == "default"
        assert saver._external_db is None

    def test_init_with_custom_values(self):
        """Should initialize with custom values"""
        mock_db = Mock()
        saver = PostgresCheckpointSaver(
            project_id=2,
            thread_id="custom_thread",
            db=mock_db
        )
        assert saver.project_id == 2
        assert saver.thread_id == "custom_thread"
        assert saver._external_db == mock_db

    def test_get_tuple_no_checkpoint(self):
        """Should return None when no checkpoint exists"""
        saver = PostgresCheckpointSaver(project_id=1)
        config = {"configurable": {"thread_id": "default"}}

        with patch.object(saver, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
            mock_get_db.return_value = mock_db

            result = saver.get_tuple(config)
            assert result is None

    def test_put_creates_checkpoint(self):
        """Should create new checkpoint with proper structure"""
        saver = PostgresCheckpointSaver(project_id=1)
        config = {"configurable": {"thread_id": "default"}}
        checkpoint = {"channel_values": {"stage": "writing"}}
        metadata = {"step": 1}

        with patch.object(saver, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.add = Mock()
            mock_db.commit = Mock()
            mock_get_db.return_value = mock_db

            result = saver.put(config, checkpoint, metadata)

            assert "configurable" in result
            assert "checkpoint_id" in result["configurable"]
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    def test_cleanup_old_checkpoints(self):
        """Should remove old checkpoints exceeding limit"""
        saver = PostgresCheckpointSaver(project_id=1)

        # 创建模拟的检查点列表
        mock_checkpoints = [Mock() for _ in range(MAX_CHECKPOINTS_PER_PROJECT + 5)]

        with patch.object(saver, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_checkpoints
            mock_db.delete = Mock()
            mock_db.commit = Mock()
            mock_get_db.return_value = mock_db

            deleted_count = saver._cleanup_old_checkpoints(mock_db, "default")

            # 应该删除超出限制的数量
            assert deleted_count == 5

    def test_cleanup_keeps_latest_checkpoints(self):
        """Should keep only the latest checkpoints"""
        saver = PostgresCheckpointSaver(project_id=1)

        # 创建检查点，第一个是最新的
        mock_checkpoints = [Mock(id=i) for i in range(25)]

        with patch.object(saver, '_get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_checkpoints
            mock_db.delete = Mock()
            mock_db.commit = Mock()
            mock_get_db.return_value = mock_db

            saver._cleanup_old_checkpoints(mock_db, "default")

            # 验证删除的是较旧的检查点（索引 >= MAX_CHECKPOINTS_PER_PROJECT）
            assert mock_db.delete.call_count == 5

    def test_record_to_tuple_structure(self):
        """Should convert database record to CheckpointTuple correctly"""
        saver = PostgresCheckpointSaver(project_id=1)

        mock_record = Mock()
        mock_record.checkpoint_id = "test-uuid"
        mock_record.checkpoint = {
            "v": 3,
            "ts": "2024-01-01T00:00:00Z",
            "channel_values": {"stage": "writing"},
            "channel_versions": {},
            "versions_seen": {}
        }

        config = {"configurable": {"thread_id": "default"}}
        result = saver._record_to_tuple(mock_record, config)

        assert result is not None
        assert result.config["configurable"]["checkpoint_id"] == "test-uuid"
        assert result.checkpoint["channel_values"]["stage"] == "writing"


class TestCheckpointConstants:
    """Tests for checkpoint configuration constants"""

    def test_max_checkpoints_value(self):
        """Should have reasonable max checkpoints limit"""
        assert MAX_CHECKPOINTS_PER_PROJECT == 20

    def test_cleanup_interval_value(self):
        """Should have reasonable cleanup interval"""
        assert CLEANUP_INTERVAL == 10


class TestGetCheckpointSaver:
    """Tests for get_checkpoint_saver factory function"""

    def test_factory_creates_saver(self):
        """Should create checkpoint saver via factory function"""
        from app.agents.checkpointer import get_checkpoint_saver

        saver = get_checkpoint_saver(project_id=1, thread_id="test")
        assert isinstance(saver, PostgresCheckpointSaver)
        assert saver.project_id == 1
        assert saver.thread_id == "test"

    def test_factory_with_db_session(self):
        """Should pass db session to saver"""
        from app.agents.checkpointer import get_checkpoint_saver

        mock_db = Mock()
        saver = get_checkpoint_saver(project_id=1, db=mock_db)
        assert saver._external_db == mock_db
