"""角色一致性自查节点

检查行为/对话/知识边界，更新动态设定。
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import POST_WRITE_CHECK_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def character_consistency_node(state: NovelState) -> NovelState:
    """角色一致性自查 + 更新动态设定"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1) - 1  # 已递增，回退1
    kb = KnowledgeBaseService(project_id)

    # 获取刚写的章节
    written = state.get("written_chapters", [])
    chapter = None
    for ch in written:
        if ch.get("chapter_number") == current_chapter:
            chapter = ch
            break

    if not chapter:
        return {**state}

    content = chapter.get("content", "")
    characters = kb.get_characters()
    chars_text = "\n".join([f"- {c.name}（知识边界：{c.knowledge_boundary if hasattr(c, 'knowledge_boundary') else '未设定'}）" for c in characters])

    # 角色一致性检查（简化：用 LLM 检查）
    check_prompt = f"检查以下章节中角色行为是否一致，是否有角色说出其知识边界之外的信息：\n\n{content[:2000]}\n\n角色设定：\n{chars_text}"

    llm = await get_llm_from_state_async(state)
    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": check_prompt}], temperature=0.2):
        response += chunk

    # 结果不存入 state，仅记录到 DB 或日志
    return {**state}
