"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 并发控制
    is_busy = Column(Boolean, default=False)
    busy_since = Column(DateTime, nullable=True)
    busy_by = Column(String(20), nullable=True)  # "agent" | "workflow"

    # Relationships
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
    # 人物设定相关
    characters = relationship(
        "Character", back_populates="project", cascade="all, delete-orphan"
    )
    relations = relationship(
        "Relation", back_populates="project", cascade="all, delete-orphan"
    )
    checkpoints = relationship(
        "WorkflowCheckpoint", back_populates="project", cascade="all, delete-orphan"
    )
    volumes = relationship(
        "Volume", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.name}>"
