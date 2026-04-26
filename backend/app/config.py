"""Application configuration"""

import os
import secrets
import warnings
from pathlib import Path
from pydantic_settings import BaseSettings


def _generate_secret_key() -> str:
    """生成安全的随机密钥"""
    return secrets.token_urlsafe(32)


def _generate_password() -> str:
    """生成安全的随机密码"""
    return secrets.token_urlsafe(12)


def _save_password_to_file(password: str) -> Path:
    """将生成的密码保存到文件，仅首次启动时创建"""
    password_file = Path("/tmp/novelagent_admin_password.txt")
    if not password_file.exists():
        password_file.write_text(password)
        password_file.chmod(0o600)  # 仅所有者可读写
    return password_file


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql://novelagent:novelagent@localhost:5432/novelagent"

    # Authentication
    # If not set, a random key is generated (invalidates sessions on restart)
    secret_key: str = ""
    # Default credentials - if not set, random ones are generated
    default_username: str = ""
    default_password: str = ""
    session_expire_seconds: int = 86400 * 7  # 7 days

    # Model defaults
    default_model_provider: str = "deepseek"
    default_api_key: str = ""

    # App settings
    debug: bool = False  # Secure by default
    log_level: str = "INFO"  # Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:3001"]

    # Rate limiting
    auth_rate_limit_requests: int = 5
    auth_rate_limit_seconds: int = 60

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Generate secret key if not provided
        if not self.secret_key:
            self.secret_key = _generate_secret_key()
            if self.debug:
                warnings.warn(
                    "SECRET_KEY not set. Using random key. Sessions will be invalidated on restart. "
                    "Set SECRET_KEY environment variable for production.",
                    UserWarning
                )

        # Generate default credentials if not provided
        if not self.default_username:
            self.default_username = "admin"
        if not self.default_password:
            self.default_password = _generate_password()
            # 将密码保存到文件而非打印到日志
            password_file = _save_password_to_file(self.default_password)
            warnings.warn(
                f"DEFAULT_PASSWORD not set. Generated random password saved to: {password_file} "
                "Set DEFAULT_PASSWORD environment variable for production.",
                UserWarning
            )


settings = Settings()