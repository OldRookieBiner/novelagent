"""Cognitive tools for the Free Operation Agent (ReAct)

Three categories:
1. Perception (6) — read-only queries about the knowledge base
2. Modification (3) — propose changes with automatic impact assessment
3. Creation Assist (4) — help the author with creative decisions

All tools use KnowledgeBaseService (shared with the main writing loop)
via project_id from tool_context. No tool manages its own DB session.
"""

import json
from langchain_core.tools import tool

from app.agents.tool_context import get_project_id
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.retrieval import RetrievalService


def _kb() -> KnowledgeBaseService:
    """Get KnowledgeBaseService for the current project context.

    Raises ValueError if project_id is not set in tool_context.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")
    return KnowledgeBaseService(project_id)


def _serialize(obj) -> dict | list | str:
    """Serialize an ORM object to a dict, handling detached sessions."""
    if obj is None:
        return {}
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "__dict__") and hasattr(obj, "__table__"):
        return {
            c.name: getattr(obj, c.name)
            for c in obj.__table__.columns
            if c.name not in ("created_at", "updated_at")
        }
    return str(obj)


# ========================================================================
# 1. Perception Tools (read-only)
# ========================================================================


@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """Search the knowledge base for specific information.

    Use when the user asks about any aspect of the novel's settings,
    characters, plot, or style. Uses semantic retrieval when available,
    falls back to structured DB queries.

    Args:
        query: Natural language search query (e.g., "主角的魔法限制", "世界观核心规则")
        target: Which part to search - "world_setting", "characters",
                "foreshadowing", "timeline", "plot", "style", or "all"
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Try semantic retrieval first (FAISS+BM25 hybrid)
    retrieval = RetrievalService(project_id)
    if retrieval.is_index_available():
        results = retrieval.search(query, top_k=8)
        if results:
            return {"found": True, "method": "semantic", "results": results}

    # Fallback to structured DB queries
    kb = _kb()
    results = {}

    if target in ("all", "world_setting"):
        ws = kb.get_world_setting()
        if ws:
            results["world_setting"] = _serialize(ws)

    if target in ("all", "characters"):
        chars = kb.get_characters()
        results["characters"] = _serialize(chars)

    if target in ("all", "foreshadowing"):
        foreshadowings = kb.get_foreshadowings()
        results["foreshadowings"] = _serialize(foreshadowings)

    if target in ("all", "timeline"):
        timeline = kb.get_timeline()
        results["timeline"] = _serialize(timeline)

    if target in ("all", "plot"):
        blocks = kb.get_plot_blocks()
        questions = kb.get_plot_questions()
        subplots = kb.get_subplots()
        results["plot_blocks"] = _serialize(blocks)
        results["plot_questions"] = _serialize(questions)
        results["subplots"] = _serialize(subplots)

    if target in ("all", "style"):
        style = kb.get_style_constraints()
        snapshots = kb.get_style_snapshots(last_n=5)
        results["style_constraints"] = _serialize(style) if style else {}
        results["recent_style_snapshots"] = _serialize(snapshots)

    filtered = {k: v for k, v in results.items() if v}
    if not filtered:
        return {"found": False, "message": f"未找到与「{query}」相关的知识库内容"}
    return {"found": True, "results": filtered}


@tool
async def foreshadowing_check(current_chapter: int | None = None) -> dict:
    """Check foreshadowing status — active, pending reclaim, overdue.

    Use when the user asks about foreshadowing health, which foreshadowings
    haven't been reclaimed, or whether any are overdue.

    Args:
        current_chapter: Current chapter number (for overdue calculation).
                         If not provided, no overdue check is performed.
    """
    kb = _kb()

    active = kb.get_foreshadowings(status="active")
    pending = kb.get_pending_foreshadowings()
    overdue = []
    if current_chapter:
        overdue = kb.get_overdue_foreshadowings(current_chapter)

    result = {
        "active_count": len(active),
        "pending_reclaim_count": len(pending),
        "overdue_count": len(overdue),
        "active": [
            {"id": f.id, "content": f.content[:80], "planted_chapter": f.planted_chapter, "level": f.level}
            for f in active
        ],
        "pending_reclaim": [
            {"id": f.id, "content": f.content[:80], "expected_resolve_chapter": f.expected_resolve_chapter}
            for f in pending
        ],
        "overdue": [
            {
                "id": f.id,
                "content": f.content[:80],
                "expected_resolve_chapter": f.expected_resolve_chapter,
                "overdue_by": current_chapter - f.expected_resolve_chapter
                if current_chapter and f.expected_resolve_chapter else 0,
            }
            for f in overdue
        ],
    }

    if overdue:
        result["warning"] = f"有 {len(overdue)} 个伏笔已超过预期回收章节"
    return result


