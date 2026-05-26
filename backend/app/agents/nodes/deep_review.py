"""深度审查节点（每5章触发）

子 Agent 只读审查，不修改原文。
检查维度：情节一致性/伏笔追踪/节奏分析/设定违反/风格漂移/POV审查
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import DEEP_REVIEW_PROMPT
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format


async def deep_review_node(state: NovelState) -> NovelState:
    """深度审查"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1) - 1
    kb = KnowledgeBaseService(project_id)

    # 读取审查所需数据
    timeline = kb.get_timeline(chapter_range=(max(1, current_chapter - 4), current_chapter))
    world_setting = kb.get_world_setting()
    outline = kb.get_outline()
    foreshadowings = kb.get_foreshadowings()
    snapshots = kb.get_style_snapshots(last_n=10)

    # 格式化
    timeline_text = "\n".join([f"第{t.chapter_number}章：{t.summary} [{t.emotion_tag}]" for t in timeline])
    setting_text = world_setting.core_concept if world_setting else ""
    outline_text = outline.summary if outline else ""
    foreshadowing_text = "\n".join([f"- {f.content}（{f.level}/{f.status}）" for f in foreshadowings])
    stats_text = "\n".join([f"第{s.chapter_number}章：对话{s.dialogue_ratio:.0%} 句长{s.avg_sentence_length:.0f}" for s in snapshots])

    llm = await get_llm_from_state_async(state)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, "deep_review")

    if user_template:
        prompt_text = safe_format(user_template,
            timeline_entries=timeline_text,
            world_setting=setting_text,
            outline=outline_text,
            foreshadowings=foreshadowing_text,
            style_stats=stats_text,
        )
    else:
        prompt_text = safe_format(DEEP_REVIEW_PROMPT,
            timeline_entries=timeline_text,
            world_setting=setting_text,
            outline=outline_text,
            foreshadowings=foreshadowing_text,
            style_stats=stats_text,
        )

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.2):
        response += chunk

    # 审查结果不存入 state，由主 Agent 决定是否修改
    return {
        **state,
        "last_review_chapter": current_chapter,
    }
