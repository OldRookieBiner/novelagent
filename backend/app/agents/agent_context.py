"""Phase-aware context builder for the Free Operation Agent

Reads project data via KnowledgeBaseService facade.
Store 返回 dict，无需 _serialize。
Token 估算使用 token_budget.estimate_tokens。

Priorities differ by phase:
- incubation: outline + world setting basics
- structure: outline + characters + plot blocks + foreshadowing
- writing: outline + characters + foreshadowing + style + timeline
- revision: full outline + all tracking data
"""

import json

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.token_budget import estimate_tokens
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


def build_agent_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
) -> dict:
    """构建阶段感知的项目上下文。

    通过 KnowledgeBaseService facade 读取数据，返回上下文字典供调用方格式化。
    当 max_tokens <= 5000 时自动切换为轻量模式（只加载核心索引），
    详细信息由 Agent 通过 knowledge_search 按需获取。
    """
    # 小 token 预算自动切换为轻量模式
    if max_tokens <= 5000:
        return build_lightweight_context(
            project_id, phase, current_chapter_number, max_tokens
        )

    kb = KnowledgeBaseService(project_id)
    budget = BudgetTracker(max_tokens)
    context: dict = {}

    # === Always load: outline ===
    outline = kb.outlines.get()
    if outline:
        outline_json = json.dumps(outline, ensure_ascii=False)
        tokens = estimate_tokens(outline_json)
        if budget.can_add(tokens):
            context["outline"] = outline
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
    ws = kb.world_setting.get()
    if ws:
        data_json = json.dumps(ws, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = ws
            budget.add(estimate_tokens(data_json))


def _load_structure_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    chars = kb.characters.list_characters()
    char_list = []
    for c in chars:
        info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or ""}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    blocks = kb.plots.list_plot_blocks()
    block_list = []
    for b in blocks:
        info = {"id": b["id"], "title": b["title"], "chapter_start": b["chapter_start"], "chapter_end": b.get("chapter_end"), "expected_mood": b.get("expected_mood")}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            block_list.append(info)
            budget.add(tokens)
    context["plot_blocks"] = block_list

    foreshadowings = kb.foreshadowings.list_foreshadowings()
    fs_list = []
    for f in foreshadowings:
        info = {"id": f["id"], "content": (f.get("content") or "")[:60], "planted_chapter": f.get("planted_chapter"), "expected_resolve_chapter": f.get("expected_resolve_chapter"), "status": f.get("status")}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            fs_list.append(info)
            budget.add(tokens)
    context["foreshadowings"] = fs_list


