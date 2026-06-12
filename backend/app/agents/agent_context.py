"""Phase-aware context builder for the Free Operation Agent

Reads project data via KnowledgeBaseService (shared with the main writing loop).
Injects a prioritized, token-budget-constrained context into the agent system prompt.

Priorities differ by phase:
- incubation: outline + world setting basics
- structure: outline + characters + plot blocks + foreshadowing
- writing: outline + characters + foreshadowing + style + timeline
- revision: full outline + all tracking data
"""

import json
import re

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.constants import Phase


class BudgetTracker:
    """Token budget tracker"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)


def estimate_tokens(text: str) -> int:
    """Estimate token count: Chinese chars x2, English words x1.3"""
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return int(chinese_chars * 2 + english_words * 1.3)


def _serialize(obj) -> dict | list:
    """Serialize ORM object to dict (handles detached sessions)."""
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
    return obj if isinstance(obj, (dict, list)) else str(obj)


def build_agent_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
) -> dict:
    """Build phase-aware project context for the agent system prompt.

    Uses KnowledgeBaseService (independent sessions per read).
    Returns a dict with context sections to be formatted by the caller.
    """
    kb = KnowledgeBaseService(project_id)
    budget = BudgetTracker(max_tokens)
    context: dict = {}

    # === Always load: outline ===
    outline = kb.get_outline()
    if outline:
        outline_data = _serialize(outline)
        outline_json = json.dumps(outline_data, ensure_ascii=False)
        tokens = estimate_tokens(outline_json)
        if budget.can_add(tokens):
            context["outline"] = outline_data
            budget.add(tokens)

    # === Phase-specific loading ===
    if phase == Phase.INCUBATION.value:
        _load_incubation_context(kb, budget, context)
    elif phase == Phase.STRUCTURE.value:
        _load_structure_context(kb, budget, context)
    elif phase == Phase.WRITING.value:
        _load_writing_context(kb, budget, context, current_chapter_number)
    elif phase == Phase.REVISION.value:
        _load_revision_context(kb, budget, context)

    context["_budget_used"] = budget.used
    context["_budget_max"] = budget.max
    return context


def _load_incubation_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    ws = kb.get_world_setting()
    if ws:
        data = _serialize(ws)
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = data
            budget.add(estimate_tokens(data_json))


def _load_structure_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    chars = kb.get_characters()
    char_list = []
    for c in chars:
        info = {"id": c.id, "name": c.name, "role": c.role, "core_motivation": c.core_motivation or ""}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    blocks = kb.get_plot_blocks()
    block_list = []
    for b in blocks:
        info = {"id": b.id, "title": b.title, "chapter_start": b.chapter_start, "chapter_end": b.chapter_end, "expected_mood": b.expected_mood}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            block_list.append(info)
            budget.add(tokens)
    context["plot_blocks"] = block_list

    foreshadowings = kb.get_foreshadowings()
    fs_list = []
    for f in foreshadowings:
        info = {"id": f.id, "content": f.content[:60], "planted_chapter": f.planted_chapter, "expected_resolve_chapter": f.expected_resolve_chapter, "status": f.status}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            fs_list.append(info)
            budget.add(tokens)
    context["foreshadowings"] = fs_list


def _load_writing_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict, current_chapter_number: int | None):
    chars = kb.get_characters()
    char_list = []
    for c in chars:
        info = {"id": c.id, "name": c.name, "role": c.role, "core_motivation": c.core_motivation or "", "personality": (c.personality or "")[:100]}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    ws = kb.get_world_setting()
    if ws:
        data = {"core_concept": ws.core_concept or "", "red_settings": ws.tiered_settings.get("red", []) if ws.tiered_settings else [], "key_locations": ws.key_locations or []}
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = data
            budget.add(estimate_tokens(data_json))

    pending = kb.get_pending_foreshadowings()
    overdue = kb.get_overdue_foreshadowings(current_chapter_number) if current_chapter_number else []
    context["pending_foreshadowings"] = [{"id": f.id, "content": f.content[:60], "expected_resolve_chapter": f.expected_resolve_chapter} for f in pending]
    context["overdue_foreshadowings"] = [{"id": f.id, "content": f.content[:60], "expected_resolve_chapter": f.expected_resolve_chapter} for f in overdue]

    style = kb.get_style_constraints()
    if style:
        data = {"taboo_words": style.taboo_words or [], "forbidden_patterns": style.forbidden_patterns or [], "abstract_rules": style.abstract_rules or []}
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["style_constraints"] = data
            budget.add(estimate_tokens(data_json))

    # 当前章节大纲（让 Agent 写正文时参考规划）
    if current_chapter_number:
        from app.database import SessionLocal as _SL
        from app.models.outline import ChapterOutline as _CO
        _db = _SL()
        try:
            _co = _db.query(_CO).filter(
                _CO.project_id == kb.project_id,
                _CO.chapter_number == current_chapter_number,
            ).first()
            if _co:
                co_data = {
                    "chapter_number": _co.chapter_number,
                    "title": _co.title or "",
                    "scene": _co.scene or "",
                    "characters": _co.characters or "",
                    "plot": _co.plot or "",
                    "conflict": _co.conflict or "",
                    "turning_point": _co.turning_point or "",
                    "hook": _co.hook or "",
                    "transition": _co.transition or "",
                    "ending": _co.ending or "",
                    "opening_state": getattr(_co, "opening_state", None) or "",
                    "emotional_arc": getattr(_co, "emotional_arc", None) or "",
                    "key_scenes": getattr(_co, "key_scenes", None) or [],
                    "pacing_note": getattr(_co, "pacing_note", None) or "",
                    "target_words": _co.target_words,
                    "confirmed": _co.confirmed,
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                co_tokens = estimate_tokens(co_json)
                if budget.can_add(co_tokens):
                    context["current_chapter_outline"] = co_data
                    budget.add(co_tokens)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("加载当前章节大纲失败: %s", e)
        finally:
            try:
                _db.close()
            except Exception:
                pass

    # 上一章结尾 500 字（确保下章开头的场景衔接）
    if current_chapter_number and current_chapter_number > 1:
        prev = kb.get_chapter_by_number(current_chapter_number - 1)
        if prev and prev.content:
            closing = prev.content[-500:] if len(prev.content) > 500 else prev.content
            closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
            closing_tokens = estimate_tokens(closing_json)
            if budget.can_add(closing_tokens):
                context["previous_chapter_closing"] = closing.strip()
                budget.add(closing_tokens)

    # 最近的变更决策（让 Agent 知道用户已经批准/放弃了哪些修改）
    recent_decisions = kb.get_setting_changes(status="applied")
    if recent_decisions:
        decision_list = []
        for d in recent_decisions[:5]:
            decision_list.append({
                "target_type": d.target_type,
                "decision": getattr(d, "author_decision", "unknown"),
                "summary": (d.description or "")[:80],
            })
        decision_json = json.dumps(decision_list, ensure_ascii=False)
        decision_tokens = estimate_tokens(decision_json)
        if budget.can_add(decision_tokens):
            context["recent_decisions"] = decision_list
            budget.add(decision_tokens)

    if current_chapter_number:
        block = kb.get_current_plot_block(current_chapter_number)
        if block:
            context["current_plot_block"] = {"title": block.title, "expected_mood": block.expected_mood, "must_happen": block.must_happen or []}

        questions = kb.get_questions_for_chapter(current_chapter_number)
        context["questions_for_chapter"] = [{"id": q.id, "question": q.question_text[:60]} for q in questions]

    timeline = kb.get_timeline()
    if timeline:
        recent = timeline[:5]
        context["recent_timeline"] = [{"chapter": t.chapter_number, "summary": (t.summary or "")[:80], "emotion_tag": t.emotion_tag} for t in recent]

    # 关系演变规划（让 LLM 知道当前章节的关系变化）
    if current_chapter_number:
        pending_plans = kb.get_evolution_plans_triggering_at(current_chapter_number)
        if pending_plans:
            evolution_cues = []
            for plan in pending_plans:
                char_a = plan.relation.character_a.name
                char_b = plan.relation.character_b.name
                cue = (
                    f"第{plan.trigger_chapter}章，{char_a}和{char_b}的关系将发生变化："
                    f"{plan.status_before or '待定'} → {plan.status_after}，"
                    f"信任度 {plan.trust_before or 50} → {plan.trust_after or 50}。"
                    f"事件：{plan.event_description}"
                )
                evolution_cues.append(cue)
            cues_json = json.dumps(evolution_cues, ensure_ascii=False)
            cues_tokens = estimate_tokens(cues_json)
            if budget.can_add(cues_tokens):
                context["relation_evolution_cues"] = evolution_cues
                budget.add(cues_tokens)

    # 前置条件校验
    prereq = validate_prerequisites(kb.project_id, current_chapter_number)
    context["prerequisites"] = prereq


def _load_revision_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    chars = kb.get_characters()
    context["characters"] = _serialize(chars)
    foreshadowings = kb.get_foreshadowings()
    context["foreshadowings"] = _serialize(foreshadowings)
    questions = kb.get_plot_questions()
    context["plot_questions"] = _serialize(questions)
    subplots = kb.get_subplots()
    context["subplots"] = _serialize(subplots)
    timeline = kb.get_timeline()
    context["timeline"] = _serialize(timeline)
    style = kb.get_style_constraints()
    if style:
        context["style_constraints"] = _serialize(style)
    snapshots = kb.get_style_snapshots()
    context["style_snapshots"] = _serialize(snapshots)


# Model context window defaults
_MODEL_CONTEXT_WINDOW_DEFAULTS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "claude-3.5-sonnet": 200000,
    "claude-sonnet-4-6": 200000,
    "deepseek-v3": 128000,
    "deepseek-r1": 128000,
    "qwen-plus": 131072,
}

DEFAULT_CONTEXT_WINDOW = 128000


def get_context_window(model_config, model_name: str | None = None) -> int:
    """Get model context window size.

    优先级：
    1. 子模型的 context_window（coding_plan 类型 + model_name 指定时）
    2. 配置级别的 context_window
    3. 硬编码映射表
    4. 默认值
    """
    # 优先查找子模型的 context_window
    if model_config and model_name and model_config.models:
        for m in model_config.models:
            if m.get("is_enabled", True) and (m.get("id") == model_name or m.get("name") == model_name):
                if m.get("context_window"):
                    return m["context_window"]
                break

    if model_config and model_config.context_window:
        return model_config.context_window
    fallback_name = model_name or ((model_config.model_name or "") if model_config else "")
    return _MODEL_CONTEXT_WINDOW_DEFAULTS.get(fallback_name, DEFAULT_CONTEXT_WINDOW)



def validate_prerequisites(project_id: int, current_chapter: int | None) -> dict:
    """校验写作前置条件，返回 blocked 和 warnings 列表

    每个检查项独立 try-except，单项查询失败不影响其他检查项。
    失败的检查项记入 errors 列表。
    """
    from app.database import SessionLocal
    from app.models.outline import ChapterOutline
    from app.models.character import Character, EvolutionPlan, Relation
    from app.models.world_setting import WorldSetting
    from app.models.foreshadowing import Foreshadowing
    from app.models.style_constraints import StyleConstraints
    from app.models.plot_structure import PlotBlock
    from app.models.chapter import Chapter
    from app.models.timeline import TimelineEntry

    db = SessionLocal()
    blocked = []
    warnings = []
    errors = []

    try:
        # === 关键项检查 ===

        # 1. 章节大纲记录存在 + 已确认
        if current_chapter:
            try:
                co = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == current_chapter,
                ).first()
                if not co:
                    blocked.append({
                        "type": "chapter_outline_missing",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲不存在",
                        "severity": "error",
                    })
                elif not co.confirmed:
                    blocked.append({
                        "type": "outline_unconfirmed",
                        "chapter": current_chapter,
                        "message": f"第{current_chapter}章大纲尚未确认",
                        "severity": "error",
                    })
            except Exception as e:
                errors.append({"type": "chapter_outline_check", "message": str(e)})

        # 2. 角色存在
        try:
            char_count = db.query(Character).filter(Character.project_id == project_id).count()
            if char_count == 0:
                blocked.append({
                    "type": "character_missing",
                    "message": "项目中没有任何角色",
                    "severity": "error",
                })
        except Exception as e:
            errors.append({"type": "character_check", "message": str(e)})

        # 3. 世界观存在（core_concept 非空）
        try:
            ws = db.query(WorldSetting).filter(WorldSetting.project_id == project_id).first()
            if not ws or not ws.core_concept:
                blocked.append({
                    "type": "world_setting_missing",
                    "message": "项目世界观尚未完善",
                    "severity": "error",
                })
        except Exception as e:
            errors.append({"type": "world_setting_check", "message": str(e)})

        # === 次要项检查 ===

        # 4. 伏笔记录
        try:
            fs_count = db.query(Foreshadowing).filter(Foreshadowing.project_id == project_id).count()
            if fs_count == 0:
                warnings.append({
                    "type": "foreshadowing_empty",
                    "message": "当前无伏笔记录",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "foreshadowing_check", "message": str(e)})

        # 5. 风格约束
        try:
            style = db.query(StyleConstraints).filter(StyleConstraints.project_id == project_id).first()
            if not style:
                warnings.append({
                    "type": "style_constraints_missing",
                    "message": "尚未设置风格约束",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "style_check", "message": str(e)})

        # 6. 情节块
        try:
            block_count = db.query(PlotBlock).filter(PlotBlock.project_id == project_id).count()
            if block_count == 0:
                warnings.append({
                    "type": "plot_block_empty",
                    "message": "尚未创建情节块",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "plot_block_check", "message": str(e)})

        # 7. 上一章结尾内容
        if current_chapter and current_chapter > 1:
            try:
                prev_co = db.query(ChapterOutline).filter(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == current_chapter - 1,
                ).first()
                if prev_co:
                    prev_ch = db.query(Chapter).filter(
                        Chapter.chapter_outline_id == prev_co.id
                    ).first()
                    if not prev_ch or not prev_ch.content:
                        warnings.append({
                            "type": "previous_chapter_empty",
                            "chapter": current_chapter - 1,
                            "message": f"第{current_chapter - 1}章尚无正文",
                            "severity": "warning",
                        })
            except Exception as e:
                errors.append({"type": "previous_chapter_check", "message": str(e)})

        # 8. 关系演变规划
        try:
            plan_count = db.query(EvolutionPlan).filter(
                EvolutionPlan.relation.has(Relation.project_id == project_id)
            ).count()
            if plan_count == 0:
                warnings.append({
                    "type": "relation_evolution_empty",
                    "message": "尚未创建关系演变规划",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "evolution_check", "message": str(e)})

        # 9. 时间线记录
        try:
            timeline_count = db.query(TimelineEntry).filter(
                TimelineEntry.project_id == project_id
            ).count()
            if timeline_count == 0:
                warnings.append({
                    "type": "timeline_empty",
                    "message": "尚未创建时间线记录",
                    "severity": "warning",
                })
        except Exception as e:
            errors.append({"type": "timeline_check", "message": str(e)})

    finally:
        db.close()

    result = {
        "blocked": blocked,
        "warnings": warnings,
        "validated": True,
    }
    if errors:
        result["errors"] = errors
    return result
