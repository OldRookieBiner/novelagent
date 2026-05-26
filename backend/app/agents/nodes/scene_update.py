"""场景清单更新节点

更新场景清单 + 时间线压缩 + 标记待索引内容。
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService


async def scene_update_node(state: NovelState) -> NovelState:
    """更新场景清单等"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1) - 1
    kb = KnowledgeBaseService(project_id)

    # 获取刚写的章节
    written = state.get("written_chapters", [])
    content = ""
    for ch in written:
        if ch.get("chapter_number") == current_chapter:
            content = ch.get("content", "")
            break

    if not content:
        return {**state}

    # 更新场景清单（简化：整章作为一个场景条目）
    kb.create_scene_entry({
        "chapter_number": current_chapter,
        "scene_description": content[:200] + "..." if len(content) > 200 else content,
        "characters_present": [],
    })

    return {**state}