def _load_writing_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict, current_chapter_number: int | None):
    chars = kb.characters.list_characters()
    char_list = []
    for c in chars:
        info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or "", "personality": (c.get("personality") or "")[:100]}
        info_json = json.dumps(info, ensure_ascii=False)
        tokens = estimate_tokens(info_json)
        if budget.can_add(tokens):
            char_list.append(info)
            budget.add(tokens)
    context["characters"] = char_list

    ws = kb.world_setting.get()
    if ws:
        data = {"core_concept": ws.get("core_concept") or "", "red_settings": (ws.get("tiered_settings") or {}).get("red", []), "key_locations": ws.get("key_locations") or []}
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["world_setting"] = data
            budget.add(estimate_tokens(data_json))

    pending = kb.foreshadowings.list_pending()
    overdue = kb.foreshadowings.list_overdue(current_chapter_number) if current_chapter_number else []
    context["pending_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in pending]
    context["overdue_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in overdue]

    style = kb.styles.get_constraints()
    if style:
        data = {"taboo_words": style.get("taboo_words") or [], "forbidden_patterns": style.get("forbidden_patterns") or [], "abstract_rules": style.get("abstract_rules") or []}
        data_json = json.dumps(data, ensure_ascii=False)
        if budget.can_add(estimate_tokens(data_json)):
            context["style_constraints"] = data
            budget.add(estimate_tokens(data_json))

    # 当前章节大纲
    if current_chapter_number:
        try:
            co = kb.outlines.get_chapter_outline(current_chapter_number)
            if co:
                co_data = {
                    "chapter_number": co.get("chapter_number"),
                    "title": co.get("title") or "",
                    "scene": co.get("scene") or "",
                    "characters": co.get("characters") or "",
                    "plot": co.get("plot") or "",
                    "conflict": co.get("conflict") or "",
                    "turning_point": co.get("turning_point") or "",
                    "hook": co.get("hook") or "",
                    "transition": co.get("transition") or "",
                    "ending": co.get("ending") or "",
                    "opening_state": co.get("opening_state") or "",
                    "emotional_arc": co.get("emotional_arc") or "",
                    "key_scenes": co.get("key_scenes") or [],
                    "pacing_note": co.get("pacing_note") or "",
                    "target_words": co.get("target_words"),
                    "confirmed": co.get("confirmed"),
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                co_tokens = estimate_tokens(co_json)
                if budget.can_add(co_tokens):
                    context["current_chapter_outline"] = co_data
                    budget.add(co_tokens)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("加载当前章节大纲失败: %s", e)

    # 上一章结尾 500 字
    if current_chapter_number and current_chapter_number > 1:
        prev = kb.chapters.get_by_number(current_chapter_number - 1)
        if prev and prev.get("content"):
            content = prev["content"]
            closing = content[-500:] if len(content) > 500 else content
            closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
            closing_tokens = estimate_tokens(closing_json)
            if budget.can_add(closing_tokens):
                context["previous_chapter_closing"] = closing.strip()
                budget.add(closing_tokens)

    # 最近的变更决策
    recent_decisions = kb.changes.list_changes(status="applied")
    if recent_decisions:
        decision_list = []
        for d in recent_decisions[:5]:
            decision_list.append({
                "target_type": d.get("target_type"),
                "decision": d.get("author_decision", "unknown"),
                "summary": (d.get("description") or "")[:80],
            })
        decision_json = json.dumps(decision_list, ensure_ascii=False)
        decision_tokens = estimate_tokens(decision_json)
        if budget.can_add(decision_tokens):
            context["recent_decisions"] = decision_list
            budget.add(decision_tokens)

    if current_chapter_number:
        block = kb.plots.get_current_plot_block(current_chapter_number)
        if block:
            context["current_plot_block"] = {"title": block.get("title"), "expected_mood": block.get("expected_mood"), "must_happen": block.get("must_happen") or []}

        questions = kb.plots.get_questions_for_chapter(current_chapter_number)
        context["questions_for_chapter"] = [{"id": q["id"], "question": (q.get("question_text") or "")[:60]} for q in questions]

    timeline = kb.timelines.list_timeline()
    if timeline:
        recent = timeline[:5]
        context["recent_timeline"] = [{"chapter": t.get("chapter_number"), "summary": (t.get("summary") or "")[:80], "emotion_tag": t.get("emotion_tag")} for t in recent]

    # 关系演变规划
    if current_chapter_number:
        pending_plans = kb.characters.list_evolution_plans_triggering_at(current_chapter_number)
        if pending_plans:
            evolution_cues = []
            # plans 只含 dict，不含 relation 对象名，需要额外查询
            relations = kb.characters.list_relations()
            rel_map = {r["id"]: r for r in relations}
            # 同时需要角色名
            char_map = {c["id"]: c["name"] for c in kb.characters.list_characters()}

            for plan in pending_plans:
                rel = rel_map.get(plan.get("relation_id"), {})
                char_a_name = char_map.get(rel.get("character_a_id"), "?")
                char_b_name = char_map.get(rel.get("character_b_id"), "?")
                cue = (
                    f"第{plan.get('trigger_chapter')}章，{char_a_name}和{char_b_name}的关系将发生变化："
                    f"{plan.get('status_before') or '待定'} → {plan.get('status_after', '未知')}，"
                    f"信任度 {plan.get('trust_before') or 50} → {plan.get('trust_after') or 50}。"
                    f"事件：{plan.get('event_description', '')}"
                )
                evolution_cues.append(cue)
            cues_json = json.dumps(evolution_cues, ensure_ascii=False)
            cues_tokens = estimate_tokens(cues_json)
            if budget.can_add(cues_tokens):
                context["relation_evolution_cues"] = evolution_cues
                budget.add(cues_tokens)

    # 前置条件校验
    prereq = kb.validate_prerequisites(current_chapter_number)
    context["prerequisites"] = prereq


def _load_revision_context(kb: KnowledgeBaseService, budget: BudgetTracker, context: dict):
    """修订阶段上下文加载 - 使用 BudgetTracker 逐项控制"""
    import json

    # 1. world_setting 精简版：core_concept + red_settings + key_locations
    ws_tokens = estimate_tokens("world_setting")
    if budget.can_add(ws_tokens):
        ws = kb.world_setting.get()
        if ws:
            ws_mini = {
                "core_concept": ws.get("core_concept", ""),
                "red_settings": (ws.get("tiered_settings") or {}).get("red", []),
                "key_locations": ws.get("key_locations", []),
            }
            ws_json = json.dumps(ws_mini, ensure_ascii=False)
            if budget.can_add(estimate_tokens(ws_json)):
                context["world_setting"] = ws_mini
                budget.add(estimate_tokens(ws_json))

    # 2. characters 索引模式：id + name + role（不含 backstory）
    chars_tokens = estimate_tokens("characters")
    if budget.can_add(chars_tokens):
        chars = kb.characters.list_characters()
        chars_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
        chars_json = json.dumps(chars_index, ensure_ascii=False)
        if budget.can_add(estimate_tokens(chars_json)):
            context["characters"] = chars_index
            budget.add(estimate_tokens(chars_json))

    # 3. foreshadowings 精简：id + content[:60] + status + planted_chapter + expected_resolve_chapter
    fs_tokens = estimate_tokens("foreshadowings")
    if budget.can_add(fs_tokens):
        foreshadowings = kb.foreshadowings.list_foreshadowings()
        fs_mini = [
            {
                "id": f["id"],
                "content": (f.get("content") or "")[:60],
                "status": f.get("status"),
                "planted_chapter": f.get("planted_chapter"),
                "expected_resolve_chapter": f.get("expected_resolve_chapter"),
            }
            for f in foreshadowings
        ]
        fs_json = json.dumps(fs_mini, ensure_ascii=False)
        if budget.can_add(estimate_tokens(fs_json)):
            context["foreshadowings"] = fs_mini
            budget.add(estimate_tokens(fs_json))

    # 4. timeline 最近 20 章摘要
    tl_tokens = estimate_tokens("timeline")
    if budget.can_add(tl_tokens):
        timeline = kb.timelines.list_timeline()
        recent_timeline = timeline[:20] if len(timeline) > 20 else timeline
        tl_mini = [
            {
                "chapter_number": t.get("chapter_number"),
                "summary": (t.get("summary") or "")[:80],
                "emotion_tag": t.get("emotion_tag"),
            }
            for t in recent_timeline
        ]
        tl_json = json.dumps(tl_mini, ensure_ascii=False)
        if budget.can_add(estimate_tokens(tl_json)):
            context["timeline"] = tl_mini
            budget.add(estimate_tokens(tl_json))

    # 5. plot_questions 只加载 pending 状态
    pq_tokens = estimate_tokens("plot_questions")
    if budget.can_add(pq_tokens):
        questions = kb.plots.list_plot_questions(status="pending")
        pq_json = json.dumps(questions, ensure_ascii=False)
        if budget.can_add(estimate_tokens(pq_json)):
            context["plot_questions"] = questions
            budget.add(estimate_tokens(pq_json))

    # 6. subplots 只加载非 abandoned 状态
    sub_tokens = estimate_tokens("subplots")
    if budget.can_add(sub_tokens):
        all_subplots = kb.plots.list_subplots()
        active_subplots = [s for s in all_subplots if s.get("current_status") != "abandoned"]
        sub_json = json.dumps(active_subplots, ensure_ascii=False)
        if budget.can_add(estimate_tokens(sub_json)):
            context["subplots"] = active_subplots
            budget.add(estimate_tokens(sub_json))

    # 7. style_snapshots 只加载最近 10 条
    ss_tokens = estimate_tokens("style_snapshots")
    if budget.can_add(ss_tokens):
        snapshots = kb.styles.list_snapshots(last_n=10)
        ss_json = json.dumps(snapshots, ensure_ascii=False)
        if budget.can_add(estimate_tokens(ss_json)):
            context["style_snapshots"] = snapshots
            budget.add(estimate_tokens(ss_json))

    # 8. style_constraints 保留（走预算检查）
    style_tokens = estimate_tokens("style_constraints")
    if budget.can_add(style_tokens):
        style = kb.styles.get_constraints()
        if style:
            style_json = json.dumps(style, ensure_ascii=False)
            if budget.can_add(estimate_tokens(style_json)):
                context["style_constraints"] = style
                budget.add(estimate_tokens(style_json))


def build_lightweight_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 4000,
) -> dict:
    """构建轻量级上下文 — 只包含核心索引，详细信息由 Agent 通过 knowledge_search 按需获取。

    预期从 ~12K token 降到 ~3-4K token。
    """
    kb = KnowledgeBaseService(project_id)
    budget = BudgetTracker(max_tokens)
    context: dict = {}

    # 核心索引：大纲标题 + 总章数
    outline = kb.outlines.get()
    if outline:
        outline_index = {
            "title": outline.get("title") or "未命名",
            "chapter_count": outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0,
            "summary": (outline.get("summary") or "")[:100],
        }
        context["outline_index"] = outline_index
        budget.add(estimate_tokens(json.dumps(outline_index, ensure_ascii=False)))

    # 角色名+ID 列表（不包含完整 backstory）
    chars = kb.characters.list_characters()
    char_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
    context["character_index"] = char_index
    budget.add(estimate_tokens(json.dumps(char_index, ensure_ascii=False)))

    # 当前阶段 + 当前章节号
    context["phase"] = phase
    if current_chapter_number:
        context["current_chapter_number"] = current_chapter_number

    # 关键红色设定（最多 3 条）
    ws = kb.world_setting.get()
    if ws:
        red = (ws.get("tiered_settings") or {}).get("red", [])
        if red:
            context["critical_rules"] = red[:3]
            budget.add(estimate_tokens(json.dumps(red[:3], ensure_ascii=False)))

    # 写作阶段：预取当前章节大纲 + 上一章结尾
    if phase in (Phase.WRITING.value, Phase.REVISION.value) and current_chapter_number:
        try:
            co = kb.outlines.get_chapter_outline(current_chapter_number)
            if co:
                co_data = {
                    "chapter_number": co.get("chapter_number"),
                    "title": co.get("title") or "",
                    "scene": co.get("scene") or "",
                    "characters": co.get("characters") or "",
                    "emotional_arc": co.get("emotional_arc") or "",
                    "key_scenes": co.get("key_scenes") or [],
                    "target_words": co.get("target_words"),
                }
                co_json = json.dumps(co_data, ensure_ascii=False)
                if budget.can_add(estimate_tokens(co_json)):
                    context["current_chapter_outline"] = co_data
                    budget.add(estimate_tokens(co_json))
        except Exception:
            pass

        if current_chapter_number > 1:
            prev = kb.chapters.get_by_number(current_chapter_number - 1)
            if prev and prev.get("content"):
                closing = prev["content"][-300:]
                closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
                if budget.can_add(estimate_tokens(closing_json)):
                    context["previous_chapter_closing"] = closing.strip()
                    budget.add(estimate_tokens(closing_json))

    context["_budget_used"] = budget.used
    context["_budget_max"] = budget.max
    context["_mode"] = "lightweight"
    return context
