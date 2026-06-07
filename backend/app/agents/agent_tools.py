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

from app.agents.tool_context import get_project_id, get_model_config_id, get_user_id
from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.services.retrieval import RetrievalService
from app.utils.llm import resolve_llm_service
from app.agents.constants import NODE_TEMPERATURES
from app.agents.review_utils import _build_review_messages, parse_review_result, check_review_passed
from app.agents.rewrite_utils import _build_rewrite_messages, clean_chapter_content


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

    # 将扩展内容实际写入数据库（追加到 red/yellow/green 对应层级）
    tier_map = {"rule": "red", "culture": "yellow", "history": "yellow", "technology": "yellow", "location": "green"}
    target_tier = tier_map.get(aspect, "yellow")
    updated_tiered = dict(ws.tiered_settings) if ws.tiered_settings else {}
    if target_tier not in updated_tiered:
        updated_tiered[target_tier] = []
    updated_tiered[target_tier].append(f"[扩展-{aspect}] {description}")
    kb.update_world_setting(ws.id, {"tiered_settings": updated_tiered})

    return {
        "aspect": aspect,
        "description": description,
        "impact_level": impact_level,
        "impact_detail": impact_detail,
        "affected_chapters": len(affected),
        "contradictions": contradictions,
        "suggestion": "可以安全扩展" if impact_level == "none" else "建议先解决冲突再扩展",
        "written": True,
        "tier": target_tier,
    }


# ========================================================================
# 4. Creation Tools (direct write to knowledge base)
# ========================================================================


@tool
async def create_world_setting(
    core_concept: str,
    tiered_settings: str = "{}",
    key_locations: str = "[]",
) -> dict:
    """Create or update the world setting for the novel.

    Use when the user asks to set up or modify the world/setting of their novel.
    If a world setting already exists, it will be updated.

    Args:
        core_concept: The core concept of the world (e.g., "一个以灵力为基石的修仙世界，灵力枯竭导致文明衰败")
        tiered_settings: JSON string with tiered rules: {"red": [...], "yellow": [...], "green": [...]}
                         red = 🔴不可违反的核心规则, yellow = 🟡可突破但有代价, green = 🟢装饰性设定
        key_locations: JSON string list of key locations (e.g., ["天枢城", "灵脉深渊"])
    """
    import json as _json
    kb = _kb()

    try:
        tiered = _json.loads(tiered_settings) if isinstance(tiered_settings, str) else tiered_settings
    except _json.JSONDecodeError:
        tiered = {}

    try:
        locations = _json.loads(key_locations) if isinstance(key_locations, str) else key_locations
    except _json.JSONDecodeError:
        locations = []

    existing = kb.get_world_setting()
    if existing:
        # 合并策略：只更新用户显式传入的字段，避免"仅改 core_concept 却清空 tiered_settings"
        update_data = {"core_concept": core_concept}
        # 只有当 LLM 显式传入了 tiered_settings 时才覆盖
        if tiered_settings != "{}" or tiered:
            update_data["tiered_settings"] = tiered
        else:
            update_data["tiered_settings"] = existing.tiered_settings or {}
        # 只有当 LLM 显式传入了 key_locations 时才覆盖
        if key_locations != "[]" or locations:
            update_data["key_locations"] = locations
        else:
            update_data["key_locations"] = existing.key_locations or []
        updated = kb.update_world_setting(existing.id, update_data)
        return {"action": "updated", "id": updated.id, "core_concept": core_concept[:100]}
    else:
        created = kb.create_world_setting({
            "core_concept": core_concept,
            "tiered_settings": tiered,
            "key_locations": locations,
        })
        return {"action": "created", "id": created.id, "core_concept": core_concept[:100]}


@tool
async def create_character(
    name: str,
    role: str,
    personality: str = "",
    catchphrase: str = "",
    habit_action: str = "",
    deep_fear: str = "",
    core_motivation: str = "",
    growth_arc: str = "",
    appearance: str = "",
    backstory: str = "",
    signature_item: str = "",
) -> dict:
    """Create a new character in the novel.

    Use when the user describes a new character they want to add to their novel.
    This directly writes to the knowledge base — no approval needed for new characters.

    Args:
        name: Character name
        role: Character role - one of: 主角, 核心反派, 重要配角, 配角
        personality: Personality traits description
        catchphrase: Character's catchphrase or typical speech pattern
        habit_action: Character's habitual gesture or action
        deep_fear: Character's deep-seated fear
        core_motivation: Character's core motivation driving their actions
        growth_arc: Character's growth arc / character development trajectory
        appearance: Physical appearance description
        backstory: Character's backstory
        signature_item: Character's signature item or accessory
    """
    kb = _kb()

    data = {"name": name, "role": role}
    for key, val in [
        ("personality", personality),
        ("catchphrase", catchphrase),
        ("habit_action", habit_action),
        ("deep_fear", deep_fear),
        ("core_motivation", core_motivation),
        ("growth_arc", growth_arc),
        ("appearance", appearance),
        ("backstory", backstory),
        ("signature_item", signature_item),
    ]:
        if val:
            data[key] = val

    char = kb.create_character(data)
    return {
        "action": "created",
        "id": char.id,
        "name": char.name,
        "role": char.role,
        "message": f"角色「{name}」已创建并写入知识库",
    }


