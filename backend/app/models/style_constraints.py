"""风格约束模型

包含禁忌词、禁用句式、风格锚点和抽象风格规则。
"""

from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class StyleConstraints(Base):
    """风格约束"""

    __tablename__ = "style_constraints"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # 禁忌词列表
    taboo_words = Column(JSON, default=list)
    # 禁用句式列表
    forbidden_patterns = Column(JSON, default=list)
    # 风格锚点（用户贴的参考文段）
    style_anchor = Column(Text, nullable=True)
    # 抽象风格规则（自然语言描述）
    abstract_rules = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="style_constraints")

    def __repr__(self):
        return f"<StyleConstraints project_id={self.project_id}>"
