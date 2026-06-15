"""Agent 工具统一导出

所有 29 个工具 + 阶段常量 + 内部函数。
"""

# 感知工具
from app.agents.tools.perception import (
    knowledge_search,
    foreshadowing_check,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
)
# 修改工具
from app.agents.tools.modification import (
    apply_change,
    reject_change,
    list_proposed_changes,
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
)
# 创作辅助
from app.agents.tools.assist import (
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
)
# 创作工具
from app.agents.tools.creation import (
    create_world_setting,
    create_character,
    create_relation,
    create_subplot,
    create_plot_question,
    create_timeline_entry,
    create_style_constraints,
    create_foreshadowing,
    create_plot_block,
    generate_outline,
    generate_chapter_content,
    generate_story_seed,
    generate_world_setting_complete,
    review_chapter,
    rewrite_chapter,
    advance_phase,
)
# 阶段工具列表
from app.agents.tools.registry import (
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
)
# 内部函数（测试兼容）
from app.agents.tools.utils import _kb, _extract_keywords, _grade_impact
