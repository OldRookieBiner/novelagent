"""世界观设定模型

支持 novelskills 的分级设定：🔴不可违反 / 🟡可突破有代价 / 🟢装饰性
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class WorldSetting(Base):
    """世界观设定"""

    __tablename__ = "world_settings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # 核心理念（一段描述）
    core_concept = Column(Text, nullable=True)
    # 分级设定：{ "red": [...], "yellow": [...], "green": [...] }
    # red = 🔴不可违反, yellow = 🟡可突破有代价, green = 🟢装饰性
    tiered_settings = Column(JSON, default=dict)
    # 关键地点列表
    key_locations = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="world_setting")

    def __repr__(self):
        return f"<WorldSetting project_id={self.project_id}>"
