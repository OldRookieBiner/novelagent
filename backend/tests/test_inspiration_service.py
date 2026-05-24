# backend/tests/test_inspiration_service.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from app.agents.services.inspiration_service import (
    read_inspiration_brief,
    update_inspiration_brief,
)


class TestReadInspirationBrief:
    @pytest.mark.asyncio
    async def test_read_returns_template_when_outline_exists(self):
        """读取已存在的灵感简报"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = "# 灵感简报\n写作风格：古风"
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await read_inspiration_brief(db, project_id=1)

        assert result["inspiration_template"] == "# 灵感简报\n写作风格：古风"

    @pytest.mark.asyncio
    async def test_read_returns_empty_string_when_template_is_none(self):
        """灵感简报为空时返回空字符串"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = None
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await read_inspiration_brief(db, project_id=1)

        assert result["inspiration_template"] == ""

    @pytest.mark.asyncio
    async def test_read_returns_error_when_outline_missing(self):
        """大纲不存在时返回错误"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = await read_inspiration_brief(db, project_id=1)

        assert "error" in result


class TestUpdateInspirationBrief:
    @pytest.mark.asyncio
    async def test_update_creates_new_brief(self):
        """首次创建灵感简报"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = None
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await update_inspiration_brief(db, project_id=1, brief="# 新简报")

        assert result["success"] is True
        assert "灵感简报已创建" in result["changes"]
        assert mock_outline.inspiration_template == "# 新简报"
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_modifies_existing_brief(self):
        """更新已有灵感简报"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = "# 旧简报"
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await update_inspiration_brief(db, project_id=1, brief="# 新简报")

        assert result["success"] is True
        assert "灵感简报已更新" in result["changes"]
        assert mock_outline.inspiration_template == "# 新简报"

    @pytest.mark.asyncio
    async def test_update_no_change_when_same_content(self):
        """内容相同时不触发更新"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = "# 简报"
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await update_inspiration_brief(db, project_id=1, brief="# 简报")

        assert result["success"] is True
        assert result["changes"] == []
        db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_clears_brief_with_empty_string(self):
        """传空字符串清空简报"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = "# 旧简报"
        db.query.return_value.filter.return_value.first.return_value = mock_outline

        result = await update_inspiration_brief(db, project_id=1, brief="")

        assert result["success"] is True
        assert "灵感简报已清空" in result["changes"]
        assert mock_outline.inspiration_template == ""

    @pytest.mark.asyncio
    async def test_update_returns_error_when_outline_missing(self):
        """大纲不存在时返回错误"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        result = await update_inspiration_brief(db, project_id=1, brief="# 简报")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_rolls_back_on_commit_failure(self):
        """commit 失败时回滚并返回错误"""
        db = MagicMock()
        mock_outline = MagicMock()
        mock_outline.inspiration_template = None
        db.query.return_value.filter.return_value.first.return_value = mock_outline
        db.commit.side_effect = Exception("DB error")

        result = await update_inspiration_brief(db, project_id=1, brief="# 简报")

        assert "error" in result
        db.rollback.assert_called_once()
