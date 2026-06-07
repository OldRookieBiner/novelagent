"""结构完整性检查节点

Phase 4 增强：支持逐卷修订和全书修订两种范围。
- revision_context == "per_volume"：仅审查当前卷
- revision_context == "full_book" 或 None：审查全书（含跨卷追踪）

LangGraph 签名：(state: NovelState) -> NovelState
"""

import logging

from app.agents.state import NovelState, Phase, RevisionContext
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import (
    STRUCTURAL_REVIEW_PROMPT,
    PER_VOLUME_STRUCTURAL_REVIEW_PROMPT,
    FULL_BOOK_STRUCTURAL_REVIEW_PROMPT,
)
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def structural_review_node(state: NovelState) -> NovelState:
    """结构完整性：伏笔闭环/问题链闭环/时间线一致性/支线闭环

    根据 revision_context 决定审查范围：
    - per_volume：当前卷内的伏笔、问题链、时间线、支线
    - full_book：全书范围 + 跨卷伏笔/支线/角色变化
    """
    project_id = state["project_id"]
    current_volume = state.get("current_volume", 1)
    revision_context = state.get("revision_context")
    kb = KnowledgeBaseService(project_id)

    # 选择 prompt 模板
    if revision_context == RevisionContext.PER_VOLUME.value:
        prompt_key = "per_volume_structural_review"
        default_prompt = PER_VOLUME_STRUCTURAL_REVIEW_PROMPT
    else:
        prompt_key = "full_book_structural_review"
        default_prompt = FULL_BOOK_STRUCTURAL_REVIEW_PROMPT

    # 收集审查数据
    foreshadowings = kb.get_foreshadowings()
    questions = kb.get_plot_questions()
    timeline = kb.get_timeline()
    subplots = kb.get_subplots()

    # 格式化通用数据
    fs_text = "\n".join([f"- {f.content[:60]}（{f.status}）" for f in foreshadowings]) or "无"
    q_text = "\n".join([f"- {q.question_text[:60]}（{q.status}）" for q in questions]) or "无"
    t_text = "\n".join([f"第{e.chapter_number}章：{e.summary[:80]}" for e in timeline[-10:]]) or "无"
    sp_text = "\n".join([f"- {s.name}（{s.current_status}）" for s in subplots]) or "无"

    # 格式化 prompt 参数
    format_kwargs = {
        "foreshadowings": fs_text,
        "plot_questions": q_text,
        "timeline": t_text,
        "subplots": sp_text,
    }

    if revision_context == RevisionContext.PER_VOLUME.value:
        # 逐卷修订：限定卷内范围
        volume = kb.get_volume(current_volume)
        chapter_start = volume.chapter_offset + 1 if volume else 1
        chapter_end = state.get("current_chapter", 1) - 1

        # 跨卷伏笔
        cvf = kb.get_cross_volume_foreshadowings(status="active")
        cvf_text = "\n".join([f"- 跨卷伏笔#{c.id}（出现{c.appearance_count}次，预期第{c.expected_volume}卷回收）" for c in cvf]) or "无"

        format_kwargs.update({
            "volume_number": current_volume,
            "chapter_start": chapter_start,
            "chapter_end": chapter_end,
            "cross_volume_foreshadowings": cvf_text,
        })
    else:
        # 全书修订：含跨卷追踪
        volumes = kb.get_volumes()
        total_volumes = len(volumes) if volumes else 1

        # 跨卷伏笔
        cvf = kb.get_cross_volume_foreshadowings()
        cvf_text = "\n".join([f"- 跨卷伏笔#{c.id}（状态：{c.status}，出现{c.appearance_count}次）" for c in cvf]) or "无"

        # 跨卷支线
        cvs = kb.get_cross_volume_subplots()
        cvs_text = "\n".join([f"- 跨卷支线#{c.id}（状态：{c.status}）" for c in cvs]) or "无"

        # 角色变化日志
        ccl = kb.get_character_change_logs()
        ccl_text = "\n".join([f"- 第{l.volume_number}卷 角色#{l.character_id}：{str(l.changes)[:80]}" for l in ccl[:10]]) or "无"

        # 各卷边界时间线
        vol_timeline = []
        for v in (volumes or []):
            if v.character_snapshot:
                chars = [f"{c.get('name','?')}" for c in v.character_snapshot[:5]]
                vol_timeline.append(f"第{v.volume_number}卷(offset={v.chapter_offset}): {', '.join(chars)}")
        vol_tl_text = "\n".join(vol_timeline) or "无"

        format_kwargs.update({
            "total_volumes": total_volumes,
            "cross_volume_foreshadowings": cvf_text,
            "cross_volume_subplots": cvs_text,
            "character_change_logs": ccl_text,
            "timeline": vol_tl_text,
        })

    # 调用 LLM
    llm = await get_llm_from_state_async(state, for_review=True)
    prompts = state.get("_prompts", {})
    _, user_template = get_prompts_from_state(prompts, prompt_key)

    if user_template:
        prompt_text = safe_format(user_template, **format_kwargs)
    else:
        prompt_text = safe_format(default_prompt, **format_kwargs)

    response = ""
    async for chunk in llm.chat_stream([{"role": "user", "content": prompt_text}], temperature=0.2):
        response += chunk

    return {"phase": Phase.REVISION.value}