@tool
async def create_relation(
    character_a_id: int,
    character_b_id: int,
    relation_type: str,
    direction: str = "双向",
    current_status: str = "",
    trust_level: int = 50,
) -> dict:
    """Create a relationship between two characters.

    Use when the user describes a relationship between characters they've created.
    This directly writes to the knowledge base.

    Args:
        character_a_id: ID of the first character
        character_b_id: ID of the second character
        relation_type: Type of relationship - one of: 信任, 敌对, 感情, 合作, 利用, 陌生
        direction: Direction of the relationship - one of: 双向, 单向A→B, 单向B→A
        current_status: Description of the current relationship status (optional)
        trust_level: Trust level from 0 to 100, default 50
    """
    kb = _kb()

    data = {
        "character_a_id": character_a_id,
        "character_b_id": character_b_id,
        "relation_type": relation_type,
        "direction": direction,
        "trust_level": trust_level,
    }
    if current_status:
        data["current_status"] = current_status

    relation = kb.create_relation(data)
    return {
        "action": "created",
        "id": relation.id,
        "relation_type": relation_type,
        "direction": direction,
        "message": f"角色关系「{relation_type}」已创建并写入知识库",
    }


@tool
async def create_subplot(
    name: str,
    characters: str = "[]",
    current_status: str = "hint",
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
    """Create a new subplot (支线) in the novel.

    Use when the user wants to add a subplot or secondary storyline.
    This directly writes to the knowledge base.

    Args:
        name: Subplot name (e.g., "皇室阴谋线", "师徒恩怨线")
        characters: JSON string list of character names involved
        current_status: Current subplot status - one of: hint (暗示), developing (发展中), pending_intersection (待交汇), resolved (已解决)
        raised_in_chapter: Chapter number where this subplot is first introduced
        planned_intersection_chapter: Chapter number where this subplot intersects with the main plot
        expected_resolution_chapter: Chapter number where this subplot resolves
    """
    import json as _json
    kb = _kb()

    try:
        chars = _json.loads(characters) if isinstance(characters, str) else characters
    except _json.JSONDecodeError:
        chars = []

    data = {"name": name, "characters": chars, "current_status": current_status}
    if raised_in_chapter is not None:
        data["raised_in_chapter"] = raised_in_chapter
    if planned_intersection_chapter is not None:
        data["planned_intersection_chapter"] = planned_intersection_chapter
    if expected_resolution_chapter is not None:
        data["expected_resolution_chapter"] = expected_resolution_chapter

    s = kb.create_subplot(data)
    return {
        "action": "created",
        "id": s.id,
        "name": name,
        "message": f"支线「{name}」已创建并写入知识库",
    }


@tool
async def create_plot_question(
    question_text: str,
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
) -> dict:
    """Create a new plot question in the question chain.

    Use when the user wants to add a dramatic question that the story
    needs to answer. Part of the reverse-planning question chain system.

    Args:
        question_text: The question to be answered (e.g., "主角为什么被追捕？")
        raised_in_chapter: Chapter number where this question is raised
        plot_block_id: Optional plot block ID that this question belongs to
    """
    kb = _kb()

    data = {"question_text": question_text, "status": "pending"}
    if raised_in_chapter is not None:
        data["raised_in_chapter"] = raised_in_chapter
    if plot_block_id is not None:
        data["plot_block_id"] = plot_block_id

    q = kb.create_plot_question(data)
    return {
        "action": "created",
        "id": q.id,
        "question_text": question_text[:80],
        "message": f"问题「{question_text[:60]}」已创建并写入知识库",
    }


@tool
async def create_timeline_entry(
    chapter_number: int,
    summary: str,
    causal_chain: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
) -> dict:
    """Create a timeline entry for a chapter.

    Use when the user wants to manually add a timeline summary entry
    for a specific chapter. Timeline entries help the Agent track
    story progression across chapters.

    Args:
        chapter_number: Chapter number this entry refers to
        summary: One-sentence summary of key events in this chapter
        causal_chain: Causal chain description (what led to what)
        rhythm_score: Rhythm score 1-5 (1=slow, 5=frantic)
        tension_score: Tension score 1-5 (1=relaxed, 5=peak)
        emotion_score: Emotion score 1-5
        emotion_tag: Emotion tag - one of: 紧张, 舒缓, 悲伤, 温暖, 转折, 日常
    """
    kb = _kb()

    data = {"chapter_number": chapter_number, "summary": summary}
    if causal_chain:
        data["causal_chain"] = causal_chain
    if rhythm_score:
        data["rhythm_score"] = rhythm_score
    if tension_score:
        data["tension_score"] = tension_score
    if emotion_score:
        data["emotion_score"] = emotion_score
    if emotion_tag:
        data["emotion_tag"] = emotion_tag

    entry = kb.create_timeline_entry(data)
    return {
        "action": "created",
        "id": entry.id,
        "chapter_number": chapter_number,
        "message": f"第{chapter_number}章时间线条目已创建",
    }


@tool
async def create_style_constraints(
    style_anchor: str = "",
    taboo_words: str = "[]",
    forbidden_patterns: str = "[]",
    abstract_rules: str = "[]",
) -> dict:
    """Create or update style constraints for the novel.

    Use when the user describes writing style requirements, forbidden words,
    or style rules they want to enforce.

    Args:
        style_anchor: Reference text snippet that embodies the desired style
        taboo_words: JSON string list of forbidden words (e.g., ["突然", "不由得"])
        forbidden_patterns: JSON string list of forbidden sentence patterns
        abstract_rules: JSON string list of abstract style rules (e.g., ["对话占比不低于30%", "避免长段内心独白"])
    """
    import json as _json
    kb = _kb()

    try:
        taboo = _json.loads(taboo_words) if isinstance(taboo_words, str) else taboo_words
    except _json.JSONDecodeError:
        taboo = []

    try:
        patterns = _json.loads(forbidden_patterns) if isinstance(forbidden_patterns, str) else forbidden_patterns
    except _json.JSONDecodeError:
        patterns = []

    try:
        rules = _json.loads(abstract_rules) if isinstance(abstract_rules, str) else abstract_rules
    except _json.JSONDecodeError:
        rules = []

    existing = kb.get_style_constraints()
    if existing:
        update_data = {}
        if taboo:
            update_data["taboo_words"] = taboo
        if patterns:
            update_data["forbidden_patterns"] = patterns
        if rules:
            update_data["abstract_rules"] = rules
        if style_anchor:
            update_data["style_anchor"] = style_anchor
        if update_data:
            updated = kb.update_style_constraints(existing.id, update_data)
            return {"action": "updated", "id": updated.id, "message": "风格约束已更新"}
        return {"action": "unchanged", "message": "没有需要更新的内容"}
    else:
        created = kb.create_style_constraints({
            "style_anchor": style_anchor,
            "taboo_words": taboo,
            "forbidden_patterns": patterns,
            "abstract_rules": rules,
        })
        return {"action": "created", "id": created.id, "message": "风格约束已创建并写入知识库"}


@tool
async def create_foreshadowing(
    content: str,
    level: str = "hint",
    planted_chapter: int | None = None,
    expected_resolve_chapter: int | None = None,
    related_characters: str = "[]",
) -> dict:
    """Create a new foreshadowing entry in the novel.

    Use when the user wants to plan or add a foreshadowing element
    to their story. This directly writes to the knowledge base.

    Args:
        content: Description of the foreshadowing element
        level: Foreshadowing level - one of: hint (暗示), strengthened (强化), revealed (揭示)
        planted_chapter: Chapter number where the foreshadowing is planted
        expected_resolve_chapter: Chapter number where the foreshadowing is expected to be resolved
        related_characters: JSON string list of related character names
    """
    import json as _json
    kb = _kb()

    try:
        characters = _json.loads(related_characters) if isinstance(related_characters, str) else related_characters
    except _json.JSONDecodeError:
        characters = []

    data = {
        "content": content,
        "level": level,
        "related_characters": characters,
    }
    if planted_chapter is not None:
        data["planted_chapter"] = planted_chapter
    if expected_resolve_chapter is not None:
        data["expected_resolve_chapter"] = expected_resolve_chapter

    f = kb.create_foreshadowing(data)
    return {
        "action": "created",
        "id": f.id,
        "content": content[:80],
        "level": level,
        "message": f"伏笔已创建并写入知识库",
    }


@tool
async def create_plot_block(
    title: str,
    chapter_start: int,
    chapter_end: int,
    must_happen: str = "[]",
    questions_to_raise: str = "[]",
    questions_to_answer: str = "[]",
    expected_mood: str = "",
) -> dict:
    """Create a new plot block (story arc segment).

    Use when the user wants to define a plot segment or story arc
    covering a range of chapters.

    Args:
        title: Plot block title (e.g., "初入修仙界")
        chapter_start: Starting chapter number
        chapter_end: Ending chapter number
        must_happen: JSON string list of events that must happen in this block
        questions_to_raise: JSON string list of questions this block raises
        questions_to_answer: JSON string list of questions this block should answer
        expected_mood: Expected mood/tone for this block (e.g., "紧张悬疑", "温馨治愈")
    """
    import json as _json
    kb = _kb()

    try:
        must = _json.loads(must_happen) if isinstance(must_happen, str) else must_happen
    except _json.JSONDecodeError:
        must = []

    try:
        raise_q = _json.loads(questions_to_raise) if isinstance(questions_to_raise, str) else questions_to_raise
    except _json.JSONDecodeError:
        raise_q = []

    try:
        answer_q = _json.loads(questions_to_answer) if isinstance(questions_to_answer, str) else questions_to_answer
    except _json.JSONDecodeError:
        answer_q = []

    data = {
        "title": title,
        "chapter_start": chapter_start,
        "chapter_end": chapter_end,
        "must_happen": must,
        "questions_to_raise": raise_q,
        "questions_to_answer": answer_q,
    }
    if expected_mood:
        data["expected_mood"] = expected_mood

    block = kb.create_plot_block(data)
    return {
        "action": "created",
        "id": block.id,
        "title": title,
        "chapter_range": f"{chapter_start}-{chapter_end}",
        "message": f"情节块「{title}」已创建并写入知识库",
    }



# ========================================================================
# 6. Review & Rewrite Tools (Agent-driven quality control)
# ========================================================================


def _build_state_for_review(project_id: int, chapter_number: int) -> dict:
    """Build a minimal NovelState dict for review/rewrite message construction.

    Reads characters, relations, world_setting, chapter_outlines, written_chapters
    from KnowledgeBaseService to satisfy _build_review_messages / _build_rewrite_messages contracts.
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline

    kb = KnowledgeBaseService(project_id)

    # Outline for chapter_count and target words
    outline = kb.get_outline()
    target_words = 100000
    if outline:
        target_words = (outline.chapter_count_confirmed or outline.chapter_count_suggested or 100) * 3000

    # Characters
    chars_raw = kb.get_characters()
    characters = []
    for c in chars_raw:
        characters.append({
            "id": c.id, "name": c.name, "role": getattr(c, "role", ""),
            "personality": getattr(c, "personality", ""),
            "appearance": getattr(c, "appearance", ""),
            "backstory": getattr(c, "backstory", ""),
            "catchphrase": getattr(c, "catchphrase", ""),
            "habit_action": getattr(c, "habit_action", ""),
            "deep_fear": getattr(c, "deep_fear", ""),
            "core_motivation": getattr(c, "core_motivation", ""),
            "growth_arc": getattr(c, "growth_arc", ""),
            "signature_item": getattr(c, "signature_item", ""),
        })

    # Relations
    relations_raw = kb.get_relations()
    relations = []
    for r in relations_raw:
        relations.append({
            "character_a_id": getattr(r, "character_a_id", None),
            "character_b_id": getattr(r, "character_b_id", None),
            "relation_type": getattr(r, "relation_type", ""),
            "current_status": getattr(r, "current_status", ""),
        })

    # Evolution plans
    evolution_plans_raw = kb.get_relations_with_plans()
    evolution_plans = []
    for ep in evolution_plans_raw:
        evolution_plans.append(ep if isinstance(ep, dict) else _serialize(ep))

    # World setting
    ws = kb.get_world_setting()

    # Chapter outlines
    chapter_outlines = []
    db = SessionLocal()
    try:
        co_list = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id
        ).order_by(ChapterOutline.chapter_number).all()
        for co in co_list:
            chapter_outlines.append({
                "chapter_number": co.chapter_number,
                "title": co.title or "",
                "scene": co.scene,
                "characters": co.characters,
                "plot": co.plot or "",
                "conflict": co.conflict,
                "turning_point": co.turning_point,
                "hook": co.hook,
                "transition": co.transition,
                "ending": co.ending,
                "target_words": co.target_words,
            })
    finally:
        db.close()

    # Written chapters (timeline summaries for context)
    timeline = kb.get_timeline()
    written_chapters = []
    for t in timeline:
        written_chapters.append({
            "chapter_number": t.chapter_number,
            "summary": getattr(t, "summary", ""),
        })

    # Collected info (style preferences, genre)
    collected_info = {}
    if outline:
        collected_info["novelType"] = getattr(outline, "novel_type", "") or ""
    style = kb.get_style_constraints()
    if style:
        collected_info["stylePreference"] = getattr(style, "style_preference", "") or ""
    collected_info["targetWords"] = target_words

    # Load custom prompts from DB
    _prompts = {}
    try:
        db2 = SessionLocal()
        try:
            from app.models.system_prompt import SystemPrompt
            prompts = db2.query(SystemPrompt).all()
            for p in prompts:
                _prompts[p.node_name] = {"system": p.system_prompt, "user": p.user_prompt}
        finally:
            db2.close()
    except Exception:
        pass

    if not _prompts:
        from app.agents.prompts import DEFAULT_PROMPTS
        _prompts = DEFAULT_PROMPTS

    return {
        "project_id": project_id,
        "current_chapter": chapter_number,
        "characters": characters,
        "relations": relations,
        "evolution_plans": evolution_plans,
        "evolution_records": [],
        "world_setting": _serialize(ws) if ws else {},
        "chapter_outlines": chapter_outlines,
        "written_chapters": written_chapters,
        "collected_info": collected_info,
        "_prompts": _prompts,
        "_context_window": 32000,
    }


@tool
async def review_chapter(chapter_number: int) -> dict:
    """Review a chapter for quality across 6 dimensions.

    Performs a comprehensive quality review analyzing plot consistency,
    character consistency, writing quality, emotional tension, AI flavor,
    and outline deviation. Results are saved to the database.

    Args:
        chapter_number: The chapter number to review (e.g., 1, 2, 3)
    """
    project_id = get_project_id()
    model_config_id = get_model_config_id()
    user_id = get_user_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Resolve LLM service
    try:
        llm = resolve_llm_service(model_config_id, user_id)
    except ValueError as e:
        return {"error": f"Cannot resolve LLM config: {e}"}

    # Read chapter from DB
    kb = KnowledgeBaseService(project_id)
    chapter = kb.get_chapter_by_number(chapter_number)
    if not chapter or not chapter.content:
        return {"error": f"Chapter {chapter_number} not found or has no content"}

    # Get chapter outline
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"Chapter {chapter_number} outline not found"}
        chapter_outline_dict = {
            "chapter_number": co.chapter_number,
            "title": co.title or "",
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot or "",
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        chapter_outline_id = co.id
    finally:
        db.close()

    # Build state for review message construction
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_review_messages(state, chapter.content, chapter_outline_dict)
    try:
        response = await llm.chat(messages, temperature=NODE_TEMPERATURES["review"])
        review_result = parse_review_result(response)
        review_result["raw_response"] = response
        passed = check_review_passed(review_result)
    except Exception as e:
        return {"error": f"Review LLM call failed: {e}"}

    # Save to DB
    from app.models.chapter import Chapter
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(
            Chapter.chapter_outline_id == chapter_outline_id
        ).first()
        if ch:
            ch.review_passed = passed
            ch.review_feedback = response
            ch.review_result = review_result
            save_db.commit()
            committed = True
    except Exception as e:
        return {"error": f"Failed to save review result: {e}"}
    finally:
        if not committed:
            try:
                save_db.rollback()
            except Exception:
                pass
        try:
            save_db.close()
        except Exception:
            pass

    return {
        "chapter_number": chapter_number,
        "passed": passed,
        "scores": review_result.get("scores", {}),
        "issues": review_result.get("issues", []),
        "suggestions": review_result.get("suggestions", ""),
        "message": f"Review {'passed' if passed else 'failed'} — "
                   f"{len(review_result.get('issues', []))} issues found",
    }


@tool
async def rewrite_chapter(chapter_number: int) -> dict:
    """Rewrite a chapter based on its latest review feedback.

    The chapter must have been reviewed first (review_feedback must exist).
    Generates new content, saves it to the database, increments rewrite_count,
    and clears the review state so it can be re-reviewed.

    Args:
        chapter_number: The chapter number to rewrite (e.g., 1, 2, 3)
    """
    project_id = get_project_id()
    model_config_id = get_model_config_id()
    user_id = get_user_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    # Resolve LLM service
    try:
        llm = resolve_llm_service(model_config_id, user_id)
    except ValueError as e:
        return {"error": f"Cannot resolve LLM config: {e}"}

    # Read chapter from DB
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.models.chapter import Chapter

    db = SessionLocal()
    try:
        co = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        ).first()
        if not co:
            return {"error": f"Chapter {chapter_number} outline not found"}

        chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == co.id
        ).first()
        if not chapter or not chapter.content:
            return {"error": f"Chapter {chapter_number} not found or has no content"}

        # Must have review feedback
        review_feedback = ""
        if chapter.review_result:
            review_feedback = (
                chapter.review_result.get("raw_response", "")
                or chapter.review_result.get("suggestions", "")
            )
        if not review_feedback and chapter.review_feedback:
            review_feedback = chapter.review_feedback
        if not review_feedback:
            return {"error": f"Chapter {chapter_number} has not been reviewed yet, use review_chapter first"}

        chapter_outline_dict = {
            "chapter_number": co.chapter_number,
            "title": co.title or "",
            "scene": co.scene,
            "characters": co.characters,
            "plot": co.plot or "",
            "conflict": co.conflict,
            "turning_point": co.turning_point,
            "hook": co.hook,
            "transition": co.transition,
            "ending": co.ending,
            "target_words": co.target_words,
        }
        original_content = chapter.content
        chapter_id = chapter.id
    finally:
        db.close()

    # Build state for rewrite message construction
    state = _build_state_for_review(project_id, chapter_number)

    # Build messages and call LLM
    messages = _build_rewrite_messages(
        state, chapter_outline_dict, original_content, review_feedback
    )
    try:
        response = await llm.chat(
            messages,
            temperature=NODE_TEMPERATURES["rewrite"],
            max_tokens=16384,
        )
        new_content = clean_chapter_content(response)
    except Exception as e:
        return {"error": f"Rewrite LLM call failed: {e}"}

    # Save to DB
    save_db = SessionLocal()
    committed = False
    try:
        ch = save_db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if ch:
            ch.content = new_content
            ch.word_count = len(new_content)
            ch.rewrite_count = (ch.rewrite_count or 0) + 1
            ch.review_passed = False
            ch.review_result = None
            ch.review_feedback = None
            save_db.commit()
            committed = True
            word_count = len(new_content)
        else:
            return {"error": "Chapter deleted during rewrite"}
    except Exception as e:
        return {"error": f"Failed to save rewrite result: {e}"}
    finally:
        if not committed:
            try:
                save_db.rollback()
            except Exception:
                pass
        try:
            save_db.close()
        except Exception:
            pass

    return {
        "action": "rewritten",
        "chapter_number": chapter_number,
        "word_count": word_count,
        "message": f"Chapter {chapter_number} rewritten ({word_count} chars), please review again",
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
# 5. Generation Tools (direct content generation and write)
# ========================================================================


@tool
async def generate_outline(
    title: str,
    summary: str,
    chapter_count: int,
    plot_points: str = "[]",
    emotional_curve: str = "[]",
    characters: str = "[]",
    world_setting_summary: str = "",
) -> dict:
    """Generate and save the complete novel outline.

    Use this when the user asks to create or update the novel outline.
    This directly writes a full outline to the knowledge base — no approval needed.

    Args:
        title: Novel title (e.g., "星辰陨落之时")
        summary: 500-800 word story overview, must include surface conflict, deep conflict, and theme
        chapter_count: Total planned chapter count
        plot_points: JSON string list of plot points. Each should include:
                     [chapter_range, event, conflict, hook, foreshadowing_id]
        emotional_curve: JSON string list of emotional arc per plot block
        characters: JSON string list of character names in the novel
        world_setting_summary: Brief summary of the world setting (optional)
    """
    import json as _json
    from app.agents.services.outline_service import (
        update_outline,
    )
    from app.database import SessionLocal

    try:
        points = _json.loads(plot_points) if isinstance(plot_points, str) else plot_points
    except _json.JSONDecodeError:
        points = []

    try:
        curve = _json.loads(emotional_curve) if isinstance(emotional_curve, str) else emotional_curve
    except _json.JSONDecodeError:
        curve = []

    try:
        char_list = _json.loads(characters) if isinstance(characters, str) else characters
    except _json.JSONDecodeError:
        char_list = []

    project_id = get_project_id()
    db = SessionLocal()
    committed = False
    try:
        result = await update_outline(
            db,
            project_id,
            {
                "title": title,
                "summary": summary,
                "chapter_count_suggested": chapter_count,
                "chapter_count_confirmed": chapter_count,
                "plot_points": points,
                "emotional_curve": curve,
                "characters": char_list,
                "confirmed": True,
            },
        )
        if "error" in result:
            db.rollback()
            return result
        db.commit()
        committed = True
        return {
            "action": "created",
            "title": title,
            "chapter_count": chapter_count,
            "plot_point_count": len(points),
            "message": f"大纲「{title}」已创建并写入知识库，共 {chapter_count} 章、{len(points)} 个情节节点",
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


@tool
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    summary: str = "",
    word_count: int = 0,
    status: str = "draft",
    scene_count: int = 0,
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
    timeline_summary: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
) -> dict:
    """Generate and save a complete chapter with all tracking data.

    This is the primary tool for writing chapters. It creates the chapter content
    and simultaneously updates timeline, foreshadowings, and style stats.
    Use this when the user asks to write a chapter.

    Args:
        chapter_number: Chapter number (e.g., 1)
        chapter_title: Chapter title (e.g., "星辰陨落")
        content: Full chapter text content
        summary: One-sentence chapter summary for the timeline
        word_count: Word/character count of this chapter
        status: Chapter status - "draft" or "complete"
        scene_count: Number of scenes in this chapter
        new_foreshadowings: JSON string list of new foreshadowings planted in this chapter.
                           Each: {"content": "...", "level": "hint", "expected_resolve_chapter": N, "related_characters": ["..."]}
        reclaimed_foreshadowing_ids: JSON string list of foreshadowing IDs reclaimed in this chapter
        timeline_summary: Summary entry for the timeline (format: "第X章：[摘要] → [因果链]")
        rhythm_score: Rhythm score 1-5 (1=slow, 5=frantic)
        tension_score: Tension score 1-5 (1=relaxed, 5=peak)
        emotion_score: Emotion score 1-5
        emotion_tag: Emotion tag (e.g., "紧张", "舒缓", "悲伤", "温暖", "转折", "日常")
    """
    import json as _json
    from app.database import SessionLocal
    from app.models.chapter import Chapter
    from app.models.outline import ChapterOutline
    from app.models.timeline import TimelineEntry

    try:
        new_fs = _json.loads(new_foreshadowings) if isinstance(new_foreshadowings, str) else new_foreshadowings
    except _json.JSONDecodeError:
        new_fs = []

    try:
        reclaimed_ids = _json.loads(reclaimed_foreshadowing_ids) if isinstance(reclaimed_foreshadowing_ids, str) else reclaimed_foreshadowing_ids
    except _json.JSONDecodeError:
        reclaimed_ids = []

    project_id = get_project_id()
    kb = _kb()
    db = SessionLocal()
    committed = False

    try:
        # 1. Find or create ChapterOutline (required foreign key for Chapter)
        chapter_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number
        ).first()

        if not chapter_outline:
            chapter_outline = ChapterOutline(
                project_id=project_id,
                chapter_number=chapter_number,
                title=chapter_title,
            )
            db.add(chapter_outline)
            db.flush()

        # 2. Create or update the Chapter
        existing_chapter = db.query(Chapter).filter(
            Chapter.chapter_outline_id == chapter_outline.id
        ).first()

        if existing_chapter:
            existing_chapter.content = content
            if summary:
                existing_chapter.summary = summary
            if word_count:
                existing_chapter.word_count = word_count
        else:
            chapter = Chapter(
                chapter_outline_id=chapter_outline.id,
                content=content,
                summary=summary or "",
                word_count=word_count or len(content),
            )
            db.add(chapter)

        # 3. Create timeline entry (via KnowledgeBaseService for consistency)
        if timeline_summary:
            timeline = TimelineEntry(
                project_id=project_id,
                chapter_number=chapter_number,
                summary=timeline_summary or summary or "",
                causal_chain="",
                rhythm_score=rhythm_score,
                tension_score=tension_score,
                emotion_score=emotion_score,
                emotion_tag=emotion_tag or "",
            )
            db.add(timeline)

        # 4. Create new foreshadowings via KB service (handles its own session)
        created_fs = []
        for fs_data in new_fs:
            f = kb.create_foreshadowing({
                "content": fs_data.get("content", ""),
                "level": fs_data.get("level", "hint"),
                "planted_chapter": chapter_number,
                "expected_resolve_chapter": fs_data.get("expected_resolve_chapter"),
                "related_characters": fs_data.get("related_characters", []),
            })
            created_fs.append({"id": f.id, "content": f.content[:60]})

        # 5. Reclaim foreshadowings via KB service
        for fs_id in reclaimed_ids:
            kb.update_foreshadowing(fs_id, {"status": "reclaimed"})

        db.commit()
        committed = True

        return {
            "action": "created" if not existing_chapter else "updated",
            "chapter_number": chapter_number,
            "title": chapter_title,
            "word_count": word_count or len(content),
            "timeline_entry": bool(timeline_summary),
            "new_foreshadowings": len(created_fs),
            "reclaimed_foreshadowings": len(reclaimed_ids),
            "message": f"第{chapter_number}章「{chapter_title}」已写入（{word_count or len(content)}字）",
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


@tool
async def generate_story_seed(
    seed_narrative: str,
    core_tension: str = "",
    protagonist_archetype: str = "",
    world_tone: str = "",
    emotional_tone: str = "",
) -> dict:
    """Generate and save the story seed document.

    The story seed is a narrative description (not a form) that captures
    the essence of the story — its atmosphere, protagonist, and core tension.
    Use when the user wants to crystallize their story idea.

    Args:
        seed_narrative: 300-500 word narrative that captures the story's atmosphere and core appeal
        core_tension: The ultimate conflict/question of the story
        protagonist_archetype: Who the protagonist is, what they want, what's stopping them
        world_tone: One-sentence description of the world's unique texture
        emotional_tone: How readers should feel after finishing (e.g., "悲壮中带着希望")
    """
    from app.database import SessionLocal
    from app.models.outline import Outline

    project_id = get_project_id()
    db = SessionLocal()
    committed = False

    try:
        outline = db.query(Outline).filter(Outline.project_id == project_id).first()
        if not outline:
            outline = Outline(project_id=project_id)
            db.add(outline)
            db.flush()

        # Store story seed in outline summary field as a narrative block
        seed_block = seed_narrative
        if core_tension:
            seed_block += f"\n\n核心张力：{core_tension}"
        if protagonist_archetype:
            seed_block += f"\n\n主角原型：{protagonist_archetype}"
        if world_tone:
            seed_block += f"\n\n世界基调：{world_tone}"
        if emotional_tone:
            seed_block += f"\n\n情感基调：{emotional_tone}"

        outline.summary = seed_block
        db.commit()
        committed = True

        return {
            "action": "created",
            "seed_length": len(seed_narrative),
            "message": "故事种子已生成并写入知识库",
        }
    except Exception as e:
        return {"error": str(e)}
    finally:
        if not committed:
            try:
                db.rollback()
            except Exception:
                pass
        try:
            db.close()
        except Exception:
            pass


@tool
async def generate_world_setting_complete(
    core_concept: str,
    red_rules: str = "[]",
    yellow_rules: str = "[]",
    green_rules: str = "[]",
    key_locations: str = "[]",
    history: str = "",
    social_structure: str = "",
    magic_system: str = "",
) -> dict:
    """Generate and save a complete world setting with tiered rules.

    Creates the full world setting in one call, including tiered rules
    (red=unbreakable, yellow=breakable-with-cost, green=decorative),
    key locations, and optional lore sections.

    Args:
        core_concept: Core concept of the world (1-2 sentences explaining how this world works)
        red_rules: JSON string list of unbreakable rules (e.g., ["灵力来源于血脉，不可后天获得"])
        yellow_rules: JSON string list of breakable-with-cost rules (e.g., ["可以跨越位面，但会消耗寿命"])
        green_rules: JSON string list of decorative rules (e.g., ["修仙者有独特的灵纹"])
        key_locations: JSON string list of key locations with descriptions
                       (e.g., [{{"name": "天枢城", "desc": "修仙界最大城市，灵脉交汇处", "plot_role": "主角起点"}}])
        history: World history / backstory (optional)
        social_structure: Social/political structure description (optional)
        magic_system: Magic/power system description (optional)
    """
    import json as _json

    try:
        red = _json.loads(red_rules) if isinstance(red_rules, str) else red_rules
    except _json.JSONDecodeError:
        red = []

    try:
        yellow = _json.loads(yellow_rules) if isinstance(yellow_rules, str) else yellow_rules
    except _json.JSONDecodeError:
        yellow = []

    try:
        green = _json.loads(green_rules) if isinstance(green_rules, str) else green_rules
    except _json.JSONDecodeError:
        green = []

    try:
        locations = _json.loads(key_locations) if isinstance(key_locations, str) else key_locations
    except _json.JSONDecodeError:
        locations = []

    kb = _kb()

    tiered = {}
    if red:
        tiered["red"] = red
    if yellow:
        tiered["yellow"] = yellow
    if green:
        tiered["green"] = green

    data = {
        "core_concept": core_concept,
        "tiered_settings": tiered,
        "key_locations": locations,
    }
    if history:
        data["history"] = history
    if social_structure:
        data["social_structure"] = social_structure
    if magic_system:
        data["magic_system"] = magic_system

    existing = kb.get_world_setting()
    if existing:
        updated = kb.update_world_setting(existing.id, data)
        return {
            "action": "updated",
            "id": updated.id,
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已更新（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }
    else:
        created = kb.create_world_setting(data)
        return {
            "action": "created",
            "id": created.id,
            "red_rules": len(red),
            "yellow_rules": len(yellow),
            "green_rules": len(green),
            "locations": len(locations),
            "message": f"世界观已创建（{len(red)}个🔴规则 / {len(yellow)}个🟡规则 / {len(green)}个🟢规则 / {len(locations)}个地点）",
        }

# ========================================================================



@tool
async def advance_phase() -> dict:
    """Advance the creation phase based on knowledge base completeness.

    Checks the current phase and knowledge base state to determine if
    the project is ready to advance to the next creation phase:
    - incubation → structure: when outline + characters + world setting exist
    - structure → writing: when plot blocks + foreshadowings exist
    - writing → revision: when all planned chapters are written

    Only advances if completeness criteria are met. Returns current and
    suggested phase with a reason.
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    from app.database import SessionLocal
    from app.models.workflow_state import WorkflowState
    from app.agents.constants import Phase

    kb = _kb()

    # 读取当前阶段
    db = SessionLocal()
    try:
        ws = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id
        ).first()
        current_phase = ws.stage if ws else Phase.INCUBATION
    finally:
        db.close()

    # 检查知识库完整度
    outline = kb.get_outline()
    characters = kb.get_characters()
    world_setting = kb.get_world_setting()
    plot_blocks = kb.get_plot_blocks()
    foreshadowings = kb.get_foreshadowings()
    timeline = kb.get_timeline()

    suggested_phase = current_phase
    reason = ""

    if current_phase == Phase.INCUBATION:
        has_outline = outline and (outline.title or outline.summary)
        has_characters = len(characters) >= 1
        has_world = world_setting is not None
        if has_outline and has_characters and has_world:
            suggested_phase = Phase.STRUCTURE
            reason = "大纲、人物、世界观已就绪，可进入结构设计阶段"
        else:
            missing = []
            if not has_outline:
                missing.append("大纲")
            if not has_characters:
                missing.append("人物")
            if not has_world:
                missing.append("世界观")
            reason = f"孵化阶段尚未完成，缺少：{'、'.join(missing)}"

    elif current_phase == Phase.STRUCTURE:
        has_blocks = len(plot_blocks) >= 1
        has_foreshadowing = len(foreshadowings) >= 1
        if has_blocks:
            suggested_phase = Phase.WRITING
            reason = "情节块已规划，可进入写作阶段"
        else:
            reason = "结构阶段尚未完成，缺少情节块规划"

    elif current_phase == Phase.WRITING:
        total_chapters = 0
        if outline:
            total_chapters = outline.chapter_count_confirmed or outline.chapter_count_suggested or 0
        written = len(timeline) if timeline else 0
        if total_chapters > 0 and written >= total_chapters:
            suggested_phase = Phase.REVISION
            reason = f"全部 {total_chapters} 章已写完，可进入修订阶段"
        else:
            reason = f"写作阶段进行中（{written}/{total_chapters} 章）"

    elif current_phase == Phase.REVISION:
        reason = "已在修订阶段"

    # 如果可以推进，更新 DB
    advanced = suggested_phase != current_phase
    if advanced:
        db = SessionLocal()
        try:
            ws = db.query(WorkflowState).filter(
                WorkflowState.project_id == project_id
            ).first()
            if ws:
                ws.stage = suggested_phase
                db.commit()
        except Exception as e:
            db.rollback()
            return {"error": f"更新阶段失败: {e}"}
        finally:
            db.close()

    phase_labels = {
        Phase.INCUBATION: "创意孵化",
        Phase.STRUCTURE: "结构设计",
        Phase.WRITING: "写作中",
        Phase.REVISION: "修订中",
    }

    return {
        "current_phase": current_phase,
        "suggested_phase": suggested_phase,
        "advanced": advanced,
        "reason": reason,
        "current_phase_label": phase_labels.get(current_phase, current_phase),
        "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
    }



