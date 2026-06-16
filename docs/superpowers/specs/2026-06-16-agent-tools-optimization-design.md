# Agent 工具优化设计

**日期**：2026-06-16
**状态**：已确认，待实施
**目标**：将 Agent 工具从 43 个精简至 35 个，消除功能重叠，引入程序化成本控制，不损害对话生成质量

---

## 1. 背景与问题

当前 Agent 工具体系存在三个层面的问题：

### 1.1 工具碎片化

同一实体的 create/update/delete 被拆成独立工具，工具列表膨胀到 43 个。Agent 在更多工具间选择，增加选错概率；工具描述占用大量 prompt token 预算。

具体重叠：
- `create_timeline_entry` 完全被 `record_chapter_meta` 的 upsert 逻辑包含
- `batch_update_foreshadowing_status` 是 `update_foreshadowing` 的批量版本
- `consistency_check`（两章比对）和 `check_chapter_transition`（章节衔接）都是 `consistency_scan` 的子集
- `batch_confirm_outlines` 是 `generate_chapter_outline` 的批量操作
- `suggest_foreshadowing` / `suggest_plot_twist` / `writer_block_assist` 核心逻辑相同：基于当前章节状态建议写作方向

### 1.2 LLM 调用成本不可控

4 个工具（`review_chapter`、`rewrite_chapter`、`generate_story_seed`、`generate_world_setting_complete`）在内部调用 LLM，但签名和 docstring 与纯 KB 工具无区别。Agent 无法感知调用成本，可能在单轮中连续消耗大量 token。

### 1.3 控制流重叠

`expand_world_setting` 在冲突严重时自行创建变更提议（`kb.changes.create`），与 `propose_setting_change` 的变更提议流程重叠，导致两条路径都能修改世界观设定。

---

## 2. 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 合并策略 | 只合并语义真正重叠的工具 | CRUD 合并会增加参数复杂度，降低 Agent 工具选择准确率 |
| 成本感知 | 工具元数据分类（`cost_tier`） | 不注入 system prompt，不影响对话质量 |
| 成本控制 | 程序化拦截 + BudgetTracker 降级 | 比"让 Agent 自己判断"更可靠 |
| 控制流 | `expand_world_setting` 冲突时返回提示而非自行创建变更提议 | 保持变更提议单一入口 |

---

## 3. 工具合并详情

### 3.1 `create_timeline_entry` → 并入 `record_chapter_meta`

`record_chapter_meta` 已实现时间线 upsert（`get_by_chapter_number` → create/update），`create_timeline_entry` 功能完全被包含。

- **变更**：`record_chapter_meta` docstring 补充说明"这是记录章节追踪数据的唯一入口"
- **移除**：`creation/timeline_entry.py`

### 3.2 `batch_update_foreshadowing_status` → 并入 `update_foreshadowing`

`update_foreshadowing` 增加可选参数 `foreshadowing_ids: str = "[]"`：
- 传入 `foreshadowing_id`（单个）→ 原有行为
- 传入 `foreshadowing_ids`（JSON 列表）→ 批量更新，内部复用 `batch_update_foreshadowing_status` 的循环逻辑
- 两个都传 → 返回参数冲突提示

- **移除**：`creation/batch_update_foreshadowing_status.py`

### 3.3 `check_chapter_transition` + `consistency_check` → 并入 `consistency_scan`

`consistency_scan` 增加 `mode: str = "full"` 参数：
- `"full"` — 原有全书扫描行为
- `"transition"` — 执行章节衔接检查，需提供 `chapter_number: int = 0`
- `"compare"` — 执行两章比对，需提供 `chapter_a: int = 0` / `chapter_b: int = 0`

`consistency_check` 的交叉分析逻辑（角色名提取、时间线对比、设定红线）完整搬入 compare 分支。`check_chapter_transition` 的情绪跳跃检测、场景切换检测完整搬入 transition 分支。

- **移除**：`perception/check_chapter_transition.py`、`perception/consistency_check.py`

### 3.4 `batch_confirm_outlines` → 并入 `generate_chapter_outline`

`generate_chapter_outline` 增加可选参数 `batch_chapter_numbers: str = "[]"`：
- 不传 → 原有单章大纲生成行为
- 传入 JSON 列表 → 批量确认模式，内部复用 `batch_confirm_outlines` 的逻辑

- **移除**：`creation/batch_confirm_outlines.py`

### 3.5 `suggest_foreshadowing` + `suggest_plot_twist` + `writer_block_assist` → `suggest_writing_direction`

三个工具的核心逻辑都是"基于当前章节状态建议写作方向"，合并为一个工具：

