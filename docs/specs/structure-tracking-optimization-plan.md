# 结构与追踪标签页：优化方案

> **版本**：v1.0 | **日期**：2025-06-18 | **评估范围**：`StructureTab`（3 个子面板） + `TrackingTab`（4 个子面板）

---

## 总体诊断

核心发现：**数据已经存在、上下文已经部分注入，但有三个断裂点导致价值没有完全释放**：

1. **写作阶段 Agent 看不到风格偏差**——`style_snapshots` 只在 REVISION 阶段注入，WRITING 阶段缺失
2. **情节块的 questions 未注入**——`current_plot_block` 只含 `must_happen`，不含 `questions_to_answer/raise`
3. **感知工具结果不回流**——`rhythm_analysis`/`style_analysis` 的结果存在于工具返回值中，但不会自动进入下一轮 Agent 上下文

---

## 现有功能评估摘要

### 结构标签页（StructureTab）

| 子面板 | 价值评级 | 说明 |
|--------|---------|------|
| 情节块 | ★★★☆ 高 | 有力的结构思维工具，悬念即问题管理。`expected_mood` 连接到节奏对比视图构成规划→执行→偏差检测闭环。但 Agent 写作时不读取 must_happen/questions |
| 问题链 | ★☆☆ 低 | 纯粹派生视图，无独立信息增量，建议合并到情节块视图 |
| 支线网络 | ★★☆ 中 | 四状态生命周期设计合理，但状态流转完全手动，与情节块无交叉引用 |

### 追踪标签页（TrackingTab）

| 子面板 | 价值评级 | 说明 |
|--------|---------|------|
| 伏笔追踪 | ★★★★★ 最高 | 三级重要性 + 三态生命周期 + 逾期检测 + 健康度评分 + 后钩子自动检查。系统中最有价值的追踪功能 |
| 时间线 | ★★★ 高 | 三维评分 + 因果链，但评分由 LLM 主观给出，跨章可比性存疑 |
| 风格偏差 | ★★☆ 中 | 均值±1σ 偏差检测方法合理，但指标太表面（段长/句长/段落数），缺 AI 味检测、词汇多样性等深层指标 |
| 节奏对比 | ★★★★ 高 | 预期 vs 实际张力曲线叠加 + 偏差高亮。但数据链脆弱（依赖情节块 expected_mood + 时间线 tension_score 双条件） |

---

## 根本性问题：数据→行动闭环断裂

```
规划数据（情节块/伏笔/支线）──→ 写作过程（Agent）
                ↑                      │
                │                      ↓
          ┌─────┴──────────┐   追踪数据（时间线/风格快照）
          │  用户手动查看   │         │
          │  （结构和追踪页） │         ↓
          └────────────────┘   偏差分析（节奏对比/风格偏差/伏笔逾期）
                                       │
                                       ↓
                                  Agent 上下文？
```

**关键的"最后一公里"缺失**：伏笔逾期、节奏偏差、风格偏离等信息不会自动注入到 Agent 的下一次写作上下文中，除非用户手动在 Agent 对话中提及。

后钩子（`hooks.py`）是一个好的开始——它在章节生成后自动检查伏笔逾期和风格偏离——但检查结果只是附加到工具返回值中，Agent 下一轮对话不一定处理这些警告。

### 具体证据

1. `agent_context.py` `_load_writing_data` 不注入 `style_snapshots`（只在 `_load_revision_data` 中注入）
2. `current_plot_block` 的组装只含 `must_happen`，不含 `questions_to_answer/questions_to_raise`
3. `context_strategy.py` 只管理"前文章节内容"的上下文策略，不涉及追踪数据
4. `batch_read_for_context` 不返回感知工具分析结果（不持久化）

---

## P0：闭环断裂修复（4-6 小时）

这些改进直接让追踪数据回流到 Agent 写作决策中，是价值最高的改动。

### P0.1 将风格偏差注入 WRITING 阶段上下文

**现状**：`_load_writing_data` 注入 `style_constraints`（规则），但不注入 `style_snapshots`（实际测量）。Agent 知道"不能怎么写"但不知道"自己是否已经偏离"。`style_snapshots` 只在 `_load_revision_data` 中注入——太晚了。

**改动**：`agent_context.py` `_load_writing_data` 方法，在注入 `style_constraints` 之后追加风格偏差摘要。

