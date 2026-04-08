"""Application configuration"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # Database
    database_url: str = "postgresql://novelagent:novelagent@localhost:5432/novelagent"

    # Authentication
    secret_key: str = "your-secret-key-change-in-production"
    default_username: str = "admin"
    default_password: str = "admin123"
    session_expire_seconds: int = 86400 * 7  # 7 days

    # Model defaults
    default_model_provider: str = "deepseek"
    default_api_key: str = ""

    # App settings
    debug: bool = True
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()