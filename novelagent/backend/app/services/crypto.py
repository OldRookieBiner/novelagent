"""Encryption utilities for sensitive data"""

import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def get_encryption_key() -> bytes:
    """Derive encryption key from secret key"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'novelagent_salt',  # Fixed salt for consistency
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return key


def encrypt_api_key(api_key: str) -> str:
    """Encrypt an API key"""
    if not api_key:
        return ""

    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt an API key"""
    if not encrypted_key:
        return ""

    try:
        key = get_encryption_key()
        f = Fernet(key)
        encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    except Exception:
        return ""