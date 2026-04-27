"""LangGraph agent state definitions"""

from typing import TypedDict, Optional, Annotated, Any
from operator import add


def replace_or_append_chapters(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """
    自定义 reducer：替换同章节号的章节或追加新章节

    用于 written_chapters 字段，解决 rewrite 场景的重复章节问题：
    - 如果新章节的 chapter_number 已存在，则替换
    - 否则追加到列表末尾
    """
    result = list(existing)
    for new_chapter in new_items:
        chapter_num = new_chapter.get("chapter_number")
        existing_idx = None
        for i, ch in enumerate(result):
            if ch.get("chapter_number") == chapter_num:
                existing_idx = i
                break
        if existing_idx is not None:
            result[existing_idx] = new_chapter
        else:
            result.append(new_chapter)
    return result


class CollectedInfo(TypedDict, total=False):
    """用户收集的信息（v0.5.0 灵感数据，v0.7.x 扩展）"""
    # 必填项
    novelType: str
    targetWords: int
    coreTheme: str
    targetReader: str
    era: str                    # v0.7.x: 年代设定
    wordsPerChapter: str
    customWordsPerChapter: int
    # 主角设定（根据 targetReader 选择）
    maleLead: str               # v0.7.x: 男主人设
    customMaleLead: str
    femaleLead: str             # v0.7.x: 女主人设
    customFemaleLead: str
    # 选填项
    worldSetting: str
    customWorldSetting: str
    genre: str                  # v0.7.x: 流派
    narrative: str
    goldFinger: str
    customGoldFinger: str
    stylePreference: str


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
    written_chapters: Annotated[list[dict], replace_or_append_chapters]  # [{chapter_number, content, word_count}]
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
