"""章节正文生成节点（执行）

基于章节点 + 组装上下文 + 风格约束写正文。
"""

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

    # 从 state 读取 chapter_planning_node 的输出
    chapter_plan = state.get("chapter_plan", "（无章节点）")
    assembled_context = state.get("assembled_context", "")

    # 读取风格约束
    style = kb.get_style_constraints()
    style_text = ""
    if style:
        parts = []
        if style.taboo_words:
            parts.append(f"禁忌词：{', '.join(style.taboo_words)}")
        if style.style_anchor:
            parts.append(f"风格锚点：{style.style_anchor}")
        if style.abstract_rules:
            parts.append(f"抽象规则：{', '.join(style.abstract_rules)}")
        if parts:
            style_text = "\n".join(parts)

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "chapter_writing")

    # 目标字数
    outline = kb.get_outline()
    target_words = 3000
    if outline and outline.project:
        # 粗略估算
        target_words = max(1500, min(5000, (outline.project.target_words or 100000) // max(state.get("chapter_count", 30), 10)))

    if user_template:
        prompt_text = safe_format(user_template,
            chapter_node=chapter_plan,
            style_constraints=style_text,
            previous_context=assembled_context,
            target_words=str(target_words),
        )
    else:
        prompt_text = safe_format(CHAPTER_WRITING_PROMPT,
            chapter_node=chapter_plan,
            style_constraints=style_text,
            previous_context=assembled_context,
            target_words=str(target_words),
        )

    response = ""
    async for chunk in llm.chat_stream(
        [{"role": "user", "content": prompt_text}], temperature=0.8
    ):
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
        # 清除写作工作记忆，避免下章误用
        "chapter_plan": None,
        "assembled_context": None,
    }
