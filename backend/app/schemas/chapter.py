"""Chapter schemas"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ChapterOutlineBase(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    turning_point: Optional[str] = None  # 转折点
    hook: Optional[str] = None  # 悬念钩子
    transition: Optional[str] = None  # 过渡衔接
    ending: Optional[str] = None
    opening_state: Optional[str] = None  # 开场状态
    emotional_arc: Optional[str] = None  # 情绪弧线
    key_scenes: Optional[list[dict]] = None  # 核心场景列表
    pacing_note: Optional[str] = None  # 节奏标注
    target_words: Optional[int] = 3000


class ChapterOutlineUpdate(BaseModel):
    title: Optional[str] = None
    scene: Optional[str] = None
    characters: Optional[str] = None
    plot: Optional[str] = None
    conflict: Optional[str] = None
    turning_point: Optional[str] = None  # 转折点
    hook: Optional[str] = None  # 悬念钩子
    transition: Optional[str] = None  # 过渡衔接
    ending: Optional[str] = None
    opening_state: Optional[str] = None  # 开场状态
    emotional_arc: Optional[str] = None  # 情绪弧线
    key_scenes: Optional[list[dict]] = None  # 核心场景列表
    pacing_note: Optional[str] = None  # 节奏标注
    target_words: Optional[int] = None


class ChapterOutlineResponse(ChapterOutlineBase):
    id: int
    project_id: int
    chapter_number: int
    arc_id: Optional[int] = None
    confirmed: bool
    created_at: datetime
    has_content: bool = False

    class Config:
        from_attributes = True


class ChapterContentUpdate(BaseModel):
    content: str


class ChapterResponse(BaseModel):
    id: int
    chapter_outline_id: int
    content: Optional[str] = None
    word_count: int
    review_passed: bool
    review_feedback: Optional[str] = None
    summary: Optional[str] = None
    # v0.6.1 审核增强字段
    review_result: Optional[dict] = None
    rewrite_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
