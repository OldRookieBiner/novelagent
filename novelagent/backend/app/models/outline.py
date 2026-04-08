"""Outline models"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Outline(Base):
    """Novel outline model"""

    __tablename__ = "outlines"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False)
    title = Column(String(200), nullable=True)
    summary = Column(Text, nullable=True)
    plot_points = Column(JSON, default=list)  # List of plot points
    collected_info = Column(JSON, default=dict)  # Collected information from user
    chapter_count_suggested = Column(Integer, default=0)
    chapter_count_confirmed = Column(Boolean, default=False)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="outline")

    def __repr__(self):
        return f"<Outline project_id={self.project_id}>"


class ChapterOutline(Base):
    """Chapter outline model"""

    __tablename__ = "chapter_outlines"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=True)
    scene = Column(String(500), nullable=True)
    characters = Column(Text, nullable=True)
    plot = Column(Text, nullable=True)
    conflict = Column(Text, nullable=True)
    ending = Column(Text, nullable=True)
    target_words = Column(Integer, default=3000)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="chapter_outlines")
    chapter = relationship("Chapter", back_populates="chapter_outline", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChapterOutline project_id={self.project_id} chapter={self.chapter_number}>"