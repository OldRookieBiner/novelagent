"""Project schemas"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class WorkflowStateBase(BaseModel):
    """WorkflowState 基础 Schema"""
    thread_id: str = "main"
    stage: str = "inspiration"
    workflow_mode: str = "hybrid"
    max_rewrite_count: int = 3
    current_chapter: int = 1
    waiting_for_confirmation: bool = False
    confirmation_type: Optional[str] = None


class WorkflowStateResponse(WorkflowStateBase):
    """WorkflowState 响应 Schema"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    """Project 基础 Schema"""
    name: str
    target_words: Optional[int] = 100000


class ProjectCreate(ProjectBase):
    """Project 创建 Schema"""
    pass


class ProjectUpdate(BaseModel):
    """Project 更新 Schema"""
    name: Optional[str] = None
    target_words: Optional[int] = None


class ProjectResponse(ProjectBase):
    """Project 响应 Schema"""
    id: int
    user_id: int
    total_words: int
    created_at: datetime
    updated_at: datetime
    workflow_state: Optional[WorkflowStateResponse] = None

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Project 详情响应 Schema"""
    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0


class ProjectListResponse(BaseModel):
    """Project 列表响应 Schema"""
    projects: List[ProjectResponse]
    total: int
