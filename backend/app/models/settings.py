"""User settings model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class UserSettings(Base):
    """User settings model"""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    model_provider = Column(String(50), default="deepseek")
    model_name = Column(String(100), default="deepseek-chat")
    api_key_encrypted = Column(Text, nullable=True)
    # Agent 模型选择持久化
    agent_model_config_id = Column(Integer, nullable=True)
    agent_model_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"
