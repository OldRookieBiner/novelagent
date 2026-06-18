# 结构与追踪标签页：修正实施计划（v2）

> **版本**：v2.0 | **日期**：2025-06-18 | **基准**：v1 方案（structure-tracking-optimization-plan.md）经事实核验后的修正实施版

---

## 与 v1 的关键差异

| 差异项 | v1 方案 | v2 修正 | 原因 |
|--------|---------|---------|------|
| P0.3 hook 挂载点 | `generate_chapter_content` 后 | `record_chapter_meta` 后 | timeline 由 `record_chapter_meta` 写入，挂前者取不到 tension_score |
| P1.1 方案选择 | 保留 A/B 两个方案 | **直接选 B，砍掉 A** | A 跑在正文写入后，提醒已无意义 |
| prompt 模板 | 建议在 prompts.py 加 `{style_deviation_warning}` 占位符 | **不需改动 prompts.py** | `AGENT_SYSTEM_PROMPT` 用 `{context_block}` 注入整个 ctx 字典，新增 key 自动可见 |
| P1.3 范围 | 新增 3 个指标（含 `description_ratio`） | **只加 2 个稳定指标**，放弃 `description_ratio` | `description_ratio`（含感官词/环境词）口径模糊，词表不确定 |
| P1.4 | 列为 P1 可选 | **整体砍掉** | 增加 LLM 调用、价值/成本比低 |
| P1.3 计算位置 | 挂在 `record_chapter_meta` | **挂在 `_compute_style_snapshot`**（在 `generate_chapter_content` 中） | 风格快照时序上属于正文生成阶段 |
| P1.1B 查询语义 | 复用 `list_overdue` | **新增 `list_due_or_overdue`（`<=`）** | 现有 `list_overdue` 用严格小于，漏掉"刚好到回收章节"的场景 |

---

## 改动总览

| 文件 | 改动内容 | 类型 |
|------|---------|------|
| `backend/app/agents/agent_context.py` | P0.1 注入 `style_deviation`、P0.2 补全 `current_plot_block` questions、P1.2 注入 `active_subplot_events` | 增量 |
| `backend/app/agents/tools/hooks.py` | P0.3 新增 `_hook_rhythm_quick_check` + `TOOL_HOOKS` 注册 | 增量 |
| `backend/app/agents/tools/creation/record_chapter_meta.py` | P1.1B 末尾追加重写伏笔 warning | 增量 |
| `backend/app/agents/services/stores/foreshadowing_store.py` | P1.1B 新增 `list_due_or_overdue` 方法 | 增量 |
| `backend/app/agents/tools/creation/generate_chapter_content.py` | P1.3 `_compute_style_snapshot` 加 2 个指标 | 增量 |
| `backend/app/models/style_snapshot.py` | P1.3 加 `ai_marker_density`、`sentence_variety` 字段 | 扩展 |
| `alembic/versions/` | P1.3 新建迁移文件（ALTER TABLE ADD COLUMN） | 迁移 |
| `frontend/src/types/knowledge.ts` | P1.3 `StyleSnapshot` 接口 + 2 个可选字段 | 扩展 |
| `frontend/src/components/workbench/structure/StructureTab.tsx` | P2.1 删除 `questions` section + 统计条、P2.2 交叉引用 | 修改 |
| `frontend/src/components/workbench/tracking/TrackingTab.tsx` | P1.3 新增指标列、P2.3 可选 SVG 抽组件 | 扩展 |
| `frontend/src/components/workbench/tracking/charts/` | P2.3 可选：2 个 SVG 图表组件 | 新建 |
| `backend/tests/test_agent_context.py` | 新增 `_load_writing_data` 相关测试 | 新增 |
| `backend/tests/test_hooks.py` | 新建 hooks 测试文件 | 新增 |
| `backend/tests/test_record_chapter_meta.py` | 新建 | 新增 |
| `AGENTS.md` | P2.3 更新已知问题条目为豁免说明 | 修改 |

---

## P0 — 闭环断裂修复（建议 PR1，约 4h）

### P0.1 写作阶段注入风格偏差摘要

**文件**：`backend/app/agents/agent_context.py` `_load_writing_data` 方法

在 `style_constraints` 注入之后、`current_chapter_outline` 注入之前插入：

