"""Knowledge base change proposal + impact assessment tracking

Spec section 4: Knowledge base changes must be proposed first,
assessed for impact, then approved/abandoned by the author.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class SettingChange(Base):
    """Knowledge base change proposal

    Tracks proposed changes to the knowledge base along with
    their impact assessment and the author's decision.
    """

    __tablename__ = "setting_changes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    # What is being changed: world_setting / character / foreshadowing / style / outline / relation
    target_type = Column(String(50), nullable=False)
    # ID of the object being changed
    target_id = Column(Integer, nullable=False)
    # JSON snapshot of the current value
    old_value = Column(JSON, nullable=True)
    # JSON of the proposed new value
    new_value = Column(JSON, nullable=False)
    # proposed / approved / abandoned / applied
    status = Column(String(20), default="proposed")
    # Impact assessment report JSON: {level, affected_chapters, affected_paragraphs, details}
    impact_report = Column(JSON, nullable=True)
    # Author decision: proceed / adjust / abandon
    author_decision = Column(String(20), nullable=True)
    # Natural language description of the change
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="setting_changes")

    def __repr__(self):
        return f"<SettingChange {self.target_type}:{self.target_id} status={self.status}>"