```python
@tool
async def suggest_writing_direction(
    current_chapter: int,
    focus: str = "auto",  # "foreshadowing" | "twist" | "block" | "auto"
) -> dict:
```

- `focus="foreshadowing"` → 原 `suggest_foreshadowing` 的伏笔建议逻辑
- `focus="twist"` → 原 `suggest_plot_twist` 的反转建议逻辑
- `focus="block"` → 原 `writer_block_assist` 的卡壳辅助逻辑
- `focus="auto"` → 智能选择：有超期伏笔优先建议伏笔，张力低优先建议反转，否则返回所有三类建议的合并摘要

- **新增**：`assist/suggest_writing_direction.py`
- **移除**：`assist/suggest_foreshadowing.py`、`assist/suggest_plot_twist.py`、`assist/writer_block_assist.py`

### 3.6 `expand_world_setting` 控制流修复

`expand_world_setting` 在冲突严重时不再自行创建变更提议（`kb.changes.create`），改为返回冲突信息和提示，引导 Agent 调用 `propose_setting_change`。保持变更提议单一入口。

不减少工具数，但消除控制流重叠。

---

## 4. 工具元数据分类

### 4.1 `cost_tier` 定义

| cost_tier | 含义 | 典型工具 |
|-----------|------|----------|
| `llm` | 调用 LLM，产生 token 开销 | `review_chapter`, `rewrite_chapter`, `generate_story_seed`, `generate_world_setting_complete` |
| `db` | 读写知识库，无 LLM 开销 | 所有 create/update/delete 工具, `knowledge_search`, `progress_report` 等 |
| `rule` | 纯规则计算，只读 KB | `consistency_scan`, `rhythm_analysis`, `style_analysis`, `foreshadowing_check` |

### 4.2 标注方式

在 `registry.py` 中用字典声明，不修改工具的 `@tool` 定义：

```python
TOOL_COST_TIER = {
    "review_chapter": "llm",
    "rewrite_chapter": "llm",
    "generate_story_seed": "llm",
    "generate_world_setting_complete": "llm",
    "consistency_scan": "rule",
    "rhythm_analysis": "rule",
    "style_analysis": "rule",
    "foreshadowing_check": "rule",
    "progress_report": "rule",
}
```

未在字典中的工具默认为 `db`。查询函数：

```python
def get_cost_tier(tool_name: str) -> str:
    return TOOL_COST_TIER.get(tool_name, "db")
```

**不注入 system prompt**，仅供程序化控制使用。

---

## 5. 程序化成本控制

### 5.1 连续 LLM 调用计数器

在 `_wrap_tool_with_hooks_and_cache` 的 wrapper 中维护请求级计数器：

- 计数器存储在 `ToolResultCache` 旁边的请求级容器中，通过 `tool_context` 的 `get_tool_cache()` 获取
- 单轮最多连续调用 LLM 工具 `_MAX_LLM_CALLS_PER_TURN = 3` 次
- 超限时返回 `skipped` 提示而非执行：
  ```python
  return {
      "skipped": True,
      "reason": "本轮已调用 N 次 LLM 工具，达到上限。建议先使用感知工具收集信息，下轮再调用。",
      "tool_name": tool_name,
  }
  ```
- 每次 SSE 请求重置计数器

阈值依据：`review_chapter` + `rewrite_chapter` 是典型配对（2 次），再加 1 次余量。超过 3 次几乎一定是 Agent 在反复尝试。

### 5.2 BudgetTracker 集成的动态降级

`BudgetTracker`（`agent_context.py`）新增字段和方法：

```python
class BudgetTracker:
    llm_tool_tokens_used: int = 0  # LLM 工具消耗的 token 总量

    def should_throttle_llm_tool(self) -> bool:
        """当剩余预算 < 20% 时，建议节流"""
        if self.total_budget <= 0:
            return False
        remaining = 1 - (self.tokens_used / self.total_budget)
        return remaining < 0.2
```

LLM 工具执行前检查：预算不足时返回 `skipped` 提示。

### 5.3 感知工具输出截短

预算紧张时，感知工具返回值可截短以节省上下文空间：

```python
if budget_tracker.should_throttle_llm_tool() and is_perception:
    result = _truncate_result(result, max_items=5, max_str_len=100)
```

`_truncate_result` 递归遍历 dict/list，列表截到 `max_items` 项，字符串截到 `max_str_len` 字符。

### 5.4 三个机制的优先级

1. **BudgetTracker 降级**（最高）— 预算不足时直接拦截 LLM 工具
2. **计数器**（次之）— 预算尚可但单轮调用过多时拦截
3. **截短**（最低）— 两个都没触发时正常返回完整结果

