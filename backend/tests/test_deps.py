"""依赖注入工具函数的单元测试"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.settings import UserSettings
from app.utils.deps import get_llm_for_context, get_user_settings_or_raise


class TestGetUserSettingsOrRaise:
    """测试 get_user_settings_or_raise 函数"""

    def test_returns_settings_when_exists(self, db, test_user):
        """当用户设置存在时，应返回 UserSettings 对象"""
        result = get_user_settings_or_raise(test_user, db)

        assert isinstance(result, UserSettings)
        assert result.user_id == test_user.id

    def test_raises_400_when_not_exists(self, db):
        """当用户设置不存在时，应抛出 HTTPException(400)"""
        # 创建一个没有 UserSettings 的用户
        from app.models.user import User
        from app.utils.auth import hash_password

        user = User(username="nosettings", password_hash=hash_password("pass"))
        db.add(user)
        db.commit()
        db.refresh(user)

        with pytest.raises(HTTPException) as exc_info:
            get_user_settings_or_raise(user, db)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "User settings not found"


class TestGetLlmForContext:
    """测试 get_llm_for_context 函数"""

    @patch("app.utils.llm.get_llm_for_user")
    def test_calls_get_llm_for_user_with_config_id(self, mock_get_llm, db, test_user):
        """当请求包含 llm_config_id 时，应传递给 get_llm_for_user"""
        mock_get_llm.return_value = MagicMock()
        mock_request = MagicMock()
        mock_request.llm_config_id = 42

        # 获取用户设置
        user_settings = (
            db.query(UserSettings).filter(UserSettings.user_id == test_user.id).first()
        )

        result = get_llm_for_context(mock_request, test_user, user_settings, db)

        mock_get_llm.assert_called_once_with(
            test_user.id, user_settings, db, 42, mock_request.llm_model_name
        )
        assert result == mock_get_llm.return_value

    @patch("app.utils.llm.get_llm_for_user")
    def test_calls_get_llm_for_user_with_none_request(
        self, mock_get_llm, db, test_user
    ):
        """当请求为 None 时，llm_config_id 应为 None"""
        mock_get_llm.return_value = MagicMock()

        user_settings = (
            db.query(UserSettings).filter(UserSettings.user_id == test_user.id).first()
        )

        result = get_llm_for_context(None, test_user, user_settings, db)

        mock_get_llm.assert_called_once_with(
            test_user.id, user_settings, db, None, None
        )
        assert result == mock_get_llm.return_value