```python
# 风格偏差摘要（最近 5 章的趋势 + 异常标记）
snapshots = raw.get("style_snapshots", [])
if len(snapshots) >= 3:
    recent = snapshots[:5]
    # 计算趋势 — 对话比连续上升/下降
    dialogue_trend = "stable"
    if len(recent) >= 3:
        d_vals = [s.get("dialogue_ratio", 0) or 0 for s in recent]
        if all(d_vals[i] > d_vals[i+1] for i in range(len(d_vals)-1)):
            dialogue_trend = "declining"
        elif all(d_vals[i] < d_vals[i+1] for i in range(len(d_vals)-1)):
            dialogue_trend = "rising"

    # 检测异常章节（偏离均值 > 1.5σ）
    anomalies = []
    for metric in ("dialogue_ratio", "avg_sentence_length", "avg_paragraph_length"):
        vals = [s.get(metric, 0) or 0 for s in snapshots]
        if len(vals) < 3:
            continue
        mean = sum(vals) / len(vals)
        std = (sum((v - mean)**2 for v in vals) / len(vals)) ** 0.5
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
```

**不修改 `prompts.py`**。`AGENT_SYSTEM_PROMPT` 的 `{context_block}` 占位符会把整个 ctx 字典 JSON 序列化注入，新增`"style_deviation"` key 自动出现在 Agent 可见的项目上下文中。

### P0.2 情节块 questions 接入写作上下文

**文件**：`backend/app/agents/agent_context.py:311`

**改动**：`current_plot_block` 的字典字面量补全两个 questions 字段，各截取前 3 项控制 token：

```python
ctx["current_plot_block"] = {
    "title": b.get("title"),
    "expected_mood": b.get("expected_mood"),
    "must_happen": b.get("must_happen") or [],
    "questions_to_answer": (b.get("questions_to_answer") or [])[:3],
    "questions_to_raise": (b.get("questions_to_raise") or [])[:3],
}
```

### P0.3 节奏 quick-check hook（挂载点修正）

**文件**：`backend/app/agents/tools/hooks.py`

新增函数：

```python
async def _hook_rhythm_quick_check(project_id: int, tool_result: dict) -> dict:
    """章节追踪记录完成后快速节奏对比"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    from app.agents.tools.utils import _mood_to_tension

    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False, "reason": "无法确定章节号"}

    kb = KnowledgeBaseService(project_id)
    block = kb.plots.get_current_plot_block(ch_num)
    if not block or not block.get("expected_mood"):
        return {"checked": False, "reason": "当前章节无情节块或预期情绪"}

    timeline = kb.timelines.get_by_chapter_number(ch_num)
    if not timeline:
        return {"checked": False, "reason": "当前章节无时间线数据"}

    expected_tension = _mood_to_tension(block["expected_mood"])
    actual_tension = timeline.get("tension_score") or 3
    deviation = abs(actual_tension - expected_tension)

    if deviation > 1:
        direction = "偏低" if actual_tension < expected_tension else "偏高"
        suggestion = (
            "建议在后续章节增加紧迫感事件或冲突密度"
            if actual_tension < expected_tension
            else "建议在后续章节适当放缓节奏，增加呼吸感场景"
        )
        return {
            "checked": True,
            "warning": (
                f"节奏偏差：情节块「{block['title']}」预期情绪「{block['expected_mood']}」"
                f"（张力 {expected_tension}），实际张力 {actual_tension}，{direction}"
            ),
            "suggestion": suggestion,
            "deviation": deviation,
        }

    return {"checked": True, "deviation": deviation, "status": "normal"}
```

注册表追加（保留现有的两个 hook 不变）：

```python
TOOL_HOOKS = {
    "generate_chapter_content": ["foreshadowing_check", "style_quick_check"],
    "record_chapter_meta": ["rhythm_quick_check"],
}
```

`run_post_hooks` 函数已在 `agent_graph.py` 中统一下发，不需要额外改动。

---

## P1 — 自动化增强（建议 PR2，约 5h）

### P1.1B 待回收伏笔提示

**文件**：

- `backend/app/agents/services/stores/foreshadowing_store.py` — 新增方法
- `backend/app/agents/tools/creation/record_chapter_meta.py` — 追加 warnings

