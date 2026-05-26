"""时间线条目模型

每章写完后追加一条，记录事件摘要、因果链、节奏/张力/情感评分。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class TimelineEntry(Base):
    """时间线条目"""

    __tablename__ = "timeline_entries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_number = Column(Integer, nullable=False)
    # 事件摘要
    summary = Column(Text, nullable=True)
    # 因果链
    causal_chain = Column(Text, nullable=True)
    # 节奏评分 1-5
    rhythm_score = Column(Integer, default=3)
    # 张力评分 1-5
    tension_score = Column(Integer, default=3)
    # 情感评分 1-5
    emotion_score = Column(Integer, default=3)
    # 情绪标签（紧张/舒缓/悲伤/温暖/转折/日常）
    emotion_tag = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="timeline_entries")

    def __repr__(self):
        return f"<TimelineEntry ch={self.chapter_number}>"
