"""LangGraph agent state definitions"""

from typing import TypedDict, Optional, Annotated
from operator import add


class CollectedInfo(TypedDict, total=False):
    """Collected information from user"""
    genre: str
    theme: str
    main_characters: str
    world_setting: str
    style_preference: str


class NovelState(TypedDict):
    """Novel creation state"""

    # Project info
    project_id: int
    stage: str

    # Collected info
    collected_info: CollectedInfo

    # Outline
    outline_title: Optional[str]
    outline_summary: Optional[str]
    outline_plot_points: list[str]
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

    # Review
    review_enabled: bool
    review_passed: bool
    review_feedback: Optional[str]

    # Chat
    messages: Annotated[list[dict], add]
    last_user_message: Optional[str]
    last_assistant_message: Optional[str]


# Stage constants
STAGE_COLLECTING_INFO = "collecting_info"
STAGE_OUTLINE_GENERATING = "outline_generating"
STAGE_OUTLINE_CONFIRMING = "outline_confirming"
STAGE_CHAPTER_COUNT_SUGGESTING = "chapter_count_suggesting"
STAGE_CHAPTER_COUNT_CONFIRMING = "chapter_count_confirming"
STAGE_CHAPTER_OUTLINES_GENERATING = "chapter_outlines_generating"
STAGE_CHAPTER_OUTLINES_CONFIRMING = "chapter_outlines_confirming"
STAGE_CHAPTER_WRITING = "chapter_writing"
STAGE_CHAPTER_REVIEWING = "chapter_reviewing"
STAGE_COMPLETED = "completed"
STAGE_PAUSED = "paused"