```python
# foreshadowing_store.py 新增
def list_due_or_overdue(self, current_chapter: int) -> list[dict]:
    """active/pending_reclaim 且 expected_resolve_chapter <= current"""
    with self.session(readonly=True) as db:
        objs = db.query(Foreshadowing).filter(
            Foreshadowing.project_id == self.project_id,
            Foreshadowing.status.in_(["active", "pending_reclaim"]),
            Foreshadowing.expected_resolve_chapter.isnot(None),
            Foreshadowing.expected_resolve_chapter <= current_chapter,
        ).all()
        return self._to_dict_list(objs)
```

在 `record_chapter_meta` 函数中，第 3 步"回收伏笔"之后、`result` 构造之前追加：

```python
# 4. 检测已到期但未标记回收的伏笔
unreclaimed_fs = kb.foreshadowings.list_due_or_overdue(chapter_number)
# 排除调用方本次已传入的回收 ID
remaining_unreclaimed = [f for f in unreclaimed_fs if f["id"] not in reclaimed_ids_set]
if remaining_unreclaimed:
    warnings.append({
        "step": "unreclaimed_foreshadowings",
        "message": f"有 {len(remaining_unreclaimed)} 个伏笔已到预期回收章节但未标记回收",
        "unreclaimed_preview": [f["content"][:60] for f in remaining_unreclaimed[:3]],
    })
```

注：`reclaimed_ids_set` 需在解析 `reclaimed_foreshadowing_ids` 后将其转为 `set()`。

### P1.2 当前章节相关支线提醒

**文件**：`backend/app/agents/agent_context.py` `_load_writing_data` 方法

在 `current_plot_block` 注入之后插入（受 `budget.can_add` 守护）：

```python
# 当前章节相关的支线事件
if chapter_number:
    subplots = raw.get("subplots", [])
    subplot_events = []
    for sp in subplots:
        intersect_ch = sp.get("planned_intersection_chapter")
        raised_ch = sp.get("raised_in_chapter")
        resolve_ch = sp.get("expected_resolution_chapter")
        if intersect_ch == chapter_number:
            subplot_events.append({
                "id": sp["id"], "name": sp["name"],
                "event": "交汇", "current_status": sp.get("current_status"),
            })
        if raised_ch == chapter_number:
            subplot_events.append({
                "id": sp["id"], "name": sp["name"],
                "event": "首次提出", "current_status": sp.get("current_status"),
            })
        if resolve_ch == chapter_number:
            subplot_events.append({
                "id": sp["id"], "name": sp["name"],
                "event": "预期解决", "current_status": sp.get("current_status"),
            })
        # 逾期检测
        if chapter_number > (intersect_ch or 999999) and sp.get("current_status") in ("hint", "developing"):
            subplot_events.append({
                "id": sp["id"], "name": sp["name"],
                "event": f"逾期（预期第{intersect_ch}章交汇，当前状态仍为{sp.get('current_status')}）",
            })
    if subplot_events:
        tokens = estimate_tokens(json.dumps(subplot_events, ensure_ascii=False))
        if budget.can_add(tokens):
            ctx["active_subplot_events"] = subplot_events
            budget.add(tokens)
```

### P1.3 风格指标深化（唯⼀含 schema 变更项）

**目标**：在 StyleSnapshot 中新增 2 个字段，AI 味浓度与句式变化度。

**实施步骤**：

1. **模型** `backend/app/models/style_snapshot.py`：
   ```python
   ai_marker_density = Column(Float, default=0.0)
   sentence_variety = Column(Float, default=0.0)
   ```

2. **Alembic**：`docker exec novelagent-backend-1 alembic revision -m "add style indicator fields"`，在生成的 migration 脚本中：
   ```python
   op.add_column("style_snapshots", sa.Column("ai_marker_density", sa.Float(), server_default="0.0"))
   op.add_column("style_snapshots", sa.Column("sentence_variety", sa.Float(), server_default="0.0"))
   ```

3. **`_compute_style_snapshot`**（`generate_chapter_content.py:12`）：在现有计算后追加：
   ```python
   from app.agents.constants import FORBIDDEN_WORDS
   
   # ai_marker_density
   total_chars = max(total_chars, 1)
   marker_count = sum(content.count(w) for w in FORBIDDEN_WORDS)
   ai_marker_density = marker_count / total_chars
   
   # sentence_variety — 句长标准差
   from statistics import stdev
   if len(sentences) >= 2:
       sentence_lengths = [len(s) for s in sentences]
       sentence_variety = stdev(sentence_lengths)
   else:
       sentence_variety = 0.0
   ```
   在返回的 dict 中追加两个字段。

