"""最终润色节点"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import FINAL_POLISH_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def final_polish_node(state: NovelState) -> NovelState:
    """最终润色 + 可选生成设定百科"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    # 此节点在实际实现中会根据审查结果修改章节
    # 阶段1骨架：简化实现
    return {**state}
