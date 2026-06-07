"""WorkflowState model for storing creation phase state"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class WorkflowState(Base):
    """工作流状态模型（Agent 模式精简版）

    只保留 Phase（创作阶段）、当前章节号和 LLM 配置。
    """

    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    # 创作阶段（Phase enum 值：incubation/structure/writing/revision）
    stage = Column(String(30), nullable=False, default="incubation")

    # 进度追踪
    current_chapter = Column(Integer, nullable=False, default=1)

    # LLM 配置（持久化，确保所有端点使用同一模型）
    llm_config_id = Column(Integer, nullable=True)
    llm_model_name = Column(String(100), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 关系
    project = relationship("Project", back_populates="workflow_states")

    def __repr__(self):
        return f"<WorkflowState project_id={self.project_id} stage={self.stage}>"
