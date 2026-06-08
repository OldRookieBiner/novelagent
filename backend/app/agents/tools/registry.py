"""工具注册表 — 按阶段注册可用工具

模块级常量，确保阶段工具集合满足递进关系：
INCUBATION_TOOLS ⊆ STRUCTURE_TOOLS ⊆ WRITING_TOOLS
使用延迟导入避免循环依赖。
"""

# 延迟导入，避免循环依赖
from app.agents.tools.perception import (
    knowledge_search,
    foreshadowing_check,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
)
from app.agents.tools.modification import (
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
)
from app.agents.tools.assist import (
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
)
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

# 孵化阶段可用工具（基础感知 + 内容创建）
INCUBATION_TOOLS = [
    # 阶段管理
    advance_phase,
    # 感知
    knowledge_search,
    progress_report,
    expand_world_setting,
    # 生成（直接内容创建）
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    # 创写（直接写入）
    create_world_setting,
    create_character,
    create_relation,
    create_style_constraints,
    create_foreshadowing,
]

# 结构阶段可用工具（孵化全部 + 结构分析 + 情节构建）
# 修复：确保 INCUBATION ⊆ STRUCTURE，补回孵化阶段的独有工具
STRUCTURE_TOOLS = [
    # 阶段管理
    advance_phase,
    # 感知（孵化 + 新增）
    knowledge_search,
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    progress_report,
    rhythm_analysis,
    # 创作辅助（孵化继承）
    expand_world_setting,
    # 生成（孵化继承 + 结构生成）
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    # 修改
    propose_outline_adjustment,
    # 创作辅助（新增）
    suggest_foreshadowing,
    # 创写（孵化继承 + 结构相关）
    create_world_setting,
    create_style_constraints,
    create_plot_block,
    create_plot_question,
    create_subplot,
    create_foreshadowing,
    create_character,
    create_relation,
]

# 写作阶段可用工具（全部工具）
# 确保 STRUCTURE ⊆ WRITING
WRITING_TOOLS = [
    # 阶段管理
    advance_phase,
    # 感知（全部）
    knowledge_search,
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # 生成（主要写作工具）
    generate_chapter_content,
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    # 修改（全部）
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # 创作辅助（全部）
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
    # 创写（全部）
    create_world_setting,
    create_character,
    create_relation,
    create_style_constraints,
    create_subplot,
    create_plot_question,
    create_timeline_entry,
    create_foreshadowing,
    create_plot_block,
]

# 全部工具（默认）
AGENT_TOOLS = WRITING_TOOLS
