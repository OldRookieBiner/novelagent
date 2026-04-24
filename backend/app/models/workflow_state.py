"""WorkflowState model for storing workflow state"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class WorkflowState(Base):
    """工作流状态模型

    存储项目的工作流状态，支持多工作流实例。
    与 Project 是 N:1 关系，通过 thread_id 区分不同工作流。
    """

    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    thread_id = Column(String(50), nullable=False, default="main")

    # 工作流阶段（统一命名）
    stage = Column(String(30), nullable=False, default="inspiration")

    # 工作流模式
    workflow_mode = Column(String(20), nullable=False, default="hybrid")
    max_rewrite_count = Column(Integer, nullable=False, default=3)

    # 进度追踪
    current_chapter = Column(Integer, nullable=False, default=1)

    # 确认状态
    waiting_for_confirmation = Column(Boolean, nullable=False, default=False)
    confirmation_type = Column(String(30), nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    project = relationship("Project", back_populates="workflow_states")

    def __init__(self, **kwargs):
        """初始化，设置 Python 层面的默认值"""
        # 设置默认值
        defaults = {
            "thread_id": "main",
            "stage": "inspiration",
            "workflow_mode": "hybrid",
            "max_rewrite_count": 3,
            "current_chapter": 1,
            "waiting_for_confirmation": False,
        }
        # 合并传入的参数
        for key, value in defaults.items():
            if key not in kwargs:
                kwargs[key] = value
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<WorkflowState project_id={self.project_id} stage={self.stage}>"