```python
# 在 _load_writing_data 中，style_constraints 注入之后插入：

# 风格偏差摘要（最近 5 章的趋势 + 异常标记）
snapshots = raw.get("style_snapshots", [])
if len(snapshots) >= 3:
    recent = snapshots[:5]  # 最近 5 章
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
        vals = [s.get(metric, 0) or 0 for s in snapshots]  # 全量快照计算基线
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
        "anomalies": anomalies[:5],  # 最多 5 条，控制 token
    }
    tokens = estimate_tokens(json.dumps(style_deviation, ensure_ascii=False))
    if budget.can_add(tokens):
        ctx["style_deviation"] = style_deviation
        budget.add(tokens)
```

同时在 `prompts.py` `CHAPTER_WRITING_PROMPT` 中追加：

```
## 风格偏离警告
{style_deviation_warning}

如果上方有偏离警告，请在写作时有意识地纠正对应指标的偏离（例如对话比偏高则减少对话段落、增加叙述描写）。
```

**涉及文件**：
- `backend/app/agents/agent_context.py`（~25 行新增）
- `backend/app/agents/prompts.py`（5 行新增）
- `backend/app/agents/agent_graph.py`（组装 context 时传入 style_deviation_warning）

---

### P0.2 将当前情节块的 questions 注入 WRITING 上下文

**现状**：`_load_writing_data` 中 `current_plot_block` 的组装遗漏了 questions 字段：

```python
ctx["current_plot_block"] = {
    "title": b.get("title"),
    "expected_mood": b.get("expected_mood"),
    "must_happen": b.get("must_happen") or [],
}
# ❌ 缺少 questions_to_answer 和 questions_to_raise
```

**改动**：补全字段，加 token 预算控制（questions 可能很长）：

```python
ctx["current_plot_block"] = {
    "title": b.get("title"),
    "expected_mood": b.get("expected_mood"),
    "must_happen": b.get("must_happen") or [],
    "questions_to_answer": (b.get("questions_to_answer") or [])[:3],  # 最多 3 个
    "questions_to_raise": (b.get("questions_to_raise") or [])[:3],
}
```

同时在 `prompts.py` 的章节大纲生成 prompt（`CHAPTER_PLANNING_PROMPT` 附近）中追加指令，让 Agent 在生成章节点时显式引用当前情节块的问题：

```
## 情节块约束
当前章节属于情节块「{plot_block_title}」。
- 本章必须回答的问题: {questions_to_answer}
- 本章应提出的新问题: {questions_to_raise}
- 本章必须发生的事件: {must_happen}
```

**涉及文件**：
- `backend/app/agents/agent_context.py`（2 行改动）
- `backend/app/agents/prompts.py`（3-5 行新增）

---

### P0.3 感知工具结果回流——节奏 hook

**现状**：`rhythm_analysis` 和 `style_analysis` 的结果仅在当轮 Agent 对话中可见。Agent 调用了 `rhythm_analysis` 发现了单调段，下一轮对话时这个信息丢失了。

**方案（轻量，零 schema 变更）**：在 `hooks.py` 中，`generate_chapter_content` 的 post-hook 不仅检查伏笔和风格，也自动触发一次轻量节奏检查（比较当前章 tension 与所属情节块 expected_mood）。结果写入 `tool_result["auto_check_results"]`，Agent 在下一轮对话中自然能看到。

```python
async def _hook_rhythm_quick_check(project_id: int, tool_result: dict) -> dict:
    """章节完成后快速节奏对比（轻量版）"""
    from app.agents.services.knowledge_base import KnowledgeBaseService
    from app.agents.tools.utils import _mood_to_tension

    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False, "reason": "无法确定章节号"}

    kb = KnowledgeBaseService(project_id)

    # 获取当前章节所属情节块
    block = kb.plots.get_current_plot_block(ch_num)
    if not block or not block.get("expected_mood"):
        return {"checked": False, "reason": "当前章节无情节块或预期情绪"}

    # 获取当前章节时间线
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

然后将 `"rhythm_quick_check"` 加入 `TOOL_HOOKS["generate_chapter_content"]`。

**涉及文件**：
- `backend/app/agents/tools/hooks.py`（~35 行新增 + 1 行改动）

---

## P1：自动化增强（6-8 小时）

### P1.1 伏笔自动回收检测

**现状**：Agent 必须在 `record_chapter_meta` 的 `reclaimed_foreshadowing_ids` 中显式声明回收了哪些伏笔。容易遗漏。

**方案 A（即刻可行）**：在 `_hook_foreshadowing_check` 返回的结果中，追加当前章节恰好是预期回收章节的伏笔列表，让 Agent 注意到：

```python
# 在 _hook_foreshadowing_check 返回值中追加：
"pending_reclaim_this_chapter": [
    {"id": f["id"], "content": f["content"][:60]}
    for f in pending_reclaim
    if f.get("expected_resolve_chapter") == ch_num
],
```

Agent 看到"当前章节正好是伏笔预期回收章节"时会主动检查正文是否已回收该伏笔。

**方案 B（完整方案，延迟评估）**：在 `record_chapter_meta` 中，如果 `reclaimed_foreshadowing_ids` 为空但存在待回收伏笔的 `expected_resolve_chapter <= chapter_number`，在返回值中给出 warning 提示 Agent：

```python
# 在 record_chapter_meta 末尾追加：
unreclaimed = kb.foreshadowings.list_overdue(chapter_number)
if unreclaimed:
    result["warnings"] = result.get("warnings", []) + [{
        "step": "unreclaimed_foreshadowings",
        "message": f"有 {len(unreclaimed)} 个伏笔已到预期回收章节但未标记回收",
        "unreclaimed_preview": [f["content"][:60] for f in unreclaimed[:3]],
    }]
