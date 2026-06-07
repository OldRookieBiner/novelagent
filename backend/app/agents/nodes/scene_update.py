"""场景清单更新节点

更新场景清单 + 时间线压缩 + 标记待索引内容。
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.nodes.utils import find_chapter_by_number


async def scene_update_node(state: NovelState) -> NovelState:
    """更新场景清单等"""
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # 找到刚写完的章节
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        return {}

    content = chapter.get("content", "")
    written_chapter_num = chapter.get("chapter_number", current_chapter - 1)

    if not content:
        return {}

    # 更新场景清单（整章作为一个场景条目）
    kb.create_scene_entry({
        "chapter_number": written_chapter_num,
        "scene_index": 1,
        "location": "",
        "scene_description": content[:200] + "..." if len(content) > 200 else content,
        "characters_present": [],
        "mood": "",
        "key_events": [],
    })

    return {}
