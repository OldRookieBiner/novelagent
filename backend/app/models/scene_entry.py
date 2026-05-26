"""场景清单模型

每章写完后记录场景描述和在场角色。
支持多场景：每章可有多个场景条目，按 scene_index 排序。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import relationship

from app.database import Base


class SceneEntry(Base):
    """场景清单条目"""

    __tablename__ = "scene_entries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_number = Column(Integer, nullable=False)
    # 场景序号（一章内可能有多个场景）
    scene_index = Column(Integer, default=1)
    # 场景发生地点
    location = Column(String(200), nullable=True)
    # 场景描述
    scene_description = Column(Text, nullable=True)
    # 在场角色列表
    characters_present = Column(JSON, default=list)
    # 场景氛围
    mood = Column(String(50), nullable=True)
    # 关键事件列表
    key_events = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="scene_entries")

    def __repr__(self):
        return f"<SceneEntry ch={self.chapter_number} scene={self.scene_index}>"
