"""测试 fetch-models 端点的 config_id 和 api_key 校验逻辑"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端，mock 认证"""
    from app.main import app
    from app.database import get_db
    from app.models.user import User

    mock_user = User(id=1, username="test", created_at="2026-01-01T00:00:00")
    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    def override_get_current_user():
        return mock_user

    from app.utils.auth import get_current_user
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app)

    yield test_client, mock_db, mock_user

    app.dependency_overrides.clear()


class TestFetchModelsApiKeyValidation:
    """fetch-models 端点的 api_key 校验"""

    def test_empty_api_key_no_config_id_returns_error(self, client):
        """空 api_key 且无 config_id → 返回友好错误"""
        test_client, _, _ = client
        resp = test_client.post(
            "/api/model_configs/fetch-models",
            json={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "请输入 API Key"
        assert data["models"] == []

    def test_missing_api_key_no_config_id_returns_error(self, client):
        """不传 api_key 且无 config_id → 返回友好错误"""
        test_client, _, _ = client
        resp = test_client.post(
            "/api/model_configs/fetch-models",
            json={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "请输入 API Key"
        assert data["models"] == []

    def test_config_id_not_found_returns_error(self, client):
        """config_id 不存在 → 回退到 api_key 为空，返回友好错误"""
        test_client, mock_db, _ = client
        # mock 数据库查询返回 None（config 不存在）
        mock_db.query.return_value.filter.return_value.first.return_value = None

        resp = test_client.post(
            "/api/model_configs/fetch-models",
            json={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "config_id": 99999,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "请输入 API Key"
        assert data["models"] == []

    def test_config_id_with_encrypted_key_decrypts_and_uses(self, client):
        """config_id 指向有加密 key 的配置 → 解密后使用，不会因空 key 异常"""
        test_client, mock_db, _ = client

        mock_config = MagicMock()
        mock_config.api_key_encrypted = b"encrypted_data"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        # 验证解密函数被调用
        with patch("app.api.model_configs.decrypt_api_key", return_value="sk-test-key") as mock_decrypt:
            test_client.post(
                "/api/model_configs/fetch-models",
                json={
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "config_id": 1,
                },
            )
            # decrypt_api_key 应被调用，且传入了加密数据
            mock_decrypt.assert_called_once_with(b"encrypted_data", 1)

    def test_whitespace_api_key_returns_error(self, client):
        """api_key 为纯空格 → 返回友好错误"""
        test_client, _, _ = client
        resp = test_client.post(
            "/api/model_configs/fetch-models",
            json={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "api_key": "   ",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "请输入 API Key"
        assert data["models"] == []

    def test_config_id_no_encrypted_key_returns_error(self, client):
        """config_id 指向的配置无 api_key → 回退后仍为空，返回友好错误"""
        test_client, mock_db, _ = client

        # mock 数据库配置没有 api_key
        mock_config = MagicMock()
        mock_config.api_key_encrypted = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        resp = test_client.post(
            "/api/model_configs/fetch-models",
            json={
                "provider": "openai",
                "base_url": "https://api.openai.com/v1",
                "config_id": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] == "请输入 API Key"
        assert data["models"] == []
