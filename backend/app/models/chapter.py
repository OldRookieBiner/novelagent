"""Chapter model"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Chapter(Base):
    """Chapter content model"""

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    chapter_outline_id = Column(Integer, ForeignKey("chapter_outlines.id", ondelete="CASCADE"), unique=True, nullable=False)
    content = Column(Text, nullable=True)
    word_count = Column(Integer, default=0)
    review_passed = Column(Boolean, default=False)
    review_feedback = Column(Text, nullable=True)

    # 审核相关
    review_result = Column(JSON, nullable=True)  # {"passed": bool, "scores": dict, "issues": list}
    rewrite_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    chapter_outline = relationship("ChapterOutline", back_populates="chapter")

    def __repr__(self):
        return f"<Chapter id={self.id}>"