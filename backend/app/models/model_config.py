"""模型配置数据模型"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class ModelConfig(Base):
    """模型配置模型"""

    __tablename__ = "model_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # 显示名称
    provider = Column(String(50), nullable=False)  # 预设标识或 "custom"
    base_url = Column(String(500), nullable=False)  # API 基础地址
    model_name = Column(String(100), nullable=False)  # 模型名称
    api_key_encrypted = Column(Text, nullable=True)  # 加密的 API Key
    is_enabled = Column(Boolean, default=True)  # 是否启用
    is_default = Column(Boolean, default=False)  # 是否为默认模型
    last_health_check = Column(DateTime, nullable=True)  # 上次健康检查时间
    health_status = Column(String(20), nullable=True)  # healthy / unhealthy / unknown
    health_latency = Column(Integer, nullable=True)  # 延迟毫秒数
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联用户
    user = relationship("User", back_populates="model_configs")

    def __repr__(self):
        return f"<ModelConfig id={self.id} name={self.name} user_id={self.user_id}>"