```

**涉及文件**：
- `backend/app/agents/tools/hooks.py`（方案 A：10 行改动）
- `backend/app/agents/tools/creation/record_chapter_meta.py`（方案 B：12 行新增）

---

### P1.2 支线交汇自动提醒

**现状**：支线的 `planned_intersection_chapter`/`raised_in_chapter`/`expected_resolution_chapter` 只是数字字段。没有机制在写作进度跨越这些章节时提醒用户或 Agent。

**方案**：在 `agent_context.py` `_load_writing_data` 中，添加当前章节相关的支线提醒：

```python
# 在 _load_writing_data 中追加（current_plot_block 注入之后）：
if chapter_number:
    subplots = raw.get("subplots", [])
    intersecting_subplots = []
    for sp in subplots:
        intersect_ch = sp.get("planned_intersection_chapter")
        raised_ch = sp.get("raised_in_chapter")
        resolve_ch = sp.get("expected_resolution_chapter")
        if intersect_ch == chapter_number:
            intersecting_subplots.append({
                "id": sp["id"], "name": sp["name"],
                "event": "交汇", "current_status": sp.get("current_status"),
            })
        if raised_ch == chapter_number:
            intersecting_subplots.append({
                "id": sp["id"], "name": sp["name"],
                "event": "首次提出", "current_status": sp.get("current_status"),
            })
        if resolve_ch == chapter_number:
            intersecting_subplots.append({
                "id": sp["id"], "name": sp["name"],
                "event": "预期解决", "current_status": sp.get("current_status"),
            })
        # 逾期检测：已过交汇/解决章节但状态未更新
        if chapter_number > (intersect_ch or 999999) and sp.get("current_status") in ("hint", "developing"):
            intersecting_subplots.append({
                "id": sp["id"], "name": sp["name"],
                "event": f"逾期（预期第{intersect_ch}章交汇，当前状态仍为{sp.get('current_status')}）",
            })
    if intersecting_subplots:
        ctx["active_subplot_events"] = intersecting_subplots
```

**涉及文件**：
- `backend/app/agents/agent_context.py`（25 行新增）

---

### P1.3 风格分析指标深化

**现状**：4 个指标（段落数、平均段长、对话占比、平均句长）太表面。

**方案**：在 `StyleSnapshot` 计算中新增指标：

| 新指标 | 计算方式 | 检测目标 |
|--------|---------|---------|
| `ai_marker_density` | FORBIDDEN_WORDS 出现次数 / 总字数 | AI 味浓度 |
| `description_ratio` | 描写段落占比（启发式：含感官词/环境词的段落数 / 总段落数） | 描写 vs 叙述平衡 |
| `sentence_variety` | 句长标准差（衡量句式单调度） | 节奏单一性 |

**实现策略**：

1. **新增 DB 字段** — 在 `StyleSnapshot` 模型中新增 `ai_marker_density`（Float）、`description_ratio`（Float）、`sentence_variety`（Float）
2. **计算位置** — 在 `record_chapter_meta` 调用时同步计算（复用已有的 jieba 分词 + FORBIDDEN_WORDS 常量）
3. **前端展示** — 在 `TrackingTab.tsx` 的 `StyleTrackView` 中新增指标列
4. **Agent 注入** — P0.1 已实现，新增指标自然加入偏差检测

**涉及文件**：
- `backend/app/models/style_snapshot.py`（新增 3 个字段）
- `backend/app/agents/tools/creation/record_chapter_meta.py`（新增计算逻辑 ~40 行）
- `backend/app/agents/tools/perception/style_analysis.py`（可选：新增 POV 一致性检测）
- `frontend/src/components/workbench/tracking/TrackingTab.tsx`（StyleTrackView 新增指标列 ~15 行）
- `alembic/versions/`（新建迁移文件）

---

### P1.4 情节块完成自动检测

**现状**：情节块的 `completion_summary` 需要手动填写。

**方案**：在 `generate_chapter_content` 的 post-hook 中，检测当前章节是否是某个情节块的结束章节（`chapter_number == block.chapter_end`），如果是，通过轻量 LLM 调用自动生成 `completion_summary`：

```python
async def _hook_plot_block_completion(project_id: int, tool_result: dict) -> dict:
    """情节块结束章节自动生成完成总结"""
    ch_num = tool_result.get("chapter_number")
    if not ch_num:
        return {"checked": False}

    kb = KnowledgeBaseService(project_id)
    ending_blocks = kb.plots.get_blocks_ending_at(ch_num)
    if not ending_blocks:
        return {"checked": True, "ending_blocks": 0}

    # 对每个结束的情节块，用 LLM 生成 completion_summary
    # ...（取决于是否愿意增加 LLM 调用成本）
    return {"checked": True, "ending_blocks": len(ending_blocks)}