4. **前端类型** `frontend/src/types/knowledge.ts`：
   ```typescript
   export interface StyleSnapshot {
     // ... 现有字段
     ai_marker_density?: number
     sentence_variety?: number
   }
   ```

5. **前端渲染** `TrackingTab.tsx` `StyleTrackView`：在 `COLUMNS` 数组（L442 附近）追加两列，渲染逻辑用 `?? 0` 兜底老数据：
   ```typescript
   { key: 'ai_marker_density', label: 'AI味密度' },
   { key: 'sentence_variety', label: '句长变异性' },
   ```
   偏差检测 `isDeviant` 需要处理新指标的 `undefined`（`v ?? 0`）。

---

## P2 — UI/UX 优化（建议 PR3，约 3h）

### P2.1 合并问题链到情节块视图

**文件**：`frontend/src/components/workbench/structure/StructureTab.tsx`

- 移除 `StructureSection` 类型中的 `'questions'`
- 从 `SECTIONS` 数组中移除 `{ key: 'questions', ... }`
- 删除 `QuestionsView` 函数和 `renderContent` 中的 `case 'questions'`
- 在 `PlotBlocksView` 顶部新增统计摘要条：

```tsx
// PlotBlocksView 顶部
const totalQuestions = data.reduce((sum, b) =>
  sum + (b.questions_to_answer?.length || 0) + (b.questions_to_raise?.length || 0), 0)
const answeredQuestions = data.reduce((sum, b) =>
  sum + (b.questions_to_answer?.length || 0), 0)
// 或更精确：取有 completion_summary 的情节块的已回答问题数

<div className="flex items-center gap-3 mb-4 text-[11px] text-muted-foreground">
  <span>总问题: {totalQuestions}</span>
  <span className="text-green-600">已回答: {answeredQuestions}</span>
  <span className="text-amber-600">待回答: {totalQuestions - answeredQuestions}</span>
</div>
```

### P2.2 支线 × 情节块交叉引用

**文件**：`frontend/src/components/workbench/structure/StructureTab.tsx`

- `SubplotsView` 新增 props：`plotBlocks: PlotBlock[]`
- 在 `renderContent` 调用处传入
- 每个支线卡片底部（现有 UI 中不是空的区域）追加如下内容：

```tsx
{(() => {
  const relatedBlocks = plotBlocks.filter(b => {
    const start = b.chapter_start
    const end = b.chapter_end || 999999
    return [subplot.raised_in_chapter, subplot.planned_intersection_chapter,
            subplot.expected_resolution_chapter].some(ch =>
      ch && ch >= start && ch <= end
    )
  })
  if (!relatedBlocks.length) return null
  return (
    <div className="text-[10px] text-muted-foreground">
      涉及情节块: {relatedBlocks.map(b => `「${b.title}」(第${b.chapter_start}-${b.chapter_end}章)`).join(' · ')}
    </div>
  )
})()}
```

### P2.3 SVG 内联图表组件化（可选）

建立 `frontend/src/components/workbench/tracking/charts/` 目录，拆分：
- `RhythmComparisonChart.tsx`（从 TrackingTab.tsx 迁移节奏对比曲线图）
- `DialogueRatioTrendChart.tsx`（从 TrackingTab.tsx 迁移对话比趋势折线图）

迁移完成后，在 `AGENTS.md` 中将已知问题条目更新为：`TrackingTab 中的内联 SVG 用于动态 viewBox 数据可视化图表，lucide-react 无法替代，已抽取为独立组件放入 tracking/charts/ 目录，豁免此规则约束。`

---

## 测试计划

### 后端单元测试

**`test_agent_context.py`** 新增：

| 测试函数 | 场景 | 断言 |
|---------|------|------|
| `test_writing_phase_includes_style_deviation_when_snapshots_sufficient` | mock 6 条 snapshot，1 条含异常偏差 | ctx 含 `style_deviation.anomalies` ≥ 1 条 |
| `test_writing_phase_skips_style_deviation_when_snapshots_few` | 2 条 snapshot | ctx 不含 `style_deviation` |
| `test_writing_phase_current_plot_block_includes_questions` | mock 1 个 plot_block 含 4 个 questions | `current_plot_block.questions_to_answer` 长度 3 |
| `test_writing_phase_active_subplot_events_for_intersection_chapter` | mock 1 个 subplot 设 `planned_intersection_chapter = current` | `active_subplot_events` 含 `event=交汇` |
| `test_writing_phase_budget_overflow_skips_optional_fields` | 预算极限压缩 | 不抛异常，`style_deviation` 和 `active_subplot_events` 被优雅跳过 |

