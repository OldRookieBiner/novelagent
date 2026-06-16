"""写作方向建议工具（合并版）

合并原 suggest_foreshadowing、suggest_plot_twist、writer_block_assist 三工具。
通过 focus 参数选择建议方向：
  - "block"：克服写作瓶颈
  - "foreshadowing"：伏笔放置建议
  - "twist"：情节反转建议
  - "auto"：自动选择最紧迫的方向（默认）
"""

from langchain_core.tools import tool

from app.agents.tools.utils import _kb
from app.utils.text import tokenize_chinese


@tool
async def suggest_writing_direction(
    current_chapter: int,
    focus: str = "auto",
) -> dict:
    """提供写作方向建议。支持三种聚焦模式。

    - focus="block"：克服写作瓶颈，提供 2-3 个写作方向
    - focus="foreshadowing"：基于情节和伏笔状态，建议伏笔放置位置
    - focus="twist"：基于节奏曲线和角色弧线，建议情节反转方向
    - focus="auto"：自动选择最紧迫的方向（默认）

    Args:
        current_chapter: 当前章节号
        focus: 聚焦模式 - "block"(写作瓶颈), "foreshadowing"(伏笔建议), "twist"(反转建议), "auto"(自动选择)
    """
    if focus not in ("block", "foreshadowing", "twist", "auto"):
        return {"error": f"focus 必须是 block/foreshadowing/twist/auto 之一，收到: {focus}"}

    if focus == "auto":
        focus = _auto_select_focus(current_chapter)

    if focus == "block":
        return await _suggest_block(current_chapter)
    elif focus == "foreshadowing":
        return await _suggest_foreshadowing(current_chapter)
    else:
        return await _suggest_twist(current_chapter)


def _auto_select_focus(current_chapter: int) -> str:
    """自动选择最紧迫的建议方向"""
    try:
        kb = _kb()
        overdue = kb.foreshadowings.list_overdue(current_chapter)
        if overdue:
            return "foreshadowing"

        timeline = kb.timelines.list_timeline()
        if timeline:
            recent = timeline[:5]
            avg_tension = sum(t.get("tension_score", 3) for t in recent) / max(len(recent), 1)
            if avg_tension < 2.5:
                return "twist"

        return "block"
    except Exception:
        return "block"


async def _suggest_block(current_chapter: int) -> dict:
    """克服写作瓶颈（原 writer_block_assist 逻辑）"""
    kb = _kb()

    pending = kb.foreshadowings.list_pending()
    overdue = kb.foreshadowings.list_overdue(current_chapter)
    questions = kb.plots.get_questions_for_chapter(current_chapter)
    block = kb.plots.get_current_plot_block(current_chapter)

    suggestions = []

    if overdue:
        f = overdue[0]
        content_preview = f.get("content", "")[:50]
        suggestions.append({
            "direction": "回收超期伏笔",
            "detail": f"伏笔「{content_preview}」已超过预期回收章节，可以在本章回收",
            "foreshadowing_id": f["id"],
        })

    if questions:
        q = questions[0]
        question_preview = q.get("question_text", "")[:50]
        suggestions.append({
            "direction": "回答待解问题",
            "detail": f"问题「{question_preview}」可以在本章回答",
            "question_id": q["id"],
        })

    if block:
        must_happen = block.get("must_happen") or []
        if must_happen:
            block_title = block.get("title", "")
            suggestions.append({
                "direction": "推进情节块",
                "detail": f"当前情节块「{block_title}」必须事件：{must_happen[0][:50] if must_happen else '无'}",
                "plot_block_id": block["id"],
            })

    if not suggestions:
        suggestions.append({
            "direction": "自由发挥",
            "detail": "当前没有紧迫的伏笔或问题链需要处理，可以自由推进剧情",
        })

    return {
        "focus": "block",
        "current_chapter": current_chapter,
        "suggestions": suggestions,
        "pending_foreshadowings": len(pending),
        "pending_questions": len(questions),
    }


