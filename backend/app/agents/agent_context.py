"""统一上下文组装器 — ProjectContextAssembler

替代原 build_agent_context，整合 BudgetAllocator 动态预算分配 +
context_strategy 前文策略 + batch_read 批量读取 + ContextCache 缓存。

三层架构：
  BudgetAllocator（预算分配）→ ProjectContextAssembler（数据组装 + 前文策略集成）→ agent.py（prompt 填充）
"""

import json

from app.agents.services.knowledge_base import KnowledgeBaseService
from app.agents.token_budget import estimate_tokens
from app.agents.constants import Phase
from app.agents.budget_allocator import BudgetAllocator
from app.agents.context_cache import context_cache
from app.agents.context_strategy import select_strategy

# 轻量模式触发比例
_LIGHTWEIGHT_RATIO = 0.05


class BudgetTracker:
    """Token budget tracker"""

    def __init__(self, max_tokens: int):
        self.max = max_tokens
        self.used = 0
        self.llm_tool_tokens_used = 0

    def can_add(self, tokens: int) -> bool:
        return self.used + tokens <= self.max

    def add(self, tokens: int):
        self.used += tokens

    def remaining(self) -> int:
        return max(0, self.max - self.used)

    def should_throttle_llm_tool(self) -> bool:
        """当剩余预算 < 20% 时，建议节流 LLM 工具"""
        if self.max <= 0:
            return False
        remaining = 1 - (self.used / self.max)
        return remaining < 0.2


