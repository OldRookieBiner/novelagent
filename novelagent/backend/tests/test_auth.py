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
    """Test API key encryption functions"""

    def test_encrypt_api_key(self):
        """Should encrypt API key"""
        api_key = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(api_key)

        assert isinstance(encrypted, str)
        assert encrypted != api_key
        assert len(encrypted) > len(api_key)

    def test_decrypt_api_key(self):
        """Should decrypt API key correctly"""
        api_key = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(api_key)
        decrypted = decrypt_api_key(encrypted)

        assert decrypted == api_key

    def test_encrypt_different_keys_produce_different_ciphertext(self):
        """Different keys should produce different ciphertext"""
        key1 = "sk-key-1"
        key2 = "sk-key-2"

        encrypted1 = encrypt_api_key(key1)
        encrypted2 = encrypt_api_key(key2)

        assert encrypted1 != encrypted2

    def test_same_key_produces_different_ciphertext(self):
        """Same key should produce different ciphertext (random IV)"""
        api_key = "sk-same-key"

        encrypted1 = encrypt_api_key(api_key)
        encrypted2 = encrypt_api_key(api_key)

        # Fernet includes timestamp, so same key produces different ciphertext
        assert encrypted1 != encrypted2

    def test_decrypt_empty_string(self):
        """Empty string should return empty string"""
        assert decrypt_api_key("") == ""

    def test_decrypt_invalid_data(self):
        """Invalid encrypted data should return empty string"""
        result = decrypt_api_key("not-valid-encrypted-data")
        assert result == ""

    def test_get_encryption_key_returns_bytes(self):
        """Encryption key should be bytes"""
        key = get_encryption_key()

        assert isinstance(key, bytes)
        assert len(key) == 44  # Base64 encoded 32 bytes