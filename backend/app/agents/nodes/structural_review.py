"""结构完整性检查节点"""

from app.agents.state import NovelState, Phase
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import STRUCTURAL_REVIEW_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def structural_review_node(state: NovelState) -> NovelState:
    """结构完整性：伏笔闭环/问题链闭环/时间线一致性/支线闭环"""
    project_id = state["project_id"]
    kb = KnowledgeBaseService(project_id)

    foreshadowings = kb.get_foreshadowings()
    questions = kb.get_plot_questions()
    timeline = kb.get_timeline()
    subplots = kb.get_subplots()

    # 格式化审查数据
    fs_text = "\n".join([f"- {f.content}（{f.status}）" for f in foreshadowings])
    q_text = "\n".join([f"- {q.question_text}（{q.status}）" for q in questions])
    t_text = "\n".join([f"第{e.chapter_number}章：{e.summary}" for e in timeline[-10:]])
    sp_text = "\n".join([f"- {s.name}（{s.current_status}）" for s in subplots])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "structural_review")

    if user_template:
        prompt_text = safe_format(user_template,
            foreshadowings=fs_text,
            plot_questions=q_text,
            timeline=t_text,
            subplots=sp_text,
        )
    else:
        prompt_text = safe_format(STRUCTURAL_REVIEW_PROMPT,
            foreshadowings=fs_text,
            plot_questions=q_text,
            timeline=t_text,
            subplots=sp_text,
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.2):
        response += chunk

    return {**state, "phase": Phase.REVISION.value}
