"""Project schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ProjectBase(BaseModel):
    name: str
    target_words: Optional[int] = 100000


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    stage: Optional[str] = None
    target_words: Optional[int] = None


class ProjectResponse(ProjectBase):
    id: int
    user_id: int
    stage: str
    total_words: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


class ProjectDetail(ProjectResponse):
    """Project with additional details"""
    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0