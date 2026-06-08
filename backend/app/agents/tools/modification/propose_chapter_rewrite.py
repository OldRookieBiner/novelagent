"""提议章节重写工具"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb


@tool
async def propose_chapter_rewrite(
    chapter_number: int,
    reason: str,
) -> dict:
    """Propose rewriting a specific chapter.

    Marks the old version and creates a proposal. Does not rewrite
    immediately — the author must approve.

    Args:
        chapter_number: The chapter to rewrite
        reason: Why the rewrite is needed (e.g., "审核不通过", "设定矛盾")
    """
    kb = _kb()
    chapter = kb.get_chapter_by_number(chapter_number)
    if not chapter:
        return {"error": f"第{chapter_number}章不存在"}
    old_content = chapter.content[:500] if chapter.content else ""
    chapter_id = chapter.id

    change = kb.create_setting_change({
        "target_type": "chapter_rewrite",
        "target_id": chapter_id,
        "old_value": {"chapter_number": chapter_number, "content_preview": old_content},
        "new_value": {"chapter_number": chapter_number, "reason": reason},
        "description": f"提议重写第{chapter_number}章：{reason}",
        "status": "proposed",
        "impact_report": {
            "level": "moderate",
            "affected_chapters": 1,
            "note": "重写章节会影响后续追踪数据（时间线、伏笔、风格统计），重写后需更新追踪文件",
        },
    })

    return {
        "change_id": change.id,
        "chapter_number": chapter_number,
        "status": "proposed",
        "reason": reason,
        "impact": "🟠 重写章节需更新追踪文件（时间线、伏笔、风格统计）",
        "next_steps": "作者确认后可执行重写",
    }
