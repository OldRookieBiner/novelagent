"""场景清单模型

每章写完后记录场景描述和在场角色。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON
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
    # 场景描述
    scene_description = Column(Text, nullable=True)
    # 在场角色列表
    characters_present = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="scene_entries")

    def __repr__(self):
        return f"<SceneEntry ch={self.chapter_number}>"
