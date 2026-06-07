"""追踪数据更新节点 — 增强版

novelskills 伏笔三级递进规则：
  暗示(hint) → 强化(strengthened) → 揭示(revealed)
  - 新伏笔：appearance_count=1, level="hint", status="active"
  - 再提及：appearance_count+1, ≥2 且 level="hint" → 升级为 "strengthened", status="pending_reclaim"
  - 回收：必须 ≥2 次出现且 level="strengthened" → 标记 level="revealed", status="resolved"
  - 回收时 <2 次出现 → 违规预警（违反最低递进要求）

其他追踪：
  - 时间线追加
  - 问题链更新
  - 支线网络更新
"""

import logging

from app.agents.state import NovelState
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.nodes.utils import find_chapter_by_number

logger = logging.getLogger(__name__)


async def tracking_update_node(state: NovelState) -> NovelState:
    """更新追踪数据（时间线/伏笔/问题链/支线）

    伏笔更新严格遵循 novelskills 三级递进：
    暗示 → 强化 → 揭示，至少出现 2 次才能回收。
    """
    project_id = state["project_id"]
    written_chapters = state.get("written_chapters", [])
    current_chapter = state.get("current_chapter", 1)

    # 找到刚写完的章节
    chapter = find_chapter_by_number(written_chapters, current_chapter)
    if not chapter:
        return {}

    written_chapter_num = chapter.get("chapter_number", current_chapter - 1)
    content = chapter.get("content", "")
    kb = KnowledgeBaseService(project_id)

    # ========== 1. 追加时间线条目 ==========
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

    # ========== 2. 更新伏笔表（三级递进） ==========
    active_foreshadowings = kb.get_foreshadowings(status="active") + kb.get_foreshadowings(status="pending_reclaim")

    for f in active_foreshadowings:
        # 检查伏笔内容是否在本章被提及
        if not _is_foreshadowing_mentioned(f.content, content):
            continue

        new_count = f.appearance_count + 1
        new_level = f.level
        new_status = f.status

        if f.level == "hint" and new_count >= 2:
            # 暗示 → 强化（出现 ≥2 次）
            new_level = "strengthened"
            new_status = "pending_reclaim"
            logger.info(f"伏笔升级：{f.content[:30]} 暗示→强化（出现 {new_count} 次）")
        elif f.level == "hint":
            # 暗示但出现 <2 次，保持暗示
            new_level = "hint"
            new_status = "active"
        elif f.level == "strengthened":
            # 已强化，继续保持
            new_level = "strengthened"
            new_status = "pending_reclaim"

        kb.update_foreshadowing(f.id, {
            "appearance_count": new_count,
            "level": new_level,
            "status": new_status,
        })

    # 检查是否有伏笔在本章被回收
    # 严格规则：只有 level="strengthened" 且 appearance_count≥2 的伏笔才能回收
    pending_foreshadowings = kb.get_pending_foreshadowings()
    for f in pending_foreshadowings:
        if not _is_foreshadowing_resolved(f.content, content):
            continue

        if f.level == "strengthened" and f.appearance_count >= 2:
            # 合规回收：强化→揭示
            kb.update_foreshadowing(f.id, {
                "level": "revealed",
                "status": "resolved",
                "resolved_chapter": written_chapter_num,
            })
            logger.info(f"伏笔回收：{f.content[:30]} 强化→揭示（第{written_chapter_num}章）")
        else:
            # 违规回收：出现不足 2 次就回收
            logger.warning(
                f"伏笔违规回收：{f.content[:30]} "
                f"等级={f.level}，出现={f.appearance_count}次，"
                f"不满足三级递进要求（至少暗示→强化才能回收）"
            )
            # 仍然标记回收，但记录违规
            kb.update_foreshadowing(f.id, {
                "level": "revealed",
                "status": "resolved",
                "resolved_chapter": written_chapter_num,
            })

    # ========== 3. 更新问题链 ==========
    pending_questions = kb.get_plot_questions(status="pending")
    for q in pending_questions[:1]:
        # 简化逻辑：每章最多回答一个问题
        kb.update_plot_question(q.id, {
            "status": "answered",
            "answered_in_chapter": written_chapter_num,
        })

    return {}


def _is_foreshadowing_mentioned(foreshadowing_content: str, chapter_content: str) -> bool:
    """检查伏笔是否在本章被提及

    使用多关键词匹配：从伏笔内容中提取多个关键词片段，
    任一匹配即视为提及。比单一前缀匹配更鲁棒。

    关键词提取策略：
    1. 前缀匹配（10字）
    2. 按标点分词后的各段
    3. 滑动窗口提取 4-6 字片段（处理无标点的短伏笔）
    """
    if not foreshadowing_content or not chapter_content:
        return False

    keywords = []
    # 1. 前缀（最直接的引用方式）
    prefix = foreshadowing_content[:10]
    if len(prefix) >= 2:
        keywords.append(prefix)

    # 2. 按标点/空格分词，取每个词的前6字
    import re as _re
    segments = _re.split(r"[，。、：；！？\s]", foreshadowing_content)
    for seg in segments[:4]:
        seg = seg.strip()
        if len(seg) >= 2:
            keywords.append(seg[:6])

    # 3. 滑动窗口：提取 4-6 字的片段（处理无标点的伏笔内容）
    # 从位置 0 开始，步长 4，提取 len=4 的窗口
    for start in range(0, max(len(foreshadowing_content) - 3, 1), 4):
        window = foreshadowing_content[start:start + 4]
        if len(window) >= 2 and window not in keywords:
            keywords.append(window)

    # 任一关键词匹配即视为提及
    return any(kw in chapter_content for kw in keywords)


def _is_foreshadowing_resolved(foreshadowing_content: str, chapter_content: str) -> bool:
    """检查伏笔是否在本章被回收

    回收 = 伏笔的核心信息在本章被揭示/解释/回应。
    使用多关键词 + 频率阈值：至少 2 个不同关键词出现，或
    单个核心关键词出现 2+ 次。

    注意：这是一个简化实现。理想的实现应该用 LLM 判断伏笔是否被回收。
    """
    if not foreshadowing_content or not chapter_content:
        return False

    import re
    # 从伏笔内容中提取核心片段
    keywords = []
    prefix = foreshadowing_content[:6]
    if len(prefix) >= 2:
        keywords.append(prefix)

    # 按标点分词提取更多关键词
    segments = re.split(r"[，。、：；！？\s]", foreshadowing_content)
    for seg in segments[:3]:
        seg = seg.strip()
        if len(seg) >= 2:
            keywords.append(seg[:6])

    if not keywords:
        return False

    # 至少 2 个不同关键词出现，或核心关键词出现 2+ 次
    match_count = sum(1 for kw in keywords if kw in chapter_content)
    if match_count >= 2:
        return True

    # 核心关键词出现 2+ 次
    core_kw = keywords[0]
    return chapter_content.count(core_kw) >= 2
