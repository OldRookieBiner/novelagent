"""Project model"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Project(Base):
    """Project model"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    stage = Column(String(50), default="inspiration_collecting")  # inspiration_collecting, outline_generating, chapter_writing, completed, paused
    target_words = Column(Integer, default=100000)
    total_words = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 审核设置
    review_mode = Column(String(20), default="off", nullable=False)  # off/manual/auto
    max_rewrite_count = Column(Integer, default=3, nullable=False)

    # 工作流模式设置
    workflow_mode = Column(String(20), default="hybrid", nullable=False)  # step_by_step | hybrid | auto

    # Relationships
    user = relationship("User", back_populates="projects")
    outline = relationship("Outline", back_populates="project", uselist=False, cascade="all, delete-orphan")
    chapter_outlines = relationship("ChapterOutline", back_populates="project", cascade="all, delete-orphan")
    agent_prompts = relationship("ProjectAgentPrompt", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.name}>"