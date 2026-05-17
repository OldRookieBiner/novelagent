"""Volume and Arc schemas"""

from typing import Optional, List
from pydantic import BaseModel


class VolumeResponse(BaseModel):
    id: int
    project_id: int
    volume_number: int
    title: Optional[str] = None
    summary: Optional[str] = None


class VolumeUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None


class ArcResponse(BaseModel):
    id: int
    volume_id: int
    arc_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    chapter_count: int


class ArcUpdate(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None


class VolumeWithArcsResponse(BaseModel):
    """卷 + 包含的弧列表"""
    id: int
    project_id: int
    volume_number: int
    title: Optional[str] = None
    summary: Optional[str] = None
    arcs: List[ArcResponse] = []
