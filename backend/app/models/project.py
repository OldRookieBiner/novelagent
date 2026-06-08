"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """Project model - 小说项目"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(100), nullable=False)
    novel_length = Column(Integer, default=100000)  # 小说目标字数
    target_words = Column(Integer, default=100000)  # 保留向后兼容
    total_words = Column(Integer, default=0)

    # 故事种子（创意孵化阶段生成）
    story_seed = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 并发控制
    is_busy = Column(Boolean, default=False)
    busy_since = Column(DateTime, nullable=True)
    busy_by = Column(String(20), nullable=True)  # "agent" | "workflow"

    # Relationships — 基础
    user = relationship("User", back_populates="projects")
    outline = relationship(
        "Outline", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    chapter_outlines = relationship(
        "ChapterOutline", back_populates="project", cascade="all, delete-orphan"
    )
    workflow_states = relationship(
        "WorkflowState", back_populates="project", cascade="all, delete-orphan"
    )
    # 人物设定
    characters = relationship(
        "Character", back_populates="project", cascade="all, delete-orphan"
    )
    relations = relationship(
        "Relation", back_populates="project", cascade="all, delete-orphan"
    )
    volumes = relationship(
        "Volume", back_populates="project", cascade="all, delete-orphan"
    )

    # Relationships — 创作智能体追踪模型
    world_setting = relationship(
        "WorldSetting", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    style_constraints = relationship(
        "StyleConstraints", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    plot_blocks = relationship(
        "PlotBlock", back_populates="project", cascade="all, delete-orphan"
    )
    plot_questions = relationship(
        "PlotQuestion", back_populates="project", cascade="all, delete-orphan"
    )
    subplots = relationship(
        "Subplot", back_populates="project", cascade="all, delete-orphan"
    )
    foreshadowings = relationship(
        "Foreshadowing", back_populates="project", cascade="all, delete-orphan"
    )
    timeline_entries = relationship(
        "TimelineEntry", back_populates="project", cascade="all, delete-orphan"
    )
    style_snapshots = relationship(
        "StyleSnapshot", back_populates="project", cascade="all, delete-orphan"
    )
    scene_entries = relationship(
        "SceneEntry", back_populates="project", cascade="all, delete-orphan"
    )
    setting_changes = relationship(
        "SettingChange", back_populates="project", cascade="all, delete-orphan"
    )

    # Relationships — 跨卷追踪模型（Phase 4）
    cross_volume_foreshadowings = relationship(
        "CrossVolumeForeshadowing", back_populates="project", cascade="all, delete-orphan"
    )
    cross_volume_subplots = relationship(
        "CrossVolumeSubplot", back_populates="project", cascade="all, delete-orphan"
    )
    character_change_logs = relationship(
        "CharacterChangeLog", back_populates="project", cascade="all, delete-orphan"
    )

    # Relationships — Agent 对话
    agent_conversation = relationship(
        "AgentConversation", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.name}>"
