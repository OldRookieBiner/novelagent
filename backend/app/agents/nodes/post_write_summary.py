"""写后自检汇总节点

汇总所有自检结果，运行预警检查，写入 state["post_write_summary"]。
"""

import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.warning import WarningService
from app.agents.services.retrieval import RetrievalService

logger = logging.getLogger(__name__)


async def post_write_summary_node(state: NovelState) -> NovelState:
    """汇总写后自检结果 + 运行预警检查

    1. 读取最新追踪数据生成摘要
    2. 运行 WarningService.check_all() 检测质量信号
    3. 预警结果写入 state（供 SSE 推送）
    """
    project_id = state["project_id"]
    current_chapter = state.get("current_chapter", 1)
    kb = KnowledgeBaseService(project_id)

    # current_chapter 已在 chapter_writing_node 中递增 1，
    # 所以刚写完的章节号是 current_chapter - 1
    written_chapter_num = current_chapter - 1

    # 读取最新追踪数据
    timeline = kb.get_timeline(chapter_range=(written_chapter_num, written_chapter_num))
    snapshots = kb.get_style_snapshots(last_n=1)
    overdue = kb.get_overdue_foreshadowings(written_chapter_num)

    # 生成摘要
    parts = [f"第{written_chapter_num}章写后自检："]
    if timeline:
        parts.append("  时间线：已更新")
    if snapshots:
        s = snapshots[0]
        parts.append(f"  风格：对话{s.dialogue_ratio:.0%}，句长{s.avg_sentence_length:.0f}字")
    if overdue:
        parts.append(f"  ⚠️ 超期伏笔：{len(overdue)}个")
    else:
        parts.append("  伏笔：无超期")

    # ========== 预警检查 ==========
    warning_service = WarningService(project_id)
    warnings = warning_service.check_all(written_chapter_num)

    if warnings:
        parts.append(f"\n  预警：")
        for w in warnings:
            parts.append(f"    {w['emoji']} {w['title']}：{w['message']}")

    # ========== 每5章重建语义检索索引 ==========
    if written_chapter_num > 0 and written_chapter_num % 5 == 0:
        retrieval = RetrievalService(project_id)
        try:
            success = retrieval.rebuild_index()
            if success:
                parts.append(f"  检索索引：已重建")
            else:
                parts.append(f"  检索索引：重建失败（模型可能未就绪）")
        except Exception as e:
            logger.warning(f"检索索引重建失败: {e}")
            parts.append(f"  检索索引：重建失败")

    summary = "\n".join(parts)

    return {
        **state,
        "post_write_summary": summary,
    }
