"""小说创作智能体状态定义 v2

设计原则：
- state 只存流程控制状态和 ID 引用，不缓存 DB 数据
- 节点通过 KnowledgeBaseService 从 DB 实时读取业务数据
- 避免检查点序列化/反序列化性能问题

阶段使用 Enum 替代字符串，确认类型同理。

Phase 4 新增：
- VOLUME_TRANSITION 确认类型
- current_volume 字段（当前卷号）
- revision_context 字段（修订范围控制）
"""

from enum import Enum
from typing import TypedDict, Optional, Annotated


class Phase(str, Enum):
    """创作阶段"""
    INCUBATION = "incubation"
    STRUCTURE = "structure"
    WRITING = "writing"
    REVISION = "revision"


class ConfirmationType(str, Enum):
    """确认类型——类型安全，避免字符串拼写错误"""
    INSPIRATION_DIALOGUE = "inspiration_dialogue"
    STORY_SEED = "story_seed"
    OUTLINE = "outline"
    WORLD_SETTING = "world_setting"
    CHARACTERS = "characters"
    RELATIONS = "relations"
    STYLE = "style"
    FORESHADOWING_PLAN = "foreshadowing_plan"
    STRUCTURE = "structure"
    CHAPTER_NODE = "chapter_node"
    REVIEW_FAILED = "review_failed"
    VOLUME_TRANSITION = "volume_transition"


class RevisionContext(str, Enum):
    """修订范围控制"""
    PER_VOLUME = "per_volume"    # 逐卷修订（卷过渡后）
    FULL_BOOK = "full_book"      # 全书修订（所有章节完成后）


def replace_or_append_chapters(
    existing: list[dict], new_items: list[dict]
) -> list[dict]:
    """自定义 reducer：替换同章节号的章节或追加新章节

    用于 written_chapters 字段：
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


class NovelState(TypedDict):
    """小说创作智能体状态 v2

    state 只存流程控制状态和 ID 引用。
    所有业务数据通过 KnowledgeBaseService 从 DB 实时读取。

    例外：chapter_plan 是章节规划的 LLM 输出，在写作循环内
    从 chapter_planning 传递到 chapter_writing，不写入 DB，
    因为它是一个临时的工作记忆。
    """

    # ========== 基本信息 ==========
    project_id: int

    # ========== 阶段控制 ==========
    phase: str  # Phase enum value

    # ========== 创意孵化 ==========
    story_seed: Optional[str]
    # 创意对话消息（临时，孵化完成后不保留到检查点）
    inspiration_messages: list[dict]

    # ========== 知识库 ID 引用 ==========
    outline_id: Optional[int]
    world_setting_id: Optional[int]
    style_constraints_id: Optional[int]

    # ========== 结构 ==========
    current_plot_block_index: int
    chapter_count: int

    # ========== 写作 ==========
    current_chapter: int
    written_chapters: Annotated[
        list[dict], replace_or_append_chapters
    ]  # [{chapter_number, content, word_count}]

    # ========== 写作工作记忆（循环内临时传递，不写 DB）==========
    # chapter_planning_node 的 LLM 输出，传给 chapter_writing_node
    chapter_plan: Optional[str]
    # context_assembly_node 组装的上下文摘要，传给下游写作节点
    assembled_context: Optional[str]

    # ========== 写后自检 ==========
    # 自检结果摘要（不存完整数据，完整数据写入 DB）
    post_write_summary: Optional[str]
    # 上次深度审查的章节号
    last_review_chapter: int

    # ========== 卷管理（Phase 4）==========
    current_volume: int  # 当前卷号（1-based）
    # 修订范围控制：per_volume = 逐卷修订, full_book = 全书修订
    # 修订节点读取此字段决定审查范围
    revision_context: Optional[str]  # RevisionContext enum value

    # ========== 工作流控制 ==========
    waiting_for_confirmation: bool
    confirmation_type: Optional[str]  # ConfirmationType enum value

    # ========== LLM 服务 ==========
    llm_config_id: Optional[int]
    review_llm_config_id: Optional[int]
    llm_model_name: Optional[str]

    # ========== Prompt 加载（LangGraph 合规）==========
    _prompts: dict[str, str | dict]
    _context_window: int


# ========== 兼容旧代码的阶段常量（迁移期使用）==========
STAGE_INSPIRATION = Phase.INCUBATION.value
STAGE_OUTLINE = Phase.INCUBATION.value
STAGE_CHARACTERS = Phase.INCUBATION.value
STAGE_RELATIONS = Phase.INCUBATION.value
STAGE_VOLUME_ARC = Phase.STRUCTURE.value
STAGE_ARC_OUTLINES = Phase.STRUCTURE.value
STAGE_CHAPTER_OUTLINES = Phase.STRUCTURE.value
STAGE_WRITING = Phase.WRITING.value
STAGE_REVIEW = Phase.WRITING.value
STAGE_COMPLETE = Phase.REVISION.value
