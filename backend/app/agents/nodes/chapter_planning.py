"""章节点生成节点（决策）

基于上下文生成本章的章节点（因果链/钩子/场景规划）。
输出写入 state["chapter_plan"]，供 chapter_writing_node 使用。
"""

from app.agents.state import NovelState, ConfirmationType
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHAPTER_PLANNING_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def chapter_planning_node(state: NovelState) -> NovelState:
    """生成本章的章节点（因果链/钩子/场景规划）"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 使用 context_assembly_node 已组装的上下文
    assembled_context = state.get("assembled_context", "")

    # 补充 chapter_planning 需要的额外上下文
    current_block = kb.get_current_plot_block(current_chapter)
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    pending = kb.get_pending_foreshadowings()
    questions = kb.get_questions_for_chapter(current_chapter)

    # 格式化上下文
    plot_block_goal = ""
    if current_block:
        plot_block_goal = f"{current_block.title}"
        if current_block.must_happen:
            plot_block_goal += f"：{', '.join(current_block.must_happen)}"

    foreshadowing_text = "\n".join([
        f"- {f.content}（等级：{f.level}，状态：{f.status}）"
        for f in (overdue + pending[:5])
    ])
    questions_text = "\n".join([f"- {q.question_text}" for q in questions])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_planning")

    if user_template:
        prompt_text = safe_format(user_template,
            plot_block_goal=plot_block_goal,
            style_constraints="（见组装上下文）",
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info="（见组装上下文）",
            world_setting_info="（见组装上下文）",
            previous_context=assembled_context,
            chapter_number=str(current_chapter),
            next_block="后续",
        )
    else:
        prompt_text = safe_format(CHAPTER_PLANNING_PROMPT,
            plot_block_goal=plot_block_goal,
            style_constraints="（见组装上下文）",
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info="（见组装上下文）",
            world_setting_info="（见组装上下文）",
            previous_context=assembled_context,
            chapter_number=str(current_chapter),
            next_block="后续",
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.6
    ):
        response += chunk

    return {
        **state,
        "chapter_plan": response,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.CHAPTER_NODE.value,
    }
