"""弧纲生成节点 — 为长篇小说的每个弧生成详细概要"""

import logging
from typing import Optional

from app.agents.state import NovelState, STAGE_ARC_OUTLINES

logger = logging.getLogger(__name__)


def _build_arc_outline_messages(
    state: NovelState,
    arc: dict,
    generated_outlines: list[dict],
) -> list[dict]:
    """构建弧纲生成的 LLM 消息

    Args:
        state: 工作流状态
        arc: 当前弧数据 {arc_number, title, chapter_count, volume_number, ...}
        generated_outlines: 已生成的其他弧纲 [{arc_number, outline}]

    Returns:
        LLM 消息列表
    """
    from app.agents.prompts import DEFAULT_PROMPTS
    from app.agents.nodes.utils import format_characters_info

    prompts = state.get("_prompts", DEFAULT_PROMPTS)
    prompt_template = prompts.get("arc_outline_generation", DEFAULT_PROMPTS["arc_outline_generation"])

    # 大纲信息
    outline_title = state.get("outline_title", "")
    outline_summary = state.get("outline_summary", "")
    plot_points = state.get("outline_plot_points", [])
    plot_text = "\n".join(f"{i+1}. {p.get('event', '')}" for i, p in enumerate(plot_points)) if plot_points else "无"

    # 角色信息
    characters_str = format_characters_info(state)

    # 已生成弧纲（提供上下文连贯性）
    other_arcs_info = ""
    if generated_outlines:
        parts = []
        for go in generated_outlines:
            parts.append(f"第{go['arc_number']}弧概要：{go['outline'][:200]}...")
        other_arcs_info = "已生成弧纲（供参考，保持连贯）：\n" + "\n".join(parts)

    prompt = prompt_template.format(
        outline_title=outline_title,
        outline_summary=outline_summary or "",
        plot_points=plot_text,
        characters=characters_str,
        arc_number=arc.get("arc_number", 1),
        arc_title=arc.get("title", "未命名"),
        arc_count=arc.get("chapter_count", 10),
        volume_number=arc.get("volume_number", 1),
        other_arcs_info=other_arcs_info,
    )

    return [{"role": "user", "content": prompt}]


async def arc_outline_generation_node(state: NovelState) -> dict:
    """弧纲生成节点

    逐弧流式生成弧纲，通过 get_stream_writer() 发送结构化流式事件。
    生成完成后暂停等待确认。

    自定义事件：
        arc_outline_chunk: {content: str, arc_index: int} — 流式文本
        arc_outline_done: {arc_index: int, outline: str, arc_number: int} — 单弧纲完成

    Returns:
        更新后的 NovelState 片段
    """
    from langgraph.config import get_stream_writer
    from app.utils.llm import get_llm_from_state_async

    llm = await get_llm_from_state_async(state)
    writer = get_stream_writer()
    arcs = state.get("arcs", [])
    generated_outlines = []

    for i, arc in enumerate(arcs):
        messages = _build_arc_outline_messages(state, arc, generated_outlines)

        # 流式生成弧纲
        full_text = ""
        async for chunk in llm.chat_stream(messages):
            full_text += chunk
            # 发送流式文本事件
            writer({
                "type": "arc_outline_chunk",
                "content": chunk,
                "arc_index": i,
            })

        # 发送单弧完成事件
        writer({
            "type": "arc_outline_done",
            "arc_index": i,
            "outline": full_text,
            "arc_number": arc.get("arc_number", i + 1),
        })

        # 更新弧数据中的 outline
        arc["outline"] = full_text
        generated_outlines.append({
            "arc_number": arc.get("arc_number", i + 1),
            "outline": full_text,
        })

    return {
        **state,
        "arcs": arcs,
        "stage": STAGE_ARC_OUTLINES,
        "waiting_for_confirmation": True,
        "confirmation_type": "arc_outlines",
    }