### 5.5 对 Agent 行为的影响

Agent 收到 `skipped: True` 后看到原因说明，自然转向其他工具或汇报用户。这不是报错，是流程控制信号，与"伏笔已超期"等感知结果性质相同。Agent 的推理链不被中断。

---

## 6. 注册表更新

### 6.1 阶段工具集

合并后：

```python
INCUBATION_TOOLS = [
    advance_phase, knowledge_search, progress_report,
    expand_world_setting, generate_outline, generate_story_seed,
    generate_world_setting_complete, create_world_setting,
    create_character, create_relation, create_evolution_plan,
    create_style_constraints, create_foreshadowing,
]

_STRUCTURE_EXTRA = [
    foreshadowing_check, review_chapter, rewrite_chapter,
    rhythm_analysis, suggest_writing_direction,
    generate_chapter_outline, propose_outline_adjustment,
    create_plot_block, create_plot_question, create_subplot,
    update_character, update_plot_block, update_plot_question,
    delete_plot_block, apply_change, reject_change, list_proposed_changes,
]

_WRITING_EXTRA = [
    consistency_scan, style_analysis, generate_chapter_content,
    propose_setting_change, propose_chapter_rewrite,
    record_chapter_meta, update_subplot, update_foreshadowing,
]
```

### 6.2 `registry_v2.py`

```python
_LARGE_PROJECT_TOOL_NAMES = {"consistency_scan"}  # check_chapter_transition 已并入
_SMALL_PROJECT_EXCLUDE_NAMES = {"rhythm_analysis"}  # 不变
```

### 6.3 `agent_graph.py` wrapper 更新

`is_perception` 工具名列表更新：

```python
is_perception = tool_name in (
    "knowledge_search", "foreshadowing_check",
    "consistency_scan", "style_analysis",
    "rhythm_analysis", "progress_report",
)
```

---

## 7. 文件变更汇总

| 操作 | 文件 |
|------|------|
| 删除 | `creation/timeline_entry.py` |
| 删除 | `creation/batch_update_foreshadowing_status.py` |
| 删除 | `creation/batch_confirm_outlines.py` |
| 删除 | `perception/check_chapter_transition.py` |
| 删除 | `perception/consistency_check.py` |
| 删除 | `assist/suggest_foreshadowing.py` |
| 删除 | `assist/suggest_plot_twist.py` |
| 删除 | `assist/writer_block_assist.py` |
| 新增 | `assist/suggest_writing_direction.py` |
| 修改 | `creation/record_chapter_meta.py`（补充 docstring） |
| 修改 | `creation/update_foreshadowing.py`（加 `foreshadowing_ids` 参数） |
| 修改 | `creation/generate_chapter_outline.py`（加 `batch_chapter_numbers` 参数） |
| 修改 | `perception/consistency_scan.py`（加 `mode`/`chapter_a`/`chapter_b`/`chapter_number` 参数） |
| 修改 | `assist/expand_world_setting.py`（冲突时不再自行创建变更提议） |
| 修改 | `tools/registry.py`（更新阶段工具集 + `TOOL_COST_TIER` + `get_cost_tier`） |
| 修改 | `tools/registry_v2.py`（更新工具名引用） |
| 修改 | `agents/agent_graph.py`（更新 wrapper + 计数器 + BudgetTracker 集成） |
| 修改 | `agents/agent_context.py`（BudgetTracker 加 `llm_tool_tokens_used` + `should_throttle_llm_tool`） |
| 修改 | `perception/__init__.py`（移除 `consistency_check` / `check_chapter_transition` 导出） |
| 修改 | `creation/__init__.py`（移除 `create_timeline_entry` / `batch_update_foreshadowing_status` / `batch_confirm_outlines` 导出） |
| 修改 | `assist/__init__.py`（移除旧工具导出，加 `suggest_writing_direction`） |
| 修改 | `tools/__init__.py`（如有引用则同步更新） |

**结果**：43 → 35 个工具

---

## 8. 测试策略

- 合并后的每个工具必须有对应测试覆盖新的参数分支
- `consistency_scan` 需测试 `mode="full"` / `"transition"` / `"compare"` 三种路径
- `update_foreshadowing` 需测试单个更新和批量更新
- `suggest_writing_direction` 需测试四种 focus 模式
- `generate_chapter_outline` 需测试单章和批量确认
- 成本控制需测试：计数器超限、BudgetTracker 降级、输出截短
- 运行现有测试确保无回归：`test_agent_tools.py`、`test_context_strategy.py`、`test_constants.py`
