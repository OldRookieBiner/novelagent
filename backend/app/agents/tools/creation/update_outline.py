"""更新总纲工具 — 允许直接修改已确认的大纲"""

import logging

from langchain_core.tools import tool

from app.agents.tools.utils import _kb, parse_json_param

logger = logging.getLogger(__name__)


# 允许 Agent 修改的总纲字段白名单 — 防止幻影参数通过 setattr 静默写入 ORM
_ALLOWED_FIELDS = {
    "title", "summary", "plot_points", "characters",
    "world_setting", "emotional_curve",
}

# 需要按 JSON 解析的字段（工具入参为字符串，便于 LLM 传参）
_JSON_FIELDS = {"plot_points", "characters", "world_setting", "emotional_curve"}


@tool
async def update_outline(
    title: str | None = None,
    summary: str | None = None,
    plot_points: str | None = None,
    characters: str | None = None,
    world_setting: str | None = None,
    emotional_curve: str | None = None,
) -> dict:
    """直接修改项目总纲（标题/摘要/情节要点/角色概要/世界观/情感曲线）。

    适用于作者要求调整已确认大纲的内容，且改动明确、无需影响评估时。
    仅传入需要修改的字段，未传字段保持不变。若改动涉及大量章节、伏笔或情节块，
    需评估连带影响，请改用 propose_outline_adjustment。

    Args:
        title: 新标题
        summary: 新故事摘要
        plot_points: JSON 字符串列表，关键情节节点
        characters: JSON 字符串列表，主要角色概要
        world_setting: JSON 字符串对象，世界观设定
        emotional_curve: JSON 字符串列表，情感曲线
    """
    kb = _kb()

    outline = kb.outlines.get()
    if not outline:
        return {"error": "项目大纲不存在，请先生成大纲"}

    raw_inputs = {
        "title": title,
        "summary": summary,
        "plot_points": plot_points,
        "characters": characters,
        "world_setting": world_setting,
        "emotional_curve": emotional_curve,
    }

    updates: dict = {}
    warnings: list[str] = []
    for field, value in raw_inputs.items():
        if value is None:
            continue
        if field not in _ALLOWED_FIELDS:
            continue
        if field in _JSON_FIELDS:
            default = {} if field == "world_setting" else []
            parsed, warn = parse_json_param(value, default, field)
            if warn:
                warnings.append(warn)
            updates[field] = parsed
        else:
            updates[field] = value

    if not updates:
        return {"error": "未提供任何可修改的字段"}

    try:
        kb.outlines.update(updates)
    except Exception as e:
        logger.error("更新总纲失败: %s", e)
        return {"error": f"更新总纲失败: {str(e)}"}

    result = {
        "action": "updated",
        "updated_fields": list(updates.keys()),
        "message": f"总纲已更新：{', '.join(updates.keys())}",
    }
    if warnings:
        result["warnings"] = warnings
    return result
