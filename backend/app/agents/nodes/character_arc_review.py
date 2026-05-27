"""角色弧与风格一致性检查节点

Phase 4 增强：支持逐卷修订和全书修订两种范围。
- per_volume：当前卷角色弧验证 + 风格检查 + 卷首衔接检查
- full_book：全书角色弧验证 + 跨卷状态跳变检测 + 逐卷风格一致性

LangGraph 签名：(state: NovelState) -> NovelState
"""

import logging

from app.agents.state import NovelState, RevisionContext
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.prompts import (
    CHARACTER_ARC_REVIEW_PROMPT,
    PER_VOLUME_CHARACTER_ARC_REVIEW_PROMPT,
    FULL_BOOK_CHARACTER_ARC_REVIEW_PROMPT,
)
from app.utils.llm import get_llm_from_state_async
from app.agents.nodes.utils import get_prompts_from_state, safe_format

logger = logging.getLogger(__name__)


async def character_arc_review_node(state: NovelState) -> NovelState:
    """角色弧验证 + 风格一致性检查

    根据 revision_context 决定审查范围：
    - per_volume：当前卷角色弧、风格、卷首衔接
    - full_book：全书角色弧、跨卷状态跳变、逐卷风格
    """
    project_id = state["project_id"]
    current_volume = state.get("current_volume", 1)
    revision_context = state.get("revision_context")
    kb = KnowledgeBaseService(project_id)

    # 收集通用数据
    characters = kb.get_characters()
    style = kb.get_style_constraints()
    snapshots = kb.get_style_snapshots()

    chars_text = "\n".join([f"- {c.name}：弧线={c.growth_arc or '未设定'}" for c in characters]) or "无"
    style_text = f"禁忌词：{style.taboo_words}" if style and style.taboo_words else "无"
    stats_text = "\n".join([f"第{s.chapter_number}章：对话{s.dialogue_ratio:.0%}" for s in snapshots[-10:]]) or "无"

    # 选择 prompt 模板
    if revision_context == RevisionContext.PER_VOLUME.value:
        prompt_key = "per_volume_character_arc_review"
        default_prompt = PER_VOLUME_CHARACTER_ARC_REVIEW_PROMPT

        format_kwargs = {
            "volume_number": current_volume,
            "characters": chars_text,
            "style_constraints": style_text,
            "style_stats": stats_text,
        }
    else:
        prompt_key = "full_book_character_arc_review"
        default_prompt = FULL_BOOK_CHARACTER_ARC_REVIEW_PROMPT

        # 跨卷数据
        volumes = kb.get_volumes()
        total_volumes = len(volumes) if volumes else 1

        # 角色变化日志
        ccl = kb.get_character_change_logs()
        ccl_text = "\n".join([f"- 第{l.volume_number}卷 角色#{l.character_id}：{str(l.changes)[:80]}" for l in ccl[:10]]) or "无"

        # 卷边界角色快照
        vol_snaps = []
        for v in (volumes or []):
            if v.character_snapshot:
                chars = [f"{c.get('name','?')}(弧线:{c.get('growth_arc','?')})" for c in v.character_snapshot[:5]]
                vol_snaps.append(f"第{v.volume_number}卷: {', '.join(chars)}")
        vol_snap_text = "\n".join(vol_snaps) or "无"

        format_kwargs = {
            "total_volumes": total_volumes,
            "characters": chars_text,
            "style_constraints": style_text,
            "style_stats": stats_text,
            "character_change_logs": ccl_text,
            "volume_snapshots": vol_snap_text,
        }

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

    return {**state}
