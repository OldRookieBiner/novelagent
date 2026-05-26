"""章节点生成节点（决策）"""

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

    # 加载上下文
    current_block = kb.get_current_plot_block(current_chapter)
    style = kb.get_style_constraints()
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    pending = kb.get_pending_foreshadowings()
    questions = kb.get_questions_for_chapter(current_chapter)
    characters = kb.get_characters()
    world_setting = kb.get_world_setting()

    # 格式化上下文
    plot_block_goal = f"{current_block.title}：{current_block.must_happen}" if current_block else ""
    style_text = f"禁忌词：{style.taboo_words}\n规则：{style.abstract_rules}" if style else ""
    foreshadowing_text = "\n".join([f"- {f.content}（等级：{f.level}）" for f in overdue + pending[:5]])
    questions_text = "\n".join([f"- {q.question_text}" for q in questions])
    chars_text = "\n".join([f"- {c.name}（{c.role}）：{c.core_motivation or ''}" for c in characters])
    setting_text = world_setting.core_concept if world_setting else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_planning")

    if user_template:
        prompt_text = safe_format(user_template,
            plot_block_goal=plot_block_goal,
            style_constraints=style_text,
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info=chars_text,
            world_setting_info=setting_text,
            previous_context="",
            chapter_number=str(current_chapter),
            next_block="后续",
        )
    else:
        prompt_text = safe_format(CHAPTER_PLANNING_PROMPT,
            plot_block_goal=plot_block_goal,
            style_constraints=style_text,
            pending_foreshadowings=foreshadowing_text,
            pending_questions=questions_text,
            characters_info=chars_text,
            world_setting_info=setting_text,
            previous_context="",
            chapter_number=str(current_chapter),
            next_block="后续",
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.6):
        response += chunk

    return {
        **state,
        "waiting_for_confirmation": True,
        "confirmation_type": ConfirmationType.CHAPTER_NODE.value,
    }
