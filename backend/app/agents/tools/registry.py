"""工具注册表 — 按阶段注册可用工具

模块级常量，确保阶段工具集合满足递进关系：
INCUBATION_TOOLS ⊆ STRUCTURE_TOOLS ⊆ WRITING_TOOLS ⊆ REVISION_TOOLS
使用列表拼接保证递进关系，新阶段只需添加增量工具。
"""

from app.agents.tools.perception import (
    knowledge_search,
    foreshadowing_check,
    consistency_scan,
    style_analysis,
    progress_report,
    rhythm_analysis,
)
from app.agents.tools.modification import (
    apply_change,
    reject_change,
    list_proposed_changes,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
)
from app.agents.tools.assist import (
    suggest_writing_direction,
    expand_world_setting,
)
from app.agents.tools.creation import (
    create_evolution_plan,
    create_world_setting,
    create_character,
    create_relation,
    create_subplot,
    create_plot_question,
    create_style_constraints,
    create_foreshadowing,
    create_plot_block,
    generate_outline,
    generate_chapter_outline,
    generate_chapter_content,
    generate_story_seed,
    generate_world_setting_complete,
    review_chapter,
    rewrite_chapter,
    advance_phase,
    update_plot_block,
    update_subplot,
    update_plot_question,
    update_foreshadowing,
    delete_plot_block,
    record_chapter_meta,
)

# 孵化阶段
INCUBATION_TOOLS = [
    advance_phase,
    knowledge_search,
    progress_report,
    expand_world_setting,
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    create_world_setting,
    create_character,
    create_relation,
    create_evolution_plan,
    create_style_constraints,
    create_foreshadowing,
]

# 结构阶段增量
_STRUCTURE_EXTRA = [
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    rhythm_analysis,
    generate_chapter_outline,
    propose_outline_adjustment,
    create_plot_block,
    create_plot_question,
    create_subplot,
    update_plot_block,
    update_plot_question,
    delete_plot_block,
    apply_change,
    reject_change,
    list_proposed_changes,
    suggest_writing_direction,
]

# 写作阶段增量
_WRITING_EXTRA = [
    consistency_scan,
    style_analysis,
    generate_chapter_content,
    propose_setting_change,
    propose_chapter_rewrite,
    record_chapter_meta,
    update_subplot,
    update_foreshadowing,
]

STRUCTURE_TOOLS = INCUBATION_TOOLS + _STRUCTURE_EXTRA
WRITING_TOOLS = STRUCTURE_TOOLS + _WRITING_EXTRA
REVISION_TOOLS = WRITING_TOOLS

AGENT_TOOLS = WRITING_TOOLS


# 工具元数据分类 — 仅程序化使用，不注入 system prompt
TOOL_COST_TIER = {
    "review_chapter": "llm",
    "rewrite_chapter": "llm",
    "consistency_scan": "rule",
    "rhythm_analysis": "rule",
    "style_analysis": "rule",
    "foreshadowing_check": "rule",
    "progress_report": "rule",
}


def get_cost_tier(tool_name: str) -> str:
    """查询工具的 cost_tier，未标注默认 db"""
    return TOOL_COST_TIER.get(tool_name, "db")
