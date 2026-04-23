"""LangGraph agent state definitions"""

from typing import TypedDict, Optional, Annotated, Any
from operator import add


class CollectedInfo(TypedDict, total=False):
    """用户收集的信息（v0.5.0 灵感数据）"""
    novelType: str
    targetWords: int
    coreTheme: str
    worldSetting: str
    customWorldSetting: str
    protagonist: str
    customProtagonist: str
    stylePreference: str
    targetReader: str
    wordsPerChapter: str
    customWordsPerChapter: int
    narrative: str
    goldFinger: str
    customGoldFinger: str


class NovelState(TypedDict):
    """小说创作状态 - v0.6.2 LangGraph 重构版"""

    # ========== 基本信息 ==========
    project_id: int

    # ========== 阶段控制 ==========
    stage: str  # inspiration | outline | chapter_outlines | writing | review | complete

    # ========== 灵感/输入 ==========
    collected_info: dict[str, Any]
    inspiration_template: Optional[str]

    # ========== 大纲 ==========
    outline_title: Optional[str]
    outline_summary: Optional[str]
    outline_plot_points: list[dict]  # [{order, event, conflict, hook}]
    outline_characters: list[dict]   # [{name, role, personality, motivation, arc}]
    outline_world_setting: Optional[dict]  # {era, core_rules, power_system}
    outline_emotional_curve: Optional[str]
    outline_confirmed: bool

    # ========== 章节大纲 ==========
    chapter_count: int
    chapter_outlines: list[dict]  # [{chapter_number, title, scene, ...}]
    chapter_outlines_confirmed: bool

    # ========== 章节正文（累积）==========
    # Annotated[List, add] 表示新内容会追加到列表
    written_chapters: Annotated[list[dict], add]  # [{chapter_number, content, word_count}]
    current_chapter: int

    # ========== 审核/重写 ==========
    review_mode: str  # step_by_step | hybrid | auto
    review_result: Optional[dict]  # {passed, scores, issues, feedback}
    rewrite_count: int
    max_rewrite_count: int

    # ========== 工作流控制 ==========
    waiting_for_confirmation: bool
    confirmation_type: Optional[str]  # outline | chapter_outlines | review_failed

    # ========== LLM 服务 ==========
    llm_config_id: Optional[int]  # 使用的模型配置 ID


# ========== 阶段常量 ==========
STAGE_INSPIRATION = "inspiration"
STAGE_OUTLINE = "outline"
STAGE_CHAPTER_OUTLINES = "chapter_outlines"
STAGE_WRITING = "writing"
STAGE_REVIEW = "review"
STAGE_COMPLETE = "complete"

# ========== 工作流模式常量 ==========
WORKFLOW_MODE_STEP_BY_STEP = "step_by_step"
WORKFLOW_MODE_HYBRID = "hybrid"
WORKFLOW_MODE_AUTO = "auto"