class ProjectContextAssembler:
    """统一上下文组装器

    协调项目数据加载、前文策略、预算分配、缓存。
    输出为 dict，包含 project_data 和 previous_text 两个顶层 key。
    """

    # 可缓存的数据类型
    _CACHEABLE_TYPES = frozenset({"world_setting", "characters", "style_constraints", "outline"})

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.kb = KnowledgeBaseService(project_id)

    def build(
        self,
        context_window: int,
        phase: str,
        current_chapter_number: int | None = None,
        strategy_name: str | None = None,
    ) -> dict:
        """构建完整上下文

        Args:
            context_window: 模型上下文窗口大小
            phase: 当前阶段
            current_chapter_number: 当前章节号
            strategy_name: 用户指定的前文策略名

        Returns:
            dict with project_data, previous_text, loaded_keys, _budget_used, _budget_max
        """
        # 轻量模式：极小窗口时只加载核心索引
        if context_window <= 10000:
            return self._build_lightweight(context_window, phase, current_chapter_number)

        # 预算分配
        allocation = BudgetAllocator.allocate(context_window, phase)

        # 批量读取 + 缓存
        raw_data = self._load_with_cache(current_chapter_number)

        # 阶段感知数据裁剪
        project_data = self._load_phase_data(raw_data, phase, allocation, current_chapter_number)

        # 前文策略
        previous_text = self._load_previous_context(
            raw_data, phase, allocation, current_chapter_number, strategy_name
        )

        # 去重：Full 策略时 previous_chapter_closing 已被前文包含
        if previous_text and "previous_chapter_closing" in project_data:
            del project_data["previous_chapter_closing"]

        # 总量超窗口保护
        project_data_str = json.dumps(project_data, ensure_ascii=False, default=str)
        total_used = estimate_tokens(project_data_str) + estimate_tokens(previous_text)
        max_available = context_window - allocation.output_budget - allocation.safety_margin

        if total_used > max_available:
            # 自动压缩 Important 数据
            compressible_keys = [
                k for k in project_data
                if k not in ("outline", "style_constraints", "current_chapter_outline",
                             "pending_foreshadowings", "overdue_foreshadowings",
                             "critical_rules", "current_plot_block")
            ]
            for key in compressible_keys:
                removed = project_data.pop(key, None)
                if removed is not None:
                    removed_str = json.dumps(removed, ensure_ascii=False, default=str)
                    total_used -= estimate_tokens(removed_str)
                if total_used <= max_available:
                    break
            # 重新计算
            project_data_str = json.dumps(project_data, ensure_ascii=False, default=str)
            total_used = estimate_tokens(project_data_str) + estimate_tokens(previous_text)

        loaded_keys = list(project_data.keys())

        return {
            "project_data": project_data,
            "previous_text": previous_text,
            "loaded_keys": loaded_keys,
            "_budget_used": estimate_tokens(json.dumps(project_data, ensure_ascii=False, default=str)),
            "_budget_max": context_window,
        }

    def _load_with_cache(self, current_chapter_number: int | None) -> dict:
        """批量读取 + 缓存覆盖

        始终走 batch_read（需不可缓存数据如 chapters/timeline），
        但缓存命中数据覆盖 raw 中的对应字段，避免重复 DB 查询。
        """
        raw = self.kb.batch_read_for_context(current_chapter_number)

        # 缓存命中覆盖
        for data_type in self._CACHEABLE_TYPES:
            version = self.kb.characters.get_version(data_type) if hasattr(self.kb.characters, 'get_version') else 0
            # 使用 _BaseStore.get_version
            from app.agents.services.stores.base import _BaseStore
            version = _BaseStore.get_version(data_type)
            cached = context_cache.get(self.project_id, data_type, version)
            if cached is not None:
                raw[data_type] = cached

        # 写入缓存
        for data_type in self._CACHEABLE_TYPES:
            if data_type in raw and raw[data_type] is not None:
                from app.agents.services.stores.base import _BaseStore
                version = _BaseStore.get_version(data_type)
                context_cache.set(self.project_id, data_type, version, raw[data_type])

        return raw

    def _load_phase_data(
        self, raw_data: dict, phase: str, allocation, current_chapter_number: int | None,
    ) -> dict:
        """根据阶段和预算裁剪项目数据"""
        budget = BudgetTracker(allocation.project_data_budget)
        context: dict = {}

        if phase == Phase.INCUBATION.value:
            self._load_incubation_data(raw_data, budget, context)
        elif phase == Phase.STRUCTURE.value:
            self._load_structure_data(raw_data, budget, context)
        elif phase == Phase.WRITING.value:
            self._load_writing_data(raw_data, budget, context, current_chapter_number)
        elif phase == Phase.REVISION.value:
            self._load_revision_data(raw_data, budget, context)

        return context

    def _load_incubation_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        outline = raw.get("outline")
        if outline:
            data = {"title": outline.get("title", ""), "summary": (outline.get("summary") or "")[:100]}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["outline_index"] = data
                budget.add(tokens)

        ws = raw.get("world_setting")
        if ws:
            data_json = json.dumps(ws, ensure_ascii=False)
            if budget.can_add(estimate_tokens(data_json)):
                ctx["world_setting"] = ws
                budget.add(estimate_tokens(data_json))

    def _load_structure_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        # 大纲全文
        outline = raw.get("outline")
        if outline:
            tokens = estimate_tokens(json.dumps(outline, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["outline"] = outline
                budget.add(tokens)

        # 角色索引
        chars = raw.get("characters", [])
        char_list = []
        for c in chars:
            info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or ""}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                char_list.append(info)
                budget.add(tokens)
        ctx["characters"] = char_list

        # 情节块
        blocks = raw.get("plot_blocks", [])
        block_list = []
        for b in blocks:
            info = {"id": b["id"], "title": b["title"], "chapter_start": b["chapter_start"], "chapter_end": b.get("chapter_end"), "expected_mood": b.get("expected_mood")}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                block_list.append(info)
                budget.add(tokens)
        ctx["plot_blocks"] = block_list

        # 伏笔概览
        fs_list = raw.get("foreshadowings", [])
        fs_mini = []
        for f in fs_list:
            info = {"id": f["id"], "content": (f.get("content") or "")[:60], "planted_chapter": f.get("planted_chapter"), "expected_resolve_chapter": f.get("expected_resolve_chapter"), "status": f.get("status")}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                fs_mini.append(info)
                budget.add(tokens)
        ctx["foreshadowings"] = fs_mini

    def _load_writing_data(self, raw: dict, budget: BudgetTracker, ctx: dict, chapter_number: int | None):
        # 大纲全文
        outline = raw.get("outline")
        if outline:
            tokens = estimate_tokens(json.dumps(outline, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["outline"] = outline
                budget.add(tokens)

        # 角色索引（含 personality[:100]）
        chars = raw.get("characters", [])
        char_list = []
        for c in chars:
            info = {"id": c["id"], "name": c["name"], "role": c.get("role", ""), "core_motivation": c.get("core_motivation") or "", "personality": (c.get("personality") or "")[:100], "knowledge_boundary": (c.get("knowledge_boundary") or "")[:200], "speech_style": (c.get("speech_style") or "")[:80]}
            tokens = estimate_tokens(json.dumps(info, ensure_ascii=False))
            if budget.can_add(tokens):
                char_list.append(info)
                budget.add(tokens)
        ctx["characters"] = char_list

        # 世界观精简版
        ws = raw.get("world_setting")
        if ws:
            data = {"core_concept": ws.get("core_concept") or "", "red_settings": (ws.get("tiered_settings") or {}).get("red", []), "key_locations": ws.get("key_locations") or []}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["world_setting"] = data
                budget.add(tokens)

        # 伏笔：pending_reclaim 和 overdue 需要从批量数据中计算
        all_fs = raw.get("foreshadowings", [])
        pending_fs = [f for f in all_fs if f.get("status") == "pending_reclaim"]
        ctx["pending_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in pending_fs]
        if chapter_number:
            overdue_fs = [f for f in all_fs
                          if f.get("status") in ("active", "pending_reclaim")
                          and (f.get("expected_resolve_chapter") or 999999) < chapter_number]
            ctx["overdue_foreshadowings"] = [{"id": f["id"], "content": (f.get("content") or "")[:60], "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in overdue_fs]

        # 风格约束
        style = raw.get("style_constraints")
        if style:
            data = {"taboo_words": style.get("taboo_words") or [], "forbidden_patterns": style.get("forbidden_patterns") or [], "abstract_rules": style.get("abstract_rules") or []}
            tokens = estimate_tokens(json.dumps(data, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_constraints"] = data
                budget.add(tokens)

        # 风格偏差摘要（最近 5 章趋势 + 异常标记）
        snapshots = raw.get("style_snapshots", []) or []
        if len(snapshots) >= 3:
            recent = snapshots[:5]
            # 对话比连续上升/下降趋势
            dialogue_trend = "stable"
            if len(recent) >= 3:
                d_vals = [s.get("dialogue_ratio", 0) or 0 for s in recent]
                if all(d_vals[i] > d_vals[i + 1] for i in range(len(d_vals) - 1)):
                    dialogue_trend = "declining"
                elif all(d_vals[i] < d_vals[i + 1] for i in range(len(d_vals) - 1)):
                    dialogue_trend = "rising"

            # 异常章节检测：偏离均值 > 1.5 σ
            anomalies = []
            for metric in ("dialogue_ratio", "avg_sentence_length", "avg_paragraph_length"):
                vals = [s.get(metric, 0) or 0 for s in snapshots]
                if len(vals) < 3:
                    continue
                mean = sum(vals) / len(vals)
                std = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
                if std == 0:
                    continue
                for s in recent:
                    v = s.get(metric, 0) or 0
                    if abs(v - mean) > 1.5 * std:
                        anomalies.append({
                            "chapter": s.get("chapter_number"),
                            "metric": metric,
                            "value": round(v, 2),
                            "baseline": round(mean, 2),
                            "direction": "偏高" if v > mean else "偏低",
                        })

            style_deviation = {
                "snapshots_available": len(snapshots),
                "dialogue_trend": dialogue_trend,
                "anomalies": anomalies[:5],
            }
            tokens = estimate_tokens(json.dumps(style_deviation, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_deviation"] = style_deviation
                budget.add(tokens)

        # 当前章节大纲
        if chapter_number:
            outlines = raw.get("chapter_outlines", [])
            co = next((o for o in outlines if o.get("chapter_number") == chapter_number), None)
            if co:
                ctx["current_chapter_outline"] = co
                budget.add(estimate_tokens(json.dumps(co, ensure_ascii=False)))

        # 上一章结尾
        closing = raw.get("previous_closing")
        if closing:
            closing_json = json.dumps({"closing_scene": closing.strip()}, ensure_ascii=False)
            tokens = estimate_tokens(closing_json)
            if budget.can_add(tokens):
                ctx["previous_chapter_closing"] = closing.strip()
                budget.add(tokens)

        # 当前情节块
        if chapter_number:
            blocks = raw.get("plot_blocks", [])
            for b in blocks:
                start = b.get("chapter_start", 0)
                end = b.get("chapter_end") or 999999
                if start <= chapter_number <= end:
                    ctx["current_plot_block"] = {
                        "title": b.get("title"),
                        "expected_mood": b.get("expected_mood"),
                        "must_happen": b.get("must_happen") or [],
                        "questions_to_answer": (b.get("questions_to_answer") or [])[:3],
                        "questions_to_raise": (b.get("questions_to_raise") or [])[:3],
                    }
                    break

        # 当前章节相关支线事件（首次提出 / 交汇 / 预期解决 / 逾期）
        if chapter_number:
            subplots = raw.get("subplots", []) or []
            subplot_events = []
            for sp in subplots:
                intersect_ch = sp.get("planned_intersection_chapter")
                raised_ch = sp.get("raised_in_chapter")
                resolve_ch = sp.get("expected_resolution_chapter")
                status = sp.get("current_status")
                if raised_ch == chapter_number:
                    subplot_events.append({
                        "id": sp.get("id"), "name": sp.get("name"),
                        "event": "首次提出", "current_status": status,
                    })
                if intersect_ch == chapter_number:
                    subplot_events.append({
                        "id": sp.get("id"), "name": sp.get("name"),
                        "event": "交汇", "current_status": status,
                    })
                if resolve_ch == chapter_number:
                    subplot_events.append({
                        "id": sp.get("id"), "name": sp.get("name"),
                        "event": "预期解决", "current_status": status,
                    })
                # 逾期检测：已过预期交汇章但仍处早期状态
                if (
                    intersect_ch is not None
                    and chapter_number > intersect_ch
                    and status in ("hint", "developing")
                ):
                    subplot_events.append({
                        "id": sp.get("id"), "name": sp.get("name"),
                        "event": f"逾期（预期第{intersect_ch}章交汇，当前状态仍为{status}）",
                    })
            if subplot_events:
                tokens = estimate_tokens(json.dumps(subplot_events, ensure_ascii=False))
                if budget.can_add(tokens):
                    ctx["active_subplot_events"] = subplot_events
                    budget.add(tokens)

        # 最近的变更决策
        changes = raw.get("changes", [])
        applied = [c for c in changes if c.get("status") == "applied"]
        if applied:
            decision_list = []
            for d in applied[:5]:
                decision_list.append({
                    "target_type": d.get("target_type"),
                    "decision": d.get("author_decision", "unknown"),
                    "summary": (d.get("description") or "")[:80],
                })
            decision_json = json.dumps(decision_list, ensure_ascii=False)
            decision_tokens = estimate_tokens(decision_json)
            if budget.can_add(decision_tokens):
                ctx["recent_decisions"] = decision_list
                budget.add(decision_tokens)

        # 当前章的情节问题
        if chapter_number:
            questions = raw.get("plot_questions", [])
            chapter_qs = [q for q in questions if q.get("chapter_number") == chapter_number]
            ctx["questions_for_chapter"] = [
                {"id": q["id"], "question": (q.get("question_text") or "")[:60]}
                for q in chapter_qs
            ]

        # 时间线最近 5 条
        timeline = raw.get("timeline", [])
        if timeline:
            recent = timeline[:5]
            ctx["recent_timeline"] = [
                {"chapter": t.get("chapter_number"), "summary": (t.get("summary") or "")[:80], "emotion_tag": t.get("emotion_tag")}
                for t in recent
            ]

        # 关系演变规划
        if chapter_number:
            relations = raw.get("relations", [])
            # 注意：batch_read_for_context 未包含 evolution_plans 数据
            # 此处产生 1 次额外 DB 查询（对比旧版 ~20 次，已大幅减少）
            # 未来优化：在 CharacterStore 新增 _read_evolution_plans_with_session(db)，
            # 并在 batch_read_for_context 中调用，可完全消除额外查询
            pending_plans = self.kb.characters.list_evolution_plans_triggering_at(chapter_number)
            if pending_plans:
                evolution_cues = []
                rel_map = {r["id"]: r for r in relations}
                char_list = raw.get("characters", [])
                char_map = {c["id"]: c["name"] for c in char_list}
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
                    ctx["relation_evolution_cues"] = evolution_cues
                    budget.add(cues_tokens)

        # 前置条件校验（从批量数据中校验，避免额外 DB 查询）
        prereq = self._validate_prerequisites_from_raw(
            raw, chapter_number, phase=Phase.WRITING.value,
        )
        ctx["prerequisites"] = prereq

    def _validate_prerequisites_from_raw(
        self,
        raw: dict,
        chapter_number: int | None,
        *,
        phase: str,
    ) -> dict:
        """从批量读取结果校验前置条件，避免额外 DB 查询

        chapter_number_missing 仅在 writing 阶段触发：通过 phase 关键字参数
        显式声明调用上下文，避免未来在 structure/revision 接入校验时误报。
        """
        blocked = []
        warnings = []

        # 0. 章节号缺失或非法（仅 writing 阶段强制要求）
        # 使用 `is None or < 1` 覆盖两种异常：未传 None，或传了 0/负数等
        # 非法章节号——这两种情况下游 chapter_outline_missing 都会因为
        # `if chapter_number:` 短路跳过，所以必须在本层显式阻断。
        if phase == Phase.WRITING.value and (chapter_number is None or chapter_number < 1):
            blocked.append({
                "type": "chapter_number_missing",
                "message": "未指定当前写作章节号。请在左侧章节列表中选中要写的章节，或在对话中明确告知章节号。",
                "severity": "error",
            })

        # 1. 章节大纲
        if chapter_number:
            outlines = raw.get("chapter_outlines", [])
            co = next((o for o in outlines if o.get("chapter_number") == chapter_number), None)
            if not co:
                blocked.append({"type": "chapter_outline_missing", "chapter": chapter_number,
                                "message": f"第{chapter_number}章大纲不存在", "severity": "error"})
            elif not co.get("confirmed"):
                blocked.append({"type": "outline_unconfirmed", "chapter": chapter_number,
                                "message": f"第{chapter_number}章大纲尚未确认", "severity": "error"})

        # 2. 角色
        chars = raw.get("characters", [])
        if not chars:
            blocked.append({"type": "character_missing", "message": "项目中没有任何角色", "severity": "error"})

        # 3. 世界观
        ws = raw.get("world_setting")
        if not ws or not ws.get("core_concept"):
            blocked.append({"type": "world_setting_missing", "message": "项目世界观尚未完善", "severity": "error"})

        # 4. 伏笔
        fs_list = raw.get("foreshadowings", [])
        if not fs_list:
            warnings.append({"type": "foreshadowing_empty", "message": "当前无伏笔记录", "severity": "warning"})

        # 5. 风格约束
        style = raw.get("style_constraints")
        if not style:
            warnings.append({"type": "style_constraints_missing", "message": "尚未设置风格约束", "severity": "warning"})

        # 6. 情节块
        blocks = raw.get("plot_blocks", [])
        if not blocks:
            warnings.append({"type": "plot_block_empty", "message": "尚未创建情节块", "severity": "warning"})

        # 7. 上一章结尾
        if chapter_number and chapter_number > 1:
            closing = raw.get("previous_closing")
            if not closing:
                warnings.append({"type": "previous_chapter_empty", "chapter": chapter_number - 1,
                                 "message": f"第{chapter_number - 1}章尚无正文", "severity": "warning"})

        # 8. 关系演变（简化检查，不额外查 DB）
        relations = raw.get("relations", [])
        has_plans = any(r.get("plans") for r in relations if isinstance(r.get("plans"), list) and r["plans"])
        if not has_plans:
            warnings.append({"type": "relation_evolution_empty", "message": "尚未创建关系演变规划", "severity": "warning"})

        # 9. 时间线
        timeline = raw.get("timeline", [])
        if not timeline:
            warnings.append({"type": "timeline_empty", "message": "尚未创建时间线记录", "severity": "warning"})

        return {"blocked": blocked, "warnings": warnings, "validated": True}

    def _load_revision_data(self, raw: dict, budget: BudgetTracker, ctx: dict):
        # 大纲全文
        outline = raw.get("outline")
        if outline:
            tokens = estimate_tokens(json.dumps(outline, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["outline"] = outline
                budget.add(tokens)

        # 世界观精简版
        ws = raw.get("world_setting")
        if ws:
            ws_mini = {"core_concept": ws.get("core_concept", ""), "red_settings": (ws.get("tiered_settings") or {}).get("red", []), "key_locations": ws.get("key_locations", [])}
            tokens = estimate_tokens(json.dumps(ws_mini, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["world_setting"] = ws_mini
                budget.add(tokens)

        # 角色索引
        chars = raw.get("characters", [])
        chars_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
        tokens = estimate_tokens(json.dumps(chars_index, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["characters"] = chars_index
            budget.add(tokens)

        # 伏笔
        fs_list = raw.get("foreshadowings", [])
        fs_mini = [{"id": f["id"], "content": (f.get("content") or "")[:60], "status": f.get("status"), "planted_chapter": f.get("planted_chapter"), "expected_resolve_chapter": f.get("expected_resolve_chapter")} for f in fs_list]
        tokens = estimate_tokens(json.dumps(fs_mini, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["foreshadowings"] = fs_mini
            budget.add(tokens)

        # 时间线
        timeline = raw.get("timeline", [])
        recent = timeline[:20]
        tl_mini = [{"chapter_number": t.get("chapter_number"), "summary": (t.get("summary") or "")[:80], "emotion_tag": t.get("emotion_tag")} for t in recent]
        tokens = estimate_tokens(json.dumps(tl_mini, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["timeline"] = tl_mini
            budget.add(tokens)

        # 风格约束
        style = raw.get("style_constraints")
        if style:
            tokens = estimate_tokens(json.dumps(style, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_constraints"] = style
                budget.add(tokens)

        # 待决情节问题（仅 pending 状态）
        questions = [q for q in raw.get("plot_questions", []) if q.get("status") == "pending"]
        if questions:
            tokens = estimate_tokens(json.dumps(questions, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["plot_questions"] = questions
                budget.add(tokens)

        # 支线状态（排除已废弃）
        active_subplots = [s for s in raw.get("subplots", []) if s.get("current_status") != "abandoned"]
        if active_subplots:
            tokens = estimate_tokens(json.dumps(active_subplots, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["subplots"] = active_subplots
                budget.add(tokens)

        # 风格快照（最近 10 条）
        snapshots = raw.get("style_snapshots", [])
        if snapshots:
            tokens = estimate_tokens(json.dumps(snapshots, ensure_ascii=False))
            if budget.can_add(tokens):
                ctx["style_snapshots"] = snapshots
                budget.add(tokens)

    def _load_previous_context(
        self, raw: dict, phase: str, allocation, chapter_number: int | None, strategy_name: str | None,
    ) -> str:
        """调用 context_strategy 组装前文"""
        if allocation.previous_text_budget <= 0 or not chapter_number or chapter_number <= 1:
            return ""

        chapters = raw.get("chapters", [])
        # 过滤出当前章节之前且有内容的章节
        written = [ch for ch in chapters if ch.get("chapter_number", 0) < chapter_number and ch.get("content")]

        if not written:
            return ""

        chapter_outlines = raw.get("chapter_outlines", [])

        strategy = select_strategy(
            written_chapters=written,
            current_chapter=chapter_number,
            token_budget=allocation.previous_text_budget,
            strategy_name=strategy_name,
            chapter_outlines=chapter_outlines,
        )

        return strategy.build_previous_context(
            written_chapters=written,
            current_chapter=chapter_number,
            chapter_outlines=chapter_outlines,
            token_budget=allocation.previous_text_budget,
        )

    def _build_lightweight(
        self, context_window: int, phase: str, current_chapter_number: int | None,
    ) -> dict:
        """轻量模式 — 只加载核心索引"""
        kb = self.kb
        max_tokens = max(int(context_window * _LIGHTWEIGHT_RATIO), 2000)
        budget = BudgetTracker(max_tokens)
        context: dict = {}

        outline = kb.outlines.get()
        if outline:
            outline_index = {"title": outline.get("title") or "未命名", "chapter_count": outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0, "summary": (outline.get("summary") or "")[:100]}
            context["outline_index"] = outline_index
            budget.add(estimate_tokens(json.dumps(outline_index, ensure_ascii=False)))

        chars = kb.characters.list_characters()
        char_index = [{"id": c["id"], "name": c["name"], "role": c.get("role", "")} for c in chars]
        context["character_index"] = char_index
        budget.add(estimate_tokens(json.dumps(char_index, ensure_ascii=False)))

        context["phase"] = phase
        if current_chapter_number:
            context["current_chapter_number"] = current_chapter_number

        ws = kb.world_setting.get()
        if ws:
            red = (ws.get("tiered_settings") or {}).get("red", [])
            if red:
                context["critical_rules"] = red[:3]
                budget.add(estimate_tokens(json.dumps(red[:3], ensure_ascii=False)))

        if phase in (Phase.WRITING.value, Phase.REVISION.value) and current_chapter_number:
            try:
                co = kb.outlines.get_chapter_outline(current_chapter_number)
                if co:
                    co_data = {"chapter_number": co.get("chapter_number"), "title": co.get("title") or "", "scene": co.get("scene") or "", "characters": co.get("characters") or "", "emotional_arc": co.get("emotional_arc") or "", "key_scenes": co.get("key_scenes") or [], "target_words": co.get("target_words")}
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

        return {
            "project_data": context,
            "previous_text": "",
            "loaded_keys": list(context.keys()),
            "_budget_used": budget.used,
            "_budget_max": budget.max,
            "_mode": "lightweight",
        }


# ========== 向后兼容 ==========

def build_agent_context(
    project_id: int,
    phase: str = "incubation",
    current_chapter_number: int | None = None,
    max_tokens: int = 12000,
    context_window: int | None = None,
) -> dict:
    """向后兼容入口 — agent.py 过渡期使用

    Args:
        context_window: 模型上下文窗口大小。优先使用此参数。
            如未提供，使用 get_context_window() 获取。
        max_tokens: 已废弃，仅当 context_window 未提供时用作 fallback。
    """
    from app.agents.token_budget import get_context_window as _get_context_window
    window = context_window or _get_context_window()

    assembler = ProjectContextAssembler(project_id)
    result = assembler.build(
        context_window=window,
        phase=phase,
        current_chapter_number=current_chapter_number,
    )
    # 返回旧格式（project_data 展平）
    flat = dict(result.get("project_data", {}))
    flat["_budget_used"] = result.get("_budget_used", 0)
    flat["_budget_max"] = result.get("_budget_max", 0)
    if result.get("_mode"):
        flat["_mode"] = result["_mode"]
    return flat
