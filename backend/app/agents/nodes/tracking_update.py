"""追踪数据更新节点

追加时间线 + 更新伏笔表 + 更新问题链 + 更新支线网络。
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.nodes.utils import find_chapter_by_number


async def tracking_update_node(state: NovelState) -> NovelState:
    """更新追踪数据（时间线/伏笔/问题链/支线）"""
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)

    # 找到刚写完的章节
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        return {**state}

    written_chapter_num = chapter.get("chapter_number", current_chapter - 1)
    content = chapter.get("content", "")
    kb = KnowledgeBaseService(project_id)

    # 1. 追加时间线条目
    summary = content[:200] + "..." if len(content) > 200 else content
    kb.create_timeline_entry({
        "chapter_number": written_chapter_num,
        "summary": summary,
        "causal_chain": "",
        "rhythm_score": 3,
        "tension_score": 3,
        "emotion_score": 3,
        "emotion_tag": "未标注",
    })

    # 2. 更新伏笔表（检查已有伏笔是否在本章提及）
    active_foreshadowings = kb.get_foreshadowings(status="active")
    for f in active_foreshadowings:
        if f.content[:10] in content:
            new_count = f.appearance_count + 1
            new_level = "strengthened" if new_count >= 2 and f.level == "hint" else f.level
            new_status = "pending_reclaim" if new_level == "strengthened" else f.status
            kb.update_foreshadowing(f.id, {
                "appearance_count": new_count,
                "level": new_level,
                "status": new_status,
            })

    # 3. 更新问题链（标记当前章节回答的问题）
    pending_questions = kb.get_plot_questions(status="pending")
    for q in pending_questions[:1]:
        kb.update_plot_question(q.id, {
            "status": "answered",
            "answered_in_chapter": written_chapter_num,
        })

    return {**state}