@tool
async def consistency_check(chapter_a: int, chapter_b: int, aspect: str = "all") -> dict:
    """Check consistency between two chapters or across the whole novel.

    Use when the user suspects a contradiction or wants to verify
    consistency of character behavior, timeline, or settings.

    Args:
        chapter_a: First chapter number to compare
        chapter_b: Second chapter number to compare
        aspect: What to check - "character", "timeline", "setting", or "all"
    """
    kb = _kb()
    result = {"chapters_compared": [chapter_a, chapter_b], "issues": []}

    if aspect in ("all", "character"):
        chars = kb.get_characters()
        constraints = []
        for char in chars:
            constraints.append({
                "name": char.name,
                "knowledge_boundary": getattr(char, "knowledge_boundary", None) or getattr(char, "deep_fear", ""),
            })
        result["character_constraints"] = constraints

    if aspect in ("all", "timeline"):
        timeline = kb.get_timeline(chapter_range=(chapter_a, chapter_b))
        result["timeline_entries"] = _serialize(timeline)

    if aspect in ("all", "setting"):
        ws = kb.get_world_setting()
        if ws:
            result["world_setting_red"] = ws.tiered_settings.get("red", []) if ws.tiered_settings else []

    if not result["issues"]:
        result["message"] = "未发现明显的逻辑矛盾。请提供具体的矛盾描述，我可以帮你进一步分析。"
    return result


