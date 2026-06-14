"""生成章节大纲工具"""
import logging

from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.tools.utils import _kb, parse_json_param

logger = logging.getLogger(__name__)


@tool
async def generate_chapter_outline(
    chapter_number: int,
    title: str,
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
) -> dict:
    """生成或更新特定章节的大纲。

    当用户需要为某一章创建写作大纲时使用。大纲包含场景、角色、情绪弧线等写作指导信息。

    Args:
            chapter_number: 章节号
            title: 章节标题
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
    """
    scenes, scenes_warn = parse_json_param(key_scenes, [], "key_scenes")

    project_id = get_project_id()
    kb = _kb()

    existing = kb.outlines.get_chapter_outline(chapter_number)

    if existing:
        # 更新现有大纲
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
        # 创建新大纲
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
