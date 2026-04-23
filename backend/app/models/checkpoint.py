"""Workflow checkpoint model for LangGraph state persistence"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class WorkflowCheckpoint(Base):
    """LangGraph workflow checkpoint for state persistence"""

    __tablename__ = "workflow_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(100), nullable=False, index=True)  # LangGraph thread ID
    checkpoint_id = Column(String(36), nullable=True, index=True)  # UUID 格式的检查点 ID
    checkpoint = Column(JSONB, nullable=False)  # Complete State JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", backref="checkpoints")

    def __repr__(self):
        return f"<WorkflowCheckpoint project_id={self.project_id} thread={self.thread_id}>"
