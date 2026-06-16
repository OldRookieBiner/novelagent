"""向后兼容层 — 所有导入已迁移到 app.agents.tools

此文件保留为兼容层，确保旧导入路径仍然可用。
新代码应使用 from app.agents.tools import ...
"""

from app.agents.tools import (
    # 感知工具
    knowledge_search,
    foreshadowing_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # 修改工具
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # 创作辅助
    expand_world_setting,
    # 创作工具
    create_world_setting,
    create_character,
    create_relation,
    create_evolution_plan,
    create_subplot,
    create_plot_question,
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
    # 阶段工具列表
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
    # 内部函数
    _kb,
    _extract_keywords,
    _grade_impact,
)
