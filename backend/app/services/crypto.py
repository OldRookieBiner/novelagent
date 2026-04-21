"""加密工具，用于敏感数据加密"""

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings


def get_encryption_key(user_id: int) -> bytes:
    """
    从密钥和用户ID派生加密密钥
    每个用户使用不同的Salt，增强安全性
    """
    # 使用用户ID作为Salt的一部分，使每个用户的加密密钥不同
    salt = f'novelagent_{user_id}'.encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode()))
    return key


def encrypt_api_key(api_key: str, user_id: int) -> str:
    """
    加密 API Key
    使用用户特定的Salt增强安全性
    """
    if not api_key:
        return ""

    key = get_encryption_key(user_id)
    f = Fernet(key)
    encrypted = f.encrypt(api_key.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_api_key(encrypted_key: str, user_id: int) -> str:
    """
    解密 API Key
    需要提供正确的用户ID以解密
    """
    if not encrypted_key:
        return ""

    try:
        key = get_encryption_key(user_id)
        f = Fernet(key)
        encrypted = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = f.decrypt(encrypted)
        return decrypted.decode()
    except Exception:
        return ""
