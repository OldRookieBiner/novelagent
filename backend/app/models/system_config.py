"""System configuration model"""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime

from app.database import Base


class SystemConfig(Base):
    """System-wide configuration key-value store"""
    __tablename__ = "system_config"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemConfig key={self.key}>"