```

> ⚠️ **注意**：此方案增加一次 LLM 调用。列为 P1 而非 P0 是因为：即使没有自动检测，用户可以在前端手动填写 `completion_summary`。

**涉及文件**：
- `backend/app/agents/tools/hooks.py`（~40 行新增）
- `backend/app/agents/services/stores/plot_store.py`（新增 `get_blocks_ending_at` 方法 ~10 行）

---

## P2：UI/UX 优化（3-4 小时）

### P2.1 合并问题链到情节块视图

**现状**：`QuestionsView` 纯粹是 `PlotBlocksView` 数据的派生视图，无独立信息增量。

**方案**：
1. 删除独立的"问题链"导航项
2. 在情节块视图顶部增加摘要栏
3. 每个情节块卡片中的 questions 已在现有视图中展示（编辑/只读模式均可见），无需重复

```tsx
// 在 PlotBlocksView 顶部增加摘要栏
<div className="flex items-center gap-3 mb-4 text-[11px] text-muted-foreground">
  <span>总问题: {totalQuestions}</span>
  <span className="text-green-600">已回答: {answeredQuestions}</span>
  <span className="text-amber-600">待回答: {pendingQuestions}</span>
</div>
```

**涉及文件**：
- `frontend/src/components/workbench/structure/StructureTab.tsx`
  - 删除 `SECTIONS` 中的 `questions` 条目
  - 删除 `QuestionsView` 组件
  - 删除 `renderContent` 中的 `'questions'` case
  - 在 `PlotBlocksView` 顶部增加摘要栏（~15 行新增）

---

### P2.2 支线 × 情节块交叉引用

**现状**：支线和情节块是两个孤立的视图。

**方案**：在支线详情卡片中，根据支线的章节规划自动反查哪些情节块覆盖了这些章节，并显示交叉引用：

```
涉及情节块: 「初次交锋」(第3-5章) · 「真相揭露」(第8-10章)
```

实现：`SubplotsView` 组件接收 `plotBlocks` 数据，在渲染每个支线时计算交叉引用。

```tsx
// SubplotsView 新增 props: plotBlocks
{(() => {
  const relatedBlocks = plotBlocks.filter(b => {
    const start = b.chapter_start
    const end = b.chapter_end || 999999
    // 支线的任何一个关键章节落在情节块区间内即视为相关
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

**涉及文件**：
- `frontend/src/components/workbench/structure/StructureTab.tsx`
  - `SubplotsView` props 新增 `plotBlocks: PlotBlock[]`
  - `renderContent` 中传入 `plotBlocks`
  - 支线卡片底部新增交叉引用行（~20 行新增）

---

### P2.3 SVG 内联图表组件化

**现状**：`TrackingTab.tsx` 中的节奏对比视图和风格偏差趋势图使用内联 `<svg>`，违反项目的"禁止内联 SVG"规则（已在 AGENTS.md 已知问题中备案）。

**方案**：将 SVG 图表逻辑抽取为独立组件文件，并在 AGENTS.md 中更新为豁免说明（数据可视化图表不属于"内联 SVG 图标"范畴）。

```
src/components/workbench/tracking/
├── charts/
│   ├── RhythmComparisonChart.tsx   # 节奏对比叠加曲线图
│   └── DialogueRatioTrendChart.tsx # 对话占比趋势折线图
```

**涉及文件**：
- 新建 `frontend/src/components/workbench/tracking/charts/RhythmComparisonChart.tsx`（~80 行迁移）
- 新建 `frontend/src/components/workbench/tracking/charts/DialogueRatioTrendChart.tsx`（~30 行迁移）
- 修改 `frontend/src/components/workbench/tracking/TrackingTab.tsx`（删除内联 SVG，替换为组件引用）
- 修改 `AGENTS.md`（更新已知问题条目为豁免说明）

---

## 实施路线图

```
Phase 1（P0：闭环断裂修复，4-6h）
┌─────────────────────────────────────┐
│ P0.1 风格偏差注入 WRITING 上下文     │
│ P0.2 情节块 questions 注入上下文     │
│ P0.3 节奏 quick-check hook          │
├─────────────────────────────────────┤
│ 验证：docker compose restart backend │
│ 验证：写新章节，观察 context 是否含   │
│       style_deviation / questions    │
└─────────────────────────────────────┘
        ↓
Phase 2（P1：自动化增强，6-8h）
┌─────────────────────────────────────┐
│ P1.1 伏笔自动回收检测（方案 A）       │
│ P1.2 支线交汇自动提醒                │
│ P1.3 风格分析指标深化                │
│ P1.4 情节块完成自动检测（可选）       │
├─────────────────────────────────────┤
│ 数据库变更：P1.3 需 alembic 迁移      │
│ 验证：alembic upgrade head           │
│      + docker compose restart backend │
└─────────────────────────────────────┘
        ↓
Phase 3（P2：UI/UX 优化，3-4h）
┌─────────────────────────────────────┐
│ P2.1 合并问题链到情节块视图          │
│ P2.2 支线 × 情节块交叉引用           │
│ P2.3 SVG 图表组件化                  │
├─────────────────────────────────────┤
│ 验证：docker compose build frontend  │
│      + docker compose up -d frontend │
└─────────────────────────────────────┘
```

**总预估**：13-18 小时

---

## 改动文件总览

| 文件 | Phase | 改动量 |
|------|-------|--------|
| `backend/app/agents/agent_context.py` | P0.1, P0.2, P1.2 | +70 行 |
| `backend/app/agents/prompts.py` | P0.1, P0.2 | +10 行 |
| `backend/app/agents/tools/hooks.py` | P0.3, P1.1, P1.4 | +85 行 |
| `backend/app/agents/tools/creation/record_chapter_meta.py` | P1.1, P1.3 | +52 行 |
| `backend/app/models/style_snapshot.py` | P1.3 | +3 字段 |
| `backend/app/agents/tools/perception/style_analysis.py` | P1.3 | +15 行 |
| `backend/app/agents/services/stores/plot_store.py` | P1.4 | +10 行 |
| `alembic/versions/` | P1.3 | 1 迁移文件 |
| `frontend/src/components/workbench/structure/StructureTab.tsx` | P2.1, P2.2 | -80/+55 行 |
| `frontend/src/components/workbench/tracking/TrackingTab.tsx` | P1.3, P2.3 | -110/+20 行 |
| `frontend/src/components/workbench/tracking/charts/RhythmComparisonChart.tsx` | P2.3 | 新建 +80 行 |
| `frontend/src/components/workbench/tracking/charts/DialogueRatioTrendChart.tsx` | P2.3 | 新建 +30 行 |
| `AGENTS.md` | P2.3 | 5 行改动 |

---

## 关键设计决策

1. **P0.3 选轻量 hook 方案而非新表**：新增 `agent_context_notes` 表虽然更完整，但引入 schema 变更成本，且 hook 已经能满足"章节完成后立即反馈"的需求。

2. **P1.3 选 StyleSnapshot 扩展而非独立分析表**：风格快照已有每章一条记录，直接在现有模型上追加字段是最小改动路径。

3. **P2.3 选组件抽取而非图表库迁移**：recharts 虽然功能更强，但引入新依赖 + 学习成本 > 简单抽取现有 SVG 逻辑为独立组件。

---

## 最大杠杆的单点改动

**P0.1（风格偏差注入）**— 25 行代码，让 Agent 在写作时首次拥有"自我风格监控"能力。目前 Agent 写作是完全盲目的——它看不到自己过去章节的风格趋势，只能机械遵守 `style_constraints` 中的规则列表。注入偏差摘要后，Agent 可以主动调整（"最近三章对话比持续下降，本章有意识地增加对话段落"）。

## 最有创意的改动

**P0.3（`_hook_rhythm_quick_check`）**— 用 35 行 hook 代码实现了"每写完一章自动比对预期节奏"，无需新增表、无需改 schema。这个 hook 的妙处在于复用了已有的 `expected_mood`（情节块）和 `tension_score`（时间线）数据，只是建立了它们之间的实时连接。
