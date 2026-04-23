"""LangGraph agent state definitions"""

from typing import TypedDict, Optional, Annotated, Any
from operator import add


class CollectedInfo(TypedDict, total=False):
    """Collected information from user (v0.5.0 inspiration data)"""
    novelType: str
    targetWords: int  # Changed from string to number
    coreTheme: str
    worldSetting: str
    customWorldSetting: str
    protagonist: str
    customProtagonist: str
    stylePreference: str
    # New fields
    targetReader: str
    wordsPerChapter: str
    customWordsPerChapter: int
    narrative: str
    goldFinger: str
    customGoldFinger: str


class NovelState(TypedDict):
    """Novel creation state"""

    # Project info
    project_id: int
    stage: str

    # Collected info (v0.5.0 inspiration data)
    collected_info: dict[str, Any]
    inspiration_template: Optional[str]

    # Outline (v0.6.1 增强版)
    outline_title: Optional[str]
    outline_summary: Optional[str]
    outline_plot_points: list[str]
    outline_characters: list[dict]  # 新增：人物设定
    outline_world_setting: Optional[dict]  # 新增：世界观
    outline_emotional_curve: Optional[str]  # 新增：情感曲线
    outline_confirmed: bool

    # Chapter count
    chapter_count_suggested: int
    chapter_count_confirmed: bool

    # Chapter outlines
    chapter_outlines: list[dict]
    chapter_outlines_confirmed: bool

    # Current chapter
    current_chapter: int
    chapter_content: Optional[str]

    # Review (v0.6.1 更新)
    review_mode: str  # 'off' | 'manual' | 'auto'
    review_enabled: bool
    review_passed: bool
    review_result: Optional[dict]  # 审核结果详情
    review_feedback: Optional[str]
    rewrite_count: int  # 当前重写次数
    max_rewrite_count: int  # 最大重写次数

    # Chat
    messages: Annotated[list[dict], add]
    last_user_message: Optional[str]
    last_assistant_message: Optional[str]


# Stage constants
STAGE_INSPIRATION_COLLECTING = "inspiration_collecting"
STAGE_OUTLINE_GENERATING = "outline_generating"
STAGE_OUTLINE_CONFIRMING = "outline_confirming"
STAGE_CHAPTER_OUTLINES_GENERATING = "chapter_outlines_generating"
STAGE_CHAPTER_OUTLINES_CONFIRMING = "chapter_outlines_confirming"
STAGE_CHAPTER_WRITING = "chapter_writing"
STAGE_CHAPTER_REVIEWING = "chapter_reviewing"
STAGE_COMPLETED = "completed"
STAGE_PAUSED = "paused"