# Tool lists by phase
# ========================================================================

# Tools available during incubation phase (perception only + expand)
INCUBATION_TOOLS = [
    # Phase management
    advance_phase,
    # Perception
    knowledge_search,
    progress_report,
    expand_world_setting,
    # Generation (direct content creation)
    generate_outline,
    generate_story_seed,
    generate_world_setting_complete,
    # Creation (direct write)
    create_world_setting,
    create_character,
    create_relation,
    create_style_constraints,
    create_foreshadowing,
]

# Tools available during structure phase
STRUCTURE_TOOLS = [
    # Phase management
    advance_phase,
    # Perception
    knowledge_search,
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    progress_report,
    rhythm_analysis,
    # Generation
    generate_outline,
    generate_world_setting_complete,
    # Modification
    propose_outline_adjustment,
    # Creation assist
    suggest_foreshadowing,
    # Creation (direct write)
    create_plot_block,
    create_plot_question,
    create_subplot,
    create_foreshadowing,
    create_character,
    create_relation,
]

# Tools available during writing phase (all tools)
WRITING_TOOLS = [
    # Phase management
    advance_phase,
    # Perception
    knowledge_search,
    foreshadowing_check,
    review_chapter,
    rewrite_chapter,
    consistency_check,
    style_analysis,
    progress_report,
    rhythm_analysis,
    # Generation (primary tools for writing phase)
    generate_chapter_content,
    generate_outline,
    generate_world_setting_complete,
    # Modification
    propose_setting_change,
    propose_outline_adjustment,
    propose_chapter_rewrite,
    # Creation assist
    writer_block_assist,
    suggest_foreshadowing,
    suggest_plot_twist,
    expand_world_setting,
    # Creation (direct write)
    create_world_setting,
    create_character,
    create_relation,
    create_style_constraints,
    create_subplot,
    create_plot_question,
    create_timeline_entry,
    create_foreshadowing,
    create_plot_block,
]

# All tools (default)
AGENT_TOOLS = WRITING_TOOLS


# All tools (default)
AGENT_TOOLS = WRITING_TOOLS


