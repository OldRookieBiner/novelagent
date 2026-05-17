"""弧/卷规划节点 — 长篇小说的结构规划"""

import logging
import re

from app.agents.state import NovelState, STAGE_VOLUME_ARC

logger = logging.getLogger(__name__)


def parse_volume_arc_plan(response: str, total_chapters: int) -> tuple[list[dict], list[dict]]:
    """解析 LLM 输出的弧/卷结构文本

    Args:
        response: LLM 完整文本输出
        total_chapters: 目标总章节数

    Returns:
        (volumes, arcs) 元组
    """
    volumes = []
    arcs = []
    current_volume_number = 0

    # 按行解析
    lines = response.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 匹配卷：卷N《卷名》
        vol_match = re.match(r"卷(\d+)《(.+?)》", line)
        if vol_match:
            current_volume_number = int(vol_match.group(1))
            vol_title = vol_match.group(2)
            volumes.append({
                "volume_number": current_volume_number,
                "title": vol_title,
                "summary": None,
            })
            i += 1
            continue

        # 匹配弧：弧N《弧名》：M章（全局递增编号）
        arc_match = re.match(r"弧(\d+)《(.+?)》[：:]\s*(\d+)\s*章", line)
        if arc_match:
            arc_number = int(arc_match.group(1))
            arc_title = arc_match.group(2)
            chapter_count = int(arc_match.group(3))
            arc_summary = None

            # 下一行可能是概要
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                summary_match = re.match(r"概要[：:]\s*(.+)", next_line)
                if summary_match:
                    arc_summary = summary_match.group(1)
                    i += 1

            arcs.append({
                "volume_number": current_volume_number,
                "arc_number": arc_number,
                "title": arc_title,
                "summary": arc_summary,
                "chapter_count": chapter_count,
            })
            i += 1
            continue

        i += 1

    # 校验总章节数偏差
    if arcs and total_chapters > 0:
        parsed_total = sum(a["chapter_count"] for a in arcs)
        if parsed_total == 0 or abs(parsed_total - total_chapters) / total_chapters > 0.2:
            # 偏差 >20%，按比例调整
            ratio = total_chapters / parsed_total if parsed_total > 0 else 1
            for a in arcs:
                a["chapter_count"] = max(1, round(a["chapter_count"] * ratio))
            logger.warning(
                f"Volume/arc plan chapter count adjusted: {parsed_total} → {total_chapters}"
            )

    return volumes, arcs


async def volume_arc_planning_node(state: NovelState) -> dict:
    """弧/卷规划节点

    长篇小说专属：根据大纲数据生成卷/弧划分。
    LLM 流式输出，完成后一次性解析。

    Returns:
        更新 volumes、arcs、chapter_count、stage、waiting_for_confirmation、confirmation_type
    """
    from app.utils.llm import get_llm_from_state_async
    from app.agents.prompts import DEFAULT_PROMPTS

    # 获取 LLM 服务
    llm = await get_llm_from_state_async(state)

    # 构建 prompt
    prompts = state.get("_prompts", DEFAULT_PROMPTS)
    prompt_template = prompts.get("volume_arc_generation", DEFAULT_PROMPTS["volume_arc_generation"])

    outline_title = state.get("outline_title", "")
    outline_summary = state.get("outline_summary", "")
    plot_points = state.get("outline_plot_points", [])
    world_setting = state.get("outline_world_setting", {})
    emotional_curve = state.get("outline_emotional_curve", "")
    chapter_count = state.get("chapter_count", 30)
    target_words = state.get("collected_info", {}).get("targetWords", 200000)

    # 格式化情节节点
    if isinstance(plot_points, list):
        plot_text = "\n".join(
            f"{p.get('order', i+1)}. {p.get('event', '')}"
            for i, p in enumerate(plot_points)
            if isinstance(p, dict)
        )
    else:
        plot_text = str(plot_points)

    prompt = prompt_template.format(
        outline_title=outline_title,
        outline_summary=outline_summary or "",
        plot_points=plot_text,
        world_setting=str(world_setting) if world_setting else "",
        emotional_curve=emotional_curve or "",
        total_chapters=chapter_count,
        target_words=target_words,
    )

    # 流式调用 LLM
    messages = [{"role": "user", "content": prompt}]
    response = ""
    async for chunk in llm.chat_stream(messages):
        response += chunk

    # 解析弧/卷结构
    volumes, arcs = parse_volume_arc_plan(response, chapter_count)

    # 解析失败防护：空 arcs 时清理 volumes 避免残留脏数据，不设等待确认让路由走 end
    if not arcs:
        logger.error("volume_arc_planning_node: failed to parse arcs from LLM output")
        return {
            **state,
            "volumes": [],
            "arcs": [],
            "stage": STAGE_VOLUME_ARC,
            "waiting_for_confirmation": False,
        }

    # 更新 chapter_count 为各弧章节数之和
    new_chapter_count = sum(a.get("chapter_count", 0) for a in arcs)

    return {
        **state,
        "volumes": volumes,
        "arcs": arcs,
        "chapter_count": new_chapter_count,
        "stage": STAGE_VOLUME_ARC,
        "waiting_for_confirmation": True,
        "confirmation_type": "volume_arc",
    }
