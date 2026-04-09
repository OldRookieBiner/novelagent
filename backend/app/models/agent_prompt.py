"""Agent prompt models"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class AgentPrompt(Base):
    """Global agent prompts for a user"""
    __tablename__ = "agent_prompts"
    __table_args__ = (
        UniqueConstraint('user_id', 'agent_type', name='uq_user_agent_type'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(String(50), nullable=False)
    prompt_content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="agent_prompts")


class ProjectAgentPrompt(Base):
    """Project-specific agent prompt overrides"""
    __tablename__ = "project_agent_prompts"
    __table_args__ = (
        UniqueConstraint('project_id', 'agent_type', name='uq_project_agent_type'),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_type = Column(String(50), nullable=False)
    prompt_content = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", backref="agent_prompts")