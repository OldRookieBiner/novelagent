"""伏笔追踪模型

支撑 novelskills 的伏笔分级回收机制：
暗示(hint) -> 强化(strengthened) -> 揭示(revealed)
伏笔至少出现2次（暗示->强化）才能回收。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Foreshadowing(Base):
    """伏笔追踪"""

    __tablename__ = "foreshadowings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    # hint = 暗示, strengthened = 强化, revealed = 揭示
    level = Column(String(20), default="hint")
    # 出现次数（用于判断升级：>=2 且 hint -> strengthened）
    appearance_count = Column(Integer, default=1)
    # active = 活跃, pending_reclaim = 待回收, reclaimed = 已回收
    status = Column(String(20), default="active")
    # 埋设章节
    planted_chapter = Column(Integer, nullable=True)
    # 预期回收章节
    expected_resolve_chapter = Column(Integer, nullable=True)
    # 实际回收章节
    resolved_chapter = Column(Integer, nullable=True)
    # 关联角色
    related_characters = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="foreshadowings")

    def __repr__(self):
        return f"<Foreshadowing '{self.content[:30]}...'>"
