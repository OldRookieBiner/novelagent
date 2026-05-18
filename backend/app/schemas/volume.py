"""卷和弧的 Pydantic schemas"""

from typing import Optional
from pydantic import BaseModel


class ArcResponse(BaseModel):
    """弧响应"""
    id: int
    volume_id: int
    arc_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    outline: Optional[str] = None
    outline_confirmed: bool = False
    chapter_count: int = 10

    class Config:
        from_attributes = True


class ArcUpdate(BaseModel):
    """弧更新请求"""
    title: Optional[str] = None
    summary: Optional[str] = None
    outline: Optional[str] = None
    outline_confirmed: Optional[bool] = None
    chapter_count: Optional[int] = None


class VolumeResponse(BaseModel):
    """卷响应"""
    id: int
    project_id: int
    volume_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    arcs: list[ArcResponse] = []

    class Config:
        from_attributes = True
