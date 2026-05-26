"""写后自检汇总节点

汇总所有自检结果，写入 state["post_write_summary"]。
"""

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService


async def post_write_summary_node(state: NovelState) -> NovelState:
    """汇总写后自检结果"""
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1) - 1
    kb = KnowledgeBaseService(project_id)

    # 读取最新追踪数据
    timeline = kb.get_timeline(chapter_range=(current_chapter, current_chapter))
    snapshots = kb.get_style_snapshots(last_n=1)
    overdue = kb.get_overdue_foreshadowings(current_chapter)

    # 生成摘要
    parts = [f"第{current_chapter}章写后自检："]
    if timeline:
        parts.append(f"  时间线：已更新")
    if snapshots:
        s = snapshots[0]
        parts.append(f"  风格：对话{s.dialogue_ratio:.0%}，句长{s.avg_sentence_length:.0f}字")
    if overdue:
        parts.append(f"  ⚠️ 超期伏笔：{len(overdue)}个")
    else:
        parts.append(f"  伏笔：无超期")

    summary = "\n".join(parts)

    return {
        **state,
        "post_write_summary": summary,
        "last_review_chapter": state.get("last_review_chapter", 0),
    }
