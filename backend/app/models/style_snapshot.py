"""风格统计快照模型

每章写完后记录风格指标，用于漂移检测。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class StyleSnapshot(Base):
    """风格统计快照"""

    __tablename__ = "style_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_number = Column(Integer, nullable=False)
    # 段落数
    paragraph_count = Column(Integer, default=0)
    # 平均段落字符数
    avg_paragraph_length = Column(Float, default=0.0)
    # 对话占比 (0.0 - 1.0)
    dialogue_ratio = Column(Float, default=0.0)
    # 平均句长（字符）
    avg_sentence_length = Column(Float, default=0.0)
    # AI 味浓度（FORBIDDEN_WORDS 字符出现率，0.0 - 1.0）
    ai_marker_density = Column(Float, default=0.0)
    # 句长变异性（句长标准差，越大越有变化）
    sentence_variety = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="style_snapshots")

    def __repr__(self):
        return f"<StyleSnapshot ch={self.chapter_number}>"
