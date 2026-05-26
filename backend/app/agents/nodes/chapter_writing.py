"""章节正文生成节点（执行）"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import CHAPTER_WRITING_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def chapter_writing_node(state: NovelState) -> NovelState:
    """基于章节点+上下文+风格约束写正文"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    style = kb.get_style_constraints()
    style_text = f"禁忌词：{style.taboo_words}\n锚点：{style.style_anchor}" if style else ""

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_writing")

    # 上下文由 context_assembly_node 准备，此处简化为 DB 读取
    outline = kb.get_outline()
    characters = kb.get_characters()
    plot_blocks = kb.get_plot_blocks()
    current_block = kb.get_current_plot_block(current_chapter)

    context_parts = []
    if outline:
        context_parts.append(f"大纲概述：{outline.summary}")
    if current_block:
        context_parts.append(f"当前情节块：{current_block.title}")
    if characters:
        context_parts.append("角色：" + ", ".join([c.name for c in characters]))

    previous_context = "\n".join(context_parts) if context_parts else ""

    target_words = 3000  # 默认目标字数

    if user_template:
        prompt_text = safe_format(user_template,
            chapter_node="（章节点确认后的内容）",
            style_constraints=style_text,
            previous_context=previous_context,
            target_words=str(target_words),
        )
    else:
        prompt_text = safe_format(CHAPTER_WRITING_PROMPT,
            chapter_node="（章节点确认后的内容）",
            style_constraints=style_text,
            previous_context=previous_context,
            target_words=str(target_words),
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.8):
        response += chunk

    # 保存章节内容到 state
    word_count = len(response)
    new_chapter = {
        "chapter_number": current_chapter,
        "content": response,
        "word_count": word_count,
    }

    return {
        **state,
        "written_chapters": [new_chapter],
        "current_chapter": current_chapter + 1,
    }
