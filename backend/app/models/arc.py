"""Arc model — 弧"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Arc(Base):
    """弧模型"""

    __tablename__ = "arcs"

    id = Column(Integer, primary_key=True, index=True)
    volume_id = Column(
        Integer,
        ForeignKey("volumes.id", ondelete="CASCADE"),
        nullable=False,
    )
    arc_number = Column(Integer, nullable=False)  # 全局递增编号（弧1、弧2...跨卷不重置），非卷内编号
    title = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    chapter_count = Column(Integer, nullable=False, default=10)
    outline = Column(Text, nullable=True)                    # 弧纲（详细概要：情节走向、关键事件、角色弧线）
    outline_confirmed = Column(Boolean, default=False)       # 弧纲是否已确认
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    volume = relationship("Volume", back_populates="arcs")
    chapter_outlines = relationship("ChapterOutline", back_populates="arc")

    def __repr__(self):
        return f"<Arc volume_id={self.volume_id} num={self.arc_number}>"
