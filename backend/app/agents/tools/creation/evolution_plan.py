"""创建关系演变规划工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def create_evolution_plan(
    relation_id: int,
    trigger_chapter: int,
    event_description: str,
    status_before: str = "",
    status_after: str = "",
    trust_before: int = -1,
    trust_after: int = -1,
) -> dict:
    """为角色关系创建演变规划。

    当用户需要规划两个角色之间关系的发展变化时使用。定义关系如何随情节推进而演变。

    Args:
            relation_id: 要添加演变计划的关系 ID
            trigger_chapter: 触发演变的章节号
            event_description: 触发演变的事件描述
            status_before: 事件前的关系状态（可选）
            status_after: 事件后的关系状态（可选）
            trust_before: 事件前信任等级（0-100，可选，-1 跳过）
            trust_after: 事件后信任等级（0-100，可选，-1 跳过）
    """
    kb = _kb()

    kwargs = {
        "relation_id": relation_id,
        "trigger_chapter": trigger_chapter,
        "event_description": event_description,
    }
    if status_before:
        kwargs["status_before"] = status_before
    if status_after:
        kwargs["status_after"] = status_after
    if trust_before >= 0:
        kwargs["trust_before"] = trust_before
    if trust_after >= 0:
        kwargs["trust_after"] = trust_after

    plan = kb.characters.create_evolution_plan(kwargs)
    return {
        "action": "created",
        "id": plan["id"],
        "relation_id": relation_id,
        "trigger_chapter": trigger_chapter,
        "message": f"关系演变规划已创建：第{trigger_chapter}章「{event_description[:30]}」",
    }