@tool
async def style_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze writing style trends and detect drift.

    Use when the user asks about style consistency, dialogue ratio,
    or whether recent chapters are drifting from the established style.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    snapshots = kb.get_style_snapshots(last_n=last_n_chapters)

    if not snapshots:
        return {"has_data": False, "message": "尚无风格统计数据，需要先写几章后才能分析"}

    avg_dialogue = sum(s.dialogue_ratio for s in snapshots if s.dialogue_ratio) / max(len(snapshots), 1)
    avg_sent_len = sum(s.avg_sentence_length for s in snapshots if s.avg_sentence_length) / max(len(snapshots), 1)
    avg_para_len = sum(s.avg_paragraph_length for s in snapshots if s.avg_paragraph_length) / max(len(snapshots), 1)

    drift = {}
    if len(snapshots) >= 3:
        recent_3 = snapshots[:3]
        recent_dialogue = sum(s.dialogue_ratio for s in recent_3) / 3
        recent_sent = sum(s.avg_sentence_length for s in recent_3) / 3

        if avg_dialogue > 0 and abs(recent_dialogue - avg_dialogue) / avg_dialogue > 0.25:
            drift["dialogue_ratio"] = {
                "overall_avg": round(avg_dialogue, 3),
                "recent_avg": round(recent_dialogue, 3),
                "direction": "偏高" if recent_dialogue > avg_dialogue else "偏低",
            }
        if avg_sent_len > 0 and abs(recent_sent - avg_sent_len) / avg_sent_len > 0.25:
            drift["sentence_length"] = {
                "overall_avg": round(avg_sent_len, 1),
                "recent_avg": round(recent_sent, 1),
                "direction": "偏长" if recent_sent > avg_sent_len else "偏短",
            }

    result = {
        "has_data": True,
        "overall_averages": {
            "dialogue_ratio": round(avg_dialogue, 3),
            "avg_sentence_length": round(avg_sent_len, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
        },
        "snapshots": [
            {
                "chapter": s.chapter_number,
                "dialogue_ratio": s.dialogue_ratio,
                "avg_sentence_length": s.avg_sentence_length,
                "paragraph_count": s.paragraph_count,
            }
            for s in snapshots
        ],
        "drift_detection": drift if drift else "风格稳定，未检测到漂移",
    }

    if drift:
        result["warning"] = "检测到风格漂移，建议检查最近几章的写作风格"
    return result


@tool
async def progress_report() -> dict:
    """Generate a writing progress report.

    Use when the user asks how far they've gotten, what's been written,
    what's left, or the overall status of the novel.
    """
    kb = _kb()

    outline = kb.get_outline()
    chars = kb.get_characters()
    foreshadowings = kb.get_foreshadowings()
    timeline = kb.get_timeline()
    blocks = kb.get_plot_blocks()

    written_chapters = len(timeline) if timeline else 0
    total_chapters = 0
    if outline:
        total_chapters = outline.chapter_count_confirmed or outline.chapter_count_suggested or 0

    active_foreshadowings = [f for f in foreshadowings if f.status in ("active", "pending_reclaim")]
    reclaimed = [f for f in foreshadowings if f.status == "reclaimed"]

    result = {
        "total_planned_chapters": total_chapters,
        "chapters_written": written_chapters,
        "progress_percent": round(written_chapters / total_chapters * 100, 1) if total_chapters else 0,
        "characters_count": len(chars),
        "foreshadowings_active": len(active_foreshadowings),
        "foreshadowings_reclaimed": len(reclaimed),
        "plot_blocks_total": len(blocks),
        "plot_blocks_completed": len([b for b in blocks if b.completion_summary]),
    }

    if outline:
        result["title"] = outline.title or "未命名"
        result["summary"] = (outline.summary or "")[:200]

    return result


@tool
async def rhythm_analysis(last_n_chapters: int = 10) -> dict:
    """Analyze story rhythm — tension, emotion, pacing trends.

    Use when the user asks about pacing, whether recent chapters
    feel flat, or whether the rhythm curve is monotone.

    Args:
        last_n_chapters: Number of recent chapters to analyze (default 10)
    """
    kb = _kb()
    timeline = kb.get_timeline()
    recent = timeline[:last_n_chapters] if timeline else []

    if not recent:
        return {"has_data": False, "message": "尚无时间线数据，需要先写几章后才能分析节奏"}

    # Detect monotone sections: 3+ consecutive chapters with same emotion_tag
    monotone_sections = []
    consecutive_same = 0
    last_tag = None
    start_chapter = None
    last_tag_chapter = None

    for entry in reversed(recent):  # timeline is ordered desc
        tag = entry.emotion_tag
        if tag == last_tag and tag:
            consecutive_same += 1
            if consecutive_same >= 3:
                monotone_sections.append({
                    "start_chapter": start_chapter,
                    "end_chapter": entry.chapter_number,
                    "emotion": tag,
                    "length": consecutive_same + 1,
                })
        else:
            consecutive_same = 0
            start_chapter = entry.chapter_number
        last_tag = tag
        last_tag_chapter = entry.chapter_number

    result = {
        "has_data": True,
        "chapters_analyzed": len(recent),
        "rhythm_curve": [
            {
                "chapter": t.chapter_number,
                "rhythm_score": t.rhythm_score,
                "tension_score": t.tension_score,
                "emotion_score": t.emotion_score,
                "emotion_tag": t.emotion_tag,
            }
            for t in reversed(recent)
        ],
        "monotone_sections": monotone_sections,
        "average_tension": round(
            sum(t.tension_score for t in recent if t.tension_score) / max(len(recent), 1), 1
        ),
    }

    if monotone_sections:
        result["warning"] = f"检测到 {len(monotone_sections)} 段节奏单调区域，建议调整情绪节奏"
    return result


# ========================================================================
# 2. Modification Tools (with impact assessment)
# ========================================================================


@tool
async def propose_setting_change(
    target_type: str,
    target_id: int,
    new_value: str,
    description: str,
) -> dict:
    """Propose a change to a knowledge base setting.

    Automatically triggers impact assessment. The change is NOT applied
    immediately — it creates a SettingChange record with status="proposed"
    and an impact report. The author must approve or abandon it.

    Args:
        target_type: What to change - "world_setting", "character",
                     "foreshadowing", "style", "outline", "relation"
        target_id: ID of the object to change
        new_value: JSON string describing the new value
        description: Natural language description of the proposed change
    """
    kb = _kb()

    old_value = _get_current_value(kb, target_type, target_id)

    try:
        new_value_parsed = json.loads(new_value) if isinstance(new_value, str) else new_value
    except json.JSONDecodeError:
        new_value_parsed = {"value": new_value}

    keywords = _extract_keywords(old_value, new_value_parsed, description)
    affected = kb.search_chapters_for_references(keywords)

    impact_level, impact_detail = _grade_impact(affected, target_type, new_value_parsed, old_value)

    impact_report = {
        "level": impact_level,
        "affected_chapters": len(affected),
        "affected_paragraphs": sum(len(ch.get("matching_paragraphs", [])) for ch in affected),
        "details": affected[:5],
        "grading_explanation": impact_detail,
    }

    change = kb.create_setting_change({
        "target_type": target_type,
        "target_id": target_id,
        "old_value": old_value,
        "new_value": new_value_parsed,
        "description": description,
        "status": "proposed",
        "impact_report": impact_report,
    })

    level_labels = {"none": "🟢 不影响", "minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_chapters": impact_report["affected_chapters"],
        "affected_paragraphs": impact_report["affected_paragraphs"],
        "detail": impact_detail,
        "next_steps": "作者需决策：proceed（按原方案修改）/ adjust（调整修改方案）/ abandon（放弃修改）",
    }


@tool
async def propose_outline_adjustment(
    description: str,
    affected_plot_blocks: list[int] | None = None,
) -> dict:
    """Propose an adjustment to the story structure.

    Evaluates impact on foreshadowing, plot questions, and already-written chapters.

    Args:
        description: Natural language description of the proposed adjustment
        affected_plot_blocks: List of plot block IDs that would be affected
    """
    kb = _kb()

    blocks = kb.get_plot_blocks()
    foreshadowings = kb.get_foreshadowings(status="active")
    questions = kb.get_plot_questions(status="pending")

    affected_blocks = []
    if affected_plot_blocks:
        affected_blocks = [b for b in blocks if b.id in affected_plot_blocks]
    else:
        for b in blocks:
            block_text = f"{b.title} {' '.join(b.must_happen or [])} {' '.join(b.questions_to_answer or [])}"
            for word in description.split():
                if len(word) >= 2 and word in block_text:
                    affected_blocks.append(b)
                    break

    affected_foreshadowings = []
    for f in foreshadowings:
        for b in affected_blocks:
            if b.chapter_start and f.expected_resolve_chapter:
                if b.chapter_start <= f.expected_resolve_chapter <= (b.chapter_end or 999):
                    affected_foreshadowings.append({
                        "id": f.id,
                        "content": f.content[:60],
                        "expected_resolve_chapter": f.expected_resolve_chapter,
                    })

    affected_questions = []
    for q in questions:
        for b in affected_blocks:
            if q.plot_block_id == b.id:
                affected_questions.append({
                    "id": q.id,
                    "question": q.question_text[:60],
                    "status": q.status,
                })

    impact_level = "minor"
    if affected_foreshadowings or affected_questions:
        impact_level = "moderate"
    if len(affected_blocks) > 2:
        impact_level = "severe"

    change = kb.create_setting_change({
        "target_type": "outline_adjustment",
        "target_id": 0,
        "old_value": {},
        "new_value": {"description": description},
        "description": description,
        "status": "proposed",
        "impact_report": {
            "level": impact_level,
            "affected_blocks": [
                {"id": b.id, "title": b.title, "chapter_range": f"{b.chapter_start}-{b.chapter_end}"}
                for b in affected_blocks
            ],
            "affected_foreshadowings": affected_foreshadowings,
            "affected_questions": affected_questions,
        },
    })

    level_labels = {"minor": "🟡 轻微影响", "moderate": "🟠 中度影响", "severe": "🔴 严重影响"}

    return {
        "change_id": change.id,
        "status": "proposed",
        "impact_level": impact_level,
        "impact_label": level_labels.get(impact_level, impact_level),
        "affected_blocks": len(affected_blocks),
        "affected_foreshadowings": len(affected_foreshadowings),
        "affected_questions": len(affected_questions),
        "next_steps": "作者需决策：proceed / adjust / abandon",
    }


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


# ========================================================================
# 3. Creation Assist Tools
# ========================================================================


@tool
async def writer_block_assist(current_chapter: int) -> dict:
    """Help overcome writer's block with 2-3 writing directions.

    Suggests scene ideas, reclaimable foreshadowings, and
    question chain prompts based on current progress.

    Args:
        current_chapter: Current chapter number being worked on
    """
    kb = _kb()

    pending = kb.get_pending_foreshadowings()
    overdue = kb.get_overdue_foreshadowings(current_chapter)
    questions = kb.get_questions_for_chapter(current_chapter)
    block = kb.get_current_plot_block(current_chapter)

    suggestions = []

    if overdue:
        f = overdue[0]
        suggestions.append({
            "direction": "回收超期伏笔",
            "detail": f"伏笔「{f.content[:50]}」已超过预期回收章节，可以在本章回收",
            "foreshadowing_id": f.id,
        })

    if questions:
        q = questions[0]
        suggestions.append({
            "direction": "回答待解问题",
            "detail": f"问题「{q.question_text[:50]}」可以在本章回答",
            "question_id": q.id,
        })

    if block:
        must_happen = block.must_happen or []
        if must_happen:
            suggestions.append({
                "direction": "推进情节块",
                "detail": f"当前情节块「{block.title}」必须事件：{must_happen[0][:50] if must_happen else '无'}",
                "plot_block_id": block.id,
            })

    if not suggestions:
        suggestions.append({
            "direction": "自由发挥",
            "detail": "当前没有紧迫的伏笔或问题链需要处理，可以自由推进剧情",
        })

    return {
        "current_chapter": current_chapter,
        "suggestions": suggestions,
        "pending_foreshadowings": len(pending),
        "pending_questions": len(questions),
    }


@tool
async def suggest_foreshadowing(current_chapter: int) -> dict:
    """Suggest foreshadowing placement based on current plot block.

    Analyzes the current plot block and existing foreshadowing map
    to suggest new foreshadowings that fit the story structure.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    block = kb.get_current_plot_block(current_chapter)
    foreshadowings = kb.get_foreshadowings()
    active = [f for f in foreshadowings if f.status in ("active", "pending_reclaim")]

    if not block:
        return {"suggestion": "当前没有情节块信息，建议先完成结构设计"}

    suggestions = []
    for question in (block.questions_to_raise or []):
        suggestions.append({
            "type": "问题驱动",
            "content": f"围绕「{question[:40]}」设置伏笔暗示",
            "related_question": question[:60],
        })

    if len(active) < 3 and block.chapter_end and block.chapter_start:
        span = block.chapter_end - block.chapter_start
        if span > 3:
            suggestions.append({
                "type": "密度建议",
                "content": f"当前情节块跨越 {span} 章但仅有 {len(active)} 个活跃伏笔，建议补充",
            })

    return {
        "current_chapter": current_chapter,
        "plot_block": block.title if block else None,
        "active_foreshadowings": len(active),
        "suggestions": suggestions,
    }


@tool
async def suggest_plot_twist(current_chapter: int) -> dict:
    """Suggest a plot twist based on rhythm curve, character arcs, and foreshadowings.

    Use when the user wants ideas for a surprising turn in the story.

    Args:
        current_chapter: Current chapter number
    """
    kb = _kb()

    timeline = kb.get_timeline()
    foreshadowings = kb.get_foreshadowings(status="active")
    characters = kb.get_characters()
    block = kb.get_current_plot_block(current_chapter)

    recent_tension = []
    if timeline:
        for t in timeline[:5]:
            if t.tension_score:
                recent_tension.append(t.tension_score)

    avg_tension = sum(recent_tension) / max(len(recent_tension), 1) if recent_tension else 3

    twist_types = []

    if avg_tension < 3:
        twist_types.append({
            "type": "冲突升级",
            "reason": f"最近 {len(recent_tension)} 章平均张力 {avg_tension:.1f}，建议加入转折提升紧张感",
        })

    if len(foreshadowings) >= 2:
        twist_types.append({
            "type": "伏笔误导",
            "reason": f"有 {len(foreshadowings)} 个活跃伏笔，可以利用读者的预期制造反转",
            "foreshadowing_ids": [f.id for f in foreshadowings[:3]],
        })

    for c in characters:
        if c.core_motivation and len(c.core_motivation) > 10:
            twist_types.append({
                "type": "角色反转",
                "reason": f"角色「{c.name}」的动机可以制造意想不到的转折",
                "character_id": c.id,
                "character_name": c.name,
            })
            break

    return {
        "current_chapter": current_chapter,
        "avg_recent_tension": round(avg_tension, 1),
        "suggestions": twist_types[:3],
    }


@tool
async def expand_world_setting(aspect: str, description: str) -> dict:
    """Expand the world setting in a specific direction.

    Automatically assesses impact of the expansion on existing content.

    Args:
        aspect: What aspect to expand - "location", "rule", "culture", "history", "technology"
        description: Natural language description of the expansion
    """
    kb = _kb()
    ws = kb.get_world_setting()

    if not ws:
        return {"error": "世界观尚未创建，请先完成创意孵化阶段"}

    red_settings = ws.tiered_settings.get("red", []) if ws.tiered_settings else []
    contradictions = []
    for rule in red_settings:
        rule_text = rule if isinstance(rule, str) else str(rule)
        for word in description.split():
            if len(word) >= 2 and word in rule_text:
                contradictions.append(rule_text[:80])

    impact_level = "none"
    impact_detail = "扩展不与现有🔴设定冲突"
    if contradictions:
        impact_level = "severe"
        impact_detail = f"扩展可能与🔴设定冲突：{'; '.join(contradictions[:3])}"

    keywords = [w for w in description.split() if len(w) >= 2][:5]
    affected = kb.search_chapters_for_references(keywords) if keywords else []

    if affected and impact_level != "severe":
        impact_level = "minor"

    return {
        "aspect": aspect,
        "description": description,
        "impact_level": impact_level,
        "impact_detail": impact_detail,
        "affected_chapters": len(affected),
        "contradictions": contradictions,
        "suggestion": "可以安全扩展" if impact_level == "none" else "建议先解决冲突再扩展",
    }


# ========================================================================
# Helper functions (not exposed as tools)
# ========================================================================


def _get_current_value(kb: KnowledgeBaseService, target_type: str, target_id: int) -> dict:
    """Get the current value of a knowledge base object for comparison."""
    if target_type == "world_setting":
        obj = kb.get_world_setting()
        if obj and obj.id == target_id:
            return _serialize(obj)
    elif target_type == "character":
        chars = kb.get_characters()
        for c in chars:
            if c.id == target_id:
                return _serialize(c)
    elif target_type == "foreshadowing":
        foreshadowings = kb.get_foreshadowings()
        for f in foreshadowings:
            if f.id == target_id:
                return _serialize(f)
    elif target_type == "style":
        style = kb.get_style_constraints()
        if style and style.id == target_id:
            return _serialize(style)
    elif target_type == "outline":
        outline = kb.get_outline()
        if outline and outline.id == target_id:
            return _serialize(outline)
    elif target_type == "relation":
        relations = kb.get_relations()
        for r in relations:
            if r.id == target_id:
                return _serialize(r)
    return {}


def _extract_keywords(old_value: dict, new_value: dict, description: str) -> list[str]:
    """Extract search keywords from the change description and values."""
    keywords = []
    for word in description.split():
        if len(word) >= 2:
            keywords.append(word)
    if isinstance(new_value, dict) and isinstance(old_value, dict):
        for key in new_value:
            if new_value.get(key) != old_value.get(key):
                val = new_value[key]
                if isinstance(val, str):
                    for word in val.split():
                        if len(word) >= 2:
                            keywords.append(word)
    return keywords[:10]


def _grade_impact(
    affected_chapters: list, target_type: str, new_value: dict, old_value: dict
) -> tuple[str, str]:
    """Grade the impact level of a proposed change.

    Returns (level, detail) where level is one of:
    none, minor, moderate, severe
    """
    total_paragraphs = sum(len(ch.get("matching_paragraphs", [])) for ch in affected_chapters)
    total_chapters = len(affected_chapters)

    if total_chapters == 0:
        return "none", "变更不影响任何已写内容"

    if total_chapters <= 1 and total_paragraphs <= 2:
        return "minor", f"轻微影响：{total_chapters} 章、{total_paragraphs} 段提及，读者不易察觉"

    if total_chapters <= 3 and total_paragraphs <= 5:
        return "moderate", f"中度影响：{total_chapters} 章、{total_paragraphs} 段提及，细心读者可能发现矛盾"

    return "severe", f"严重影响：{total_chapters} 章、{total_paragraphs} 段提及，核心情节可能直接矛盾"


# ========================================================================
# Tool lists by phase
# ========================================================================

# Tools available during incubation phase (perception only + expand)
INCUBATION_TOOLS = [
    knowledge_search,
    progress_report,
    expand_world_setting,
]

# Tools available during structure phase
STRUCTURE_TOOLS = [
    knowledge_search,
    foreshadowing_check,
    progress_report,
    rhythm_analysis,
    propose_outline_adjustment,
    suggest_foreshadowing,
]

# Tools available during writing phase (all tools)
WRITING_TOOLS = [
    # Perception
    knowledge_search,
    foreshadowing_check,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # Modification
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # Creation assist
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
]

# All tools (default)
AGENT_TOOLS = WRITING_TOOLS