async def _suggest_foreshadowing(current_chapter: int) -> dict:
    """伏笔放置建议（原 suggest_foreshadowing 逻辑）"""
    kb = _kb()

    block = kb.plots.get_current_plot_block(current_chapter)
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    active = [f for f in foreshadowings if f.get("status") in ("active", "pending_reclaim")]

    if not block:
        return {"focus": "foreshadowing", "suggestion": "当前没有情节块信息，建议先完成结构设计"}

    suggestions = []
    for question in (block.get("questions_to_raise") or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
            "reasoning": f"此问题是当前情节块需要提出的关键问题，在提出前埋下伏笔可以增加悬念",
        })

    if len(active) < 3 and block.get("chapter_end") and block.get("chapter_start"):
        span = block["chapter_end"] - block["chapter_start"]
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
                "reasoning": "长情节块中伏笔密度不足会导致读者缺乏悬念感，建议每 2-3 章至少有 1 个活跃伏笔",
            })

    # 未解释现象扫描
    unexplained = []
    recent_chapters = []
    for ch_offset in range(3):
        ch_num = current_chapter - ch_offset
        if ch_num > 0:
            ch = kb.chapters.get_by_number(ch_num)
            if ch and ch.get("content"):
                recent_chapters.append((ch_num, ch["content"]))

    if recent_chapters:
        tracked_contents = set()
        for f in active:
            content = f.get("content", "")
            if content:
                for word in content.split("，")[:3]:
                    if len(word) >= 2:
                        tracked_contents.add(word)

        word_freq = {}
        for ch_num, content in recent_chapters:
            tokens = tokenize_chinese(content)
            for token in tokens:
                if len(token) >= 3:
                    word_freq[token] = word_freq.get(token, 0) + 1

        for word, freq in sorted(word_freq.items(), key=lambda x: -x[1]):
            if freq >= 2 and word not in tracked_contents:
                unexplained.append({"element": word, "occurrences": freq})
                if len(unexplained) >= 3:
                    break

        for ue in unexplained:
            suggestions.append({
                "type": "未解释现象",
                "content": f"「{ue['element']}」在最近章节出现了 {ue['occurrences']} 次但未被追踪为伏笔",
                "reasoning": f"反复出现的元素适合作为伏笔对象——读者会自然期待它有意义，将其正式纳入伏笔追踪体系可以增强叙事一致性",
            })

    return {
        "focus": "foreshadowing",
        "current_chapter": current_chapter,
        "plot_block": block.get("title") if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }


async def _suggest_twist(current_chapter: int) -> dict:
    """情节反转建议（原 suggest_plot_twist 逻辑）"""
    kb = _kb()

    timeline = kb.timelines.list_timeline()
    foreshadowings = kb.foreshadowings.list_foreshadowings(status="active")
    characters = kb.characters.list_characters()
    block = kb.plots.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.get("tension_score"):
                recent_tension.append(t["tension_score"])

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    # 1. 节奏驱动反转
    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    # 2. 伏笔误导
    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f["id"] for f in foreshadowings[:3]],
        })

    # 3. 多角色分析
    main_chars = [c for c in characters if c.get("role") in ("主角", "核心反派", "重要配角")]
    for c in main_chars[:3]:
        core_mot = c.get("core_motivation", "")
        deep_fear = c.get("deep_fear", "")
        growth_arc = c.get("growth_arc", "")
        if core_mot or deep_fear:
            twist_direction = ""
            if deep_fear and growth_arc:
                twist_direction = f"让「{c['name']}」的成长弧线突然受挫——其深层恐惧「{deep_fear[:20]}」被触发，迫使面对最不想面对的处境"
            elif core_mot:
                twist_direction = f"揭示「{c['name']}」的真正动机与表面不同——核心动机「{core_mot[:20]}」背后隐藏更深的目的"
            if twist_direction:
                twist_types.append({
                    "type": "角色反转",
                    "character_id": c["id"],
                    "character_name": c["name"],
                    "character_role": c.get("role", ""),
                    "direction": twist_direction,
                })

    # 4. 读者预期反转
    for f in foreshadowings[:3]:
        content = f.get("content", "")
        expected_resolve = f.get("expected_resolve_chapter")
        if content and expected_resolve and expected_resolve > current_chapter:
            twist_types.append({
                "type": "读者预期反转",
                "foreshadowing_id": f["id"],
                "foreshadowing_preview": content[:60],
                "direction": f"伏笔「{content[:30]}」引导读者期待一个方向，实际揭示时走向相反方向——制造意外但合理的效果",
            })

    return {
        "focus": "twist",
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:5],
    }
