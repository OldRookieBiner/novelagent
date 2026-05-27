"""Volume model — 卷

Phase 4 新增字段：
- chapter_offset: 全局章节偏移量（卷内第1章对应全局第chapter_offset+1章）
- character_snapshot: 角色状态快照（卷边界时的角色状态JSON）
- last_block_summary: 上一卷末尾情节块摘要
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Volume(Base):
    """卷模型"""

    __tablename__ = "volumes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    volume_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Phase 4: 超长篇卷管理
    chapter_offset = Column(Integer, default=0, nullable=False)
    character_snapshot = Column(JSON, nullable=True)
    last_block_summary = Column(Text, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="volumes")
    arcs = relationship("Arc", back_populates="volume", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Volume project_id={self.project_id} num={self.volume_number} offset={self.chapter_offset}>"
