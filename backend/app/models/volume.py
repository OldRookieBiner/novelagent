"""Volume model — 卷"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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

    # Relationships
    project = relationship("Project", back_populates="volumes")
    arcs = relationship("Arc", back_populates="volume", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Volume project_id={self.project_id} num={self.volume_number}>"
