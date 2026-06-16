"""生成章节大纲工具（合并版）

合并原 generate_chapter_outline 和 batch_confirm_outlines。
支持单条大纲生成和批量确认。
"""
import logging

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb, parse_json_param

logger = logging.getLogger(__name__)


@tool
async def generate_chapter_outline(
    chapter_number: int = 0,
    title: str = "",
    scene: str = "",
    characters: str = "",
    plot: str = "",
    conflict: str = "",
    turning_point: str = "",
    hook: str = "",
    transition: str = "",
    ending: str = "",
    target_words: int = 3000,
    opening_state: str = "",
    emotional_arc: str = "",
    key_scenes: str = "[]",
    pacing_note: str = "",
    batch_chapter_numbers: str = "",
) -> dict:
    """生成或更新章节大纲，或批量确认大纲。

    - 提供chapter_number+title时：生成/更新单条大纲
    - 提供batch_chapter_numbers时：批量确认指定章节的大纲（如 "[1,2,3]"）

    Args:
        chapter_number: 章节号（单条模式）
        title: 章节标题（单条模式）
        scene: 场景设定
        characters: 出场角色
        plot: 关键情节点
        conflict: 主要冲突
        turning_point: 转折点
        hook: 章末悬念钩子
        transition: 到下一章的过渡
        ending: 章节结尾描写
        target_words: 目标字数（默认 3000）
        opening_state: 章节开场状态
        emotional_arc: 情感轨迹
        key_scenes: JSON 字符串列表，关键场景
        pacing_note: 节奏指引
        batch_chapter_numbers: JSON 字符串列表，批量确认的章节号（如 "[1,2,3]"）
    """
    # 批量确认模式
    if batch_chapter_numbers:
        return _batch_confirm(batch_chapter_numbers)

    # 单条大纲模式
    if not chapter_number or not title:
        return {"error": "单条模式需要提供 chapter_number 和 title"}

    scenes, scenes_warn = parse_json_param(key_scenes, [], "key_scenes")

    project_id = get_project_id()
    kb = _kb()

    existing = kb.outlines.get_chapter_outline(chapter_number)

    if existing:
        update_data = {"title": title, "confirmed": False}
        if scene:
            update_data["scene"] = scene
        if characters:
            update_data["characters"] = characters
        if plot:
            update_data["plot"] = plot
        if conflict:
            update_data["conflict"] = conflict
        if turning_point:
            update_data["turning_point"] = turning_point
        if hook:
            update_data["hook"] = hook
        if transition:
            update_data["transition"] = transition
        if ending:
            update_data["ending"] = ending
        update_data["target_words"] = target_words
        if opening_state:
            update_data["opening_state"] = opening_state
        if emotional_arc:
            update_data["emotional_arc"] = emotional_arc
        if scenes:
            update_data["key_scenes"] = scenes
        if pacing_note:
            update_data["pacing_note"] = pacing_note
        kb.outlines.update_chapter_outline(chapter_number, update_data)
        action = "updated"
    else:
        data = {
            "chapter_number": chapter_number,
            "title": title,
            "target_words": target_words,
            "confirmed": False,
        }
        if scene:
            data["scene"] = scene
        if characters:
            data["characters"] = characters
        if plot:
            data["plot"] = plot
        if conflict:
            data["conflict"] = conflict
        if turning_point:
            data["turning_point"] = turning_point
        if hook:
            data["hook"] = hook
        if transition:
            data["transition"] = transition
        if ending:
            data["ending"] = ending
        if opening_state:
            data["opening_state"] = opening_state
        if emotional_arc:
            data["emotional_arc"] = emotional_arc
        if scenes:
            data["key_scenes"] = scenes
        if pacing_note:
            data["pacing_note"] = pacing_note
        kb.outlines.create_chapter_outline(data)
        action = "created"

    return {
        "action": action,
        "chapter_number": chapter_number,
        "title": title,
        "confirmed": False,
        "message": f"第{chapter_number}章「{title}」大纲已{action}，请审查后确认",
    }


def _batch_confirm(batch_chapter_numbers: str) -> dict:
    """批量确认章节大纲"""
    kb = _kb()

    nums, warn = parse_json_param(batch_chapter_numbers, [], "batch_chapter_numbers")
    if warn:
        return {"error": f"batch_chapter_numbers 参数解析失败: {warn}"}

    if not nums:
        return {"error": "batch_chapter_numbers 不能为空"}

    confirmed = []
    not_found = []
    already_confirmed = []
    errors = []

    for ch_num in nums:
        try:
            outline = kb.outlines.get_chapter_outline(ch_num)
            if not outline:
                not_found.append(ch_num)
            elif outline.get("confirmed"):
                already_confirmed.append(ch_num)
            else:
                kb.outlines.update_chapter_outline(ch_num, {"confirmed": True})
                confirmed.append(ch_num)
        except Exception as e:
            errors.append({"chapter_number": ch_num, "error": str(e)})

    result = {
        "confirmed": confirmed,
        "already_confirmed": already_confirmed,
        "not_found": not_found,
        "errors": errors,
        "total_requested": len(nums),
        "total_confirmed": len(confirmed),
        "message": f"已确认 {len(confirmed)} 个章节大纲" if confirmed else "没有新的章节大纲需要确认",
    }
    if not_found:
        result["hint"] = f"章节 {not_found} 大纲不存在，请先用 generate_chapter_outline 创建"
    return result
