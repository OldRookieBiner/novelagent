"""跨卷追踪模型

支撑超长篇（>20万字）的跨卷伏笔、支线和角色变化追踪。

设计原则：
- 跨卷伏笔（CrossVolumeForeshadowing）：从单卷伏笔升级而来，追踪跨多卷的长期伏笔
- 跨卷支线（CrossVolumeSubplot）：从单卷支线升级而来，追踪跨多卷的支线发展
- 角色变化日志（CharacterChangeLog）：记录角色在每卷边界的状态变化
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class CrossVolumeForeshadowing(Base):
    """跨卷伏笔追踪

    当卷过渡时，未回收的伏笔升级为跨卷伏笔，
    追踪其在后续卷中的出现和回收。
    """

    __tablename__ = "cross_volume_foreshadowings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_foreshadowing_id = Column(
        Integer,
        ForeignKey("foreshadowings.id", ondelete="CASCADE"),
        nullable=False,
    )
    appearance_count = Column(Integer, default=1)
    expected_volume = Column(Integer, nullable=True)
    # active = 仍在追踪, resolved = 已回收
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="cross_volume_foreshadowings")
    source_foreshadowing = relationship("Foreshadowing")

    def __repr__(self):
        return f"<CrossVolumeForeshadowing project={self.project_id} fs={self.source_foreshadowing_id} status={self.status}>"


class CrossVolumeSubplot(Base):
    """跨卷支线追踪

    当卷过渡时，未解决的支线升级为跨卷支线，
    追踪其在后续卷中的交汇和解决。
    """

    __tablename__ = "cross_volume_subplots"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_subplot_id = Column(
        Integer,
        ForeignKey("subplots.id", ondelete="CASCADE"),
        nullable=False,
    )
    # active = 仍在追踪, resolved = 已解决
    status = Column(String(50), default="active")
    expected_intersection_volume = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="cross_volume_subplots")
    source_subplot = relationship("Subplot")

    def __repr__(self):
        return f"<CrossVolumeSubplot project={self.project_id} sp={self.source_subplot_id} status={self.status}>"


class CharacterChangeLog(Base):
    """角色变化日志（跨卷）

    记录角色在每卷边界的状态变化，
    用于跨卷角色弧验证和状态跳变检测。
    """

    __tablename__ = "character_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    volume_number = Column(Integer, nullable=False)
    character_id = Column(
        Integer,
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    # {field: {"old": old_value, "new": new_value}}
    changes = Column(JSON, nullable=False)
    chapter_number = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="character_change_logs")
    character = relationship("Character")

    def __repr__(self):
        return f"<CharacterChangeLog project={self.project_id} vol={self.volume_number} char={self.character_id}>"
