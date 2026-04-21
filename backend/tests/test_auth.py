"""Tests for authentication utilities"""

import pytest
from app.utils.auth import (
    hash_password,
    verify_password,
    create_session_token,
    verify_session_token,
)
from app.services.crypto import (
    encrypt_api_key,
    decrypt_api_key,
    get_encryption_key,
)


class TestPasswordHashing:
    """Test password hashing functions"""

    def test_hash_password_creates_different_hashes(self):
        """Same password should produce different hashes (salt)"""
        password = "testpassword123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2
        assert hash1.startswith("$2b$")

    def test_verify_password_correct(self):
        """Correct password should verify"""
        password = "testpassword123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should not verify"""
        password = "testpassword123"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_empty(self):
        """Empty password should not verify"""
        password = "testpassword123"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False


class TestSessionTokens:
    """Test session token functions"""

    def test_create_session_token(self):
        """Should create a valid token"""
        user_id = 123
        token = create_session_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_session_token_valid(self):
        """Valid token should return user data"""
        user_id = 456
        token = create_session_token(user_id)

        data = verify_session_token(token)

        assert data is not None
        assert data["user_id"] == user_id

    def test_verify_session_token_invalid(self):
        """Invalid token should return None"""
        result = verify_session_token("invalid_token_here")
        assert result is None

    def test_verify_session_token_tampered(self):
        """Tampered token should return None"""
        user_id = 789
        token = create_session_token(user_id)
        # Tamper with the token
        tampered = token[:-5] + "xxxxx"

        result = verify_session_token(tampered)
        assert result is None


class TestAPIKeyEncryption:
    """测试 API Key 加密功能"""

    def test_encrypt_api_key(self):
        """应该成功加密 API Key"""
        api_key = "sk-test-api-key-12345"
        user_id = 1
        encrypted = encrypt_api_key(api_key, user_id)

        assert isinstance(encrypted, str)
        assert encrypted != api_key
        assert len(encrypted) > len(api_key)

    def test_decrypt_api_key(self):
        """应该正确解密 API Key"""
        api_key = "sk-test-api-key-12345"
        user_id = 1
        encrypted = encrypt_api_key(api_key, user_id)
        decrypted = decrypt_api_key(encrypted, user_id)

        assert decrypted == api_key

    def test_encrypt_different_keys_produce_different_ciphertext(self):
        """不同的 Key 应该产生不同的密文"""
        key1 = "sk-key-1"
        key2 = "sk-key-2"
        user_id = 1

        encrypted1 = encrypt_api_key(key1, user_id)
        encrypted2 = encrypt_api_key(key2, user_id)

        assert encrypted1 != encrypted2

    def test_same_key_produces_different_ciphertext(self):
        """相同的 Key 应该产生不同的密文（随机IV）"""
        api_key = "sk-same-key"
        user_id = 1

        encrypted1 = encrypt_api_key(api_key, user_id)
        encrypted2 = encrypt_api_key(api_key, user_id)

        # Fernet 包含时间戳，所以相同的 Key 产生不同的密文
        assert encrypted1 != encrypted2

    def test_different_user_id_different_ciphertext(self):
        """不同用户的相同 Key 应该产生不同的密文"""
        api_key = "sk-same-key"

        encrypted1 = encrypt_api_key(api_key, 1)
        encrypted2 = encrypt_api_key(api_key, 2)

        # 不同用户使用不同的 Salt，产生不同的密文
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_user_fails(self):
        """使用错误的用户ID解密应该失败"""
        api_key = "sk-test-key"
        encrypted = encrypt_api_key(api_key, 1)
        decrypted = decrypt_api_key(encrypted, 2)

        # 不同用户无法解密
        assert decrypted == ""

    def test_decrypt_empty_string(self):
        """空字符串应该返回空字符串"""
        assert decrypt_api_key("", 1) == ""

    def test_decrypt_invalid_data(self):
        """无效的加密数据应该返回空字符串"""
        result = decrypt_api_key("not-valid-encrypted-data", 1)
        assert result == ""

    def test_get_encryption_key_returns_bytes(self):
        """加密密钥应该是字节类型"""
        key = get_encryption_key(1)

        assert isinstance(key, bytes)
        assert len(key) == 44  # Base64 编码的 32 字节