**`test_hooks.py`**（新建）：

| 测试函数 | 场景 | 断言 |
|---------|------|------|
| `test_rhythm_quick_check_returns_warning_on_deviation` | mock `_mood_to_tension` 返回 5，timeline tension=2 | 偏差 3 > 1，返回 warning + suggestion |
| `test_rhythm_quick_check_normal_when_aligned` | expected=3, actual=3 | 偏差 0，status=normal |
| `test_rhythm_quick_check_skipped_without_timeline` | timeline None | `"checked": False, "reason": ...` |
| `test_tool_hooks_registers_record_chapter_meta` | 检查 `TOOL_HOOKS` | `"rhythm_quick_check" in TOOL_HOOKS["record_chapter_meta"]` |

**`test_record_chapter_meta.py`**（新建）：

| 测试函数 | 场景 | 断言 |
|---------|------|------|
| `test_warning_appended_when_due_foreshadowings_unreclaimed` | expected_resolve_chapter == current, active 伏笔，未传 reclaimed_ids | warnings 含 `step="unreclaimed_foreshadowings"` |
| `test_no_warning_when_due_foreshadowing_is_reclaimed` | 同上但传入对应 reclaimed_ids | warnings 不含 unreclaimed |
| `test_warning_excludes_already_overdue_outside_current` | expected_resolve_chapter < current（严格过期）和等于 current（刚到期）两种 | 两种都被 `list_due_or_overdue` 覆盖 |

**`test_generate_chapter_content.py`**（如存在）或新增测试：

| 测试函数 | 场景 | 断言 |
|---------|------|------|
| `test_compute_style_snapshot_includes_ai_marker_density` | 含 5 个 FORBIDDEN_WORDS 的 1000 字文本 | density 约 0.005 |
| `test_compute_style_snapshot_sentence_variety_zero_for_uniform` | 等长句子 | sentence_variety == 0.0 |
| `test_compute_style_snapshot_empty_content_returns_zero_metrics` | 空白 | 两个新指标 = 0.0 |

### 前端测试

- `StructureTab` 测试更新：移除 `questions` 断言 + 新增统计条存在的断言
- `SubplotsView` 测试：渲染交叉引用文本
- `StyleTrackView` 测试：两个新列存在；缺字段 mock 数据显示 `0` 而非 NaN

### 验证命令

```bash
docker compose restart backend                                          # Python 代码
docker exec novelagent-backend-1 pytest -v                               # 后端测试
docker exec novelagent-backend-1 alembic upgrade head                    # sys migration
docker compose build --no-cache frontend && docker compose up -d frontend # 前端构建
cd frontend && npm run test:run && npm run lint                          # 前端测试+lint
```

---

## Assumptions & Defaults

1. **prompt 模板不动**：`AGENT_SYSTEM_PROMPT` 的 `{context_block}` 会注入整个 ctx 字典。新增 ctx key 不需要改 prompts.py。
2. **注入顺序约定**：`style_constraints → style_deviation → current_chapter_outline → previous_chapter_closing → current_plot_block(扩展版) → active_subplot_events → recent_decisions`。保证偏差/警告类优先保留预算。
3. **P0.3 挂载点**：修正为 `record_chapter_meta`（非原方案的 `generate_chapter_content`）。
4. **P1.1B 新增方法**：`list_due_or_overdue` 用 `<=`，不修改现有 `list_overdue` 语义。
5. **P1.3 范围收敛**：只加 `ai_marker_density`（FORBIDDEN_WORDS 字符出现率）和 `sentence_variety`（句长标准差）。放弃 `description_ratio`。
6. **P1.4 砍掉**：不进行情节块完成自动总结。
7. **P2.3 可选**：如时间紧张可跳过，AGENTS.md 已记为已知豁免。
8. **测试 mock 策略**：所有新增 hook 测试通过 mock `KnowledgeBaseService` 返回值实现；agent_context 测试沿用现有 `MockKB` patch 模式。
9. **前端兼容老快照**：`StyleSnapshot` TS 接口新字段 `?: number`，UI 用 `?? 0` 兜底。
10. **零新依赖**：`ai_marker_density` 用 `str.count`，不引入新分词库或图表库。
