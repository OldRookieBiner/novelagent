# Agent 工具体系全面优化实施计划（v3.2 终审修正版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面优化 NovelAgent v0.8.11 的 Agent 工具体系——修复 9 个 Bug、消除参数爆炸、优化查询性能、增加变更闭环、增强检测能力、支持阶段回退、改进缓存结构、提升伏笔建议精度

**Architecture:** 分 4 批按优先级递进实施。第 1 批修复 P0 Bug + 消除参数爆炸（无外部依赖），第 2 批优化查询和缓存性能，第 3 批增加变更闭环 + 阶段回退，第 4 批增强检测和精度。每批完成后跑测试验证。

**Tech Stack:** Python 3.11, LangChain/LangGraph, FastAPI, SQLAlchemy, pytest

**Spec:** `docs/superpowers/specs/2026-06-14-agent-tools-optimization.md`

**v3.1 修订:** 基于 v3 plan 的第二轮源码交叉验证，发现 A6 实为 P0 功能 Bug（`update_subplot` 的 `title` 和 `resolution` 是幻影参数），新增 A8（`update_plot_question` 的 `question` 和 `answer` 是幻影参数）。两个参数通过 setattr 设置但不会持久化到 DB

---

## File Structure

### 新增文件（5 个）

| 文件 | 职责 |
|------|------|
| `tools/modification/apply_change.py` | 应用变更提议到知识库 |
| `tools/modification/reject_change.py` | 拒绝变更提议 |
| `tools/modification/list_proposed_changes.py` | 列出待决策变更 |
| `tests/test_tool_cache.py` | ToolResultCache 单元测试 |
| `tests/test_change_workflow.py` | 变更闭环工具测试 |

### 修改文件（19 个）

| 文件 | 改动 |
|------|------|
| `tools/creation/subplot.py` | 修复 docstring（A1） |
| `tools/creation/plot_question.py` | 修复 docstring（A2） |
| `tools/creation/update_plot_block.py` | 替换 chapter_range + 修复 docstring（A3） |
| `tools/creation/plot_block.py` | 修复 docstring（A5） |
| `tools/modification/propose_chapter_rewrite.py` | 删除 docstring 中的 focus（A4） |
| `tools/creation/update_subplot.py` | 修复幻影参数 title→name, resolution→expected_resolution_chapter（A6） |
| `tools/modification/propose_setting_change.py` | 修复 docstring 参数顺序（A7） |
| `tools/creation/generate_chapter_content.py` | 删除 10 个废弃参数及功能代码 + 统一 KB 获取（B1） |
| `tools/perception/knowledge_search.py` | 降级路径 token 预算控制（C1） |
| `agents/agent_context.py` | 修订阶段 BudgetTracker + world_setting（D1） |
| `tools/assist/expand_world_setting.py` | severe 时走变更提议（E4） |
| `tools/modification/__init__.py` | 导出 3 个新工具（E5） |
| `tools/registry.py` | 注册 3 个新工具（E5） |
| `tools/__init__.py` | 总导出更新（E5） |
| `agents/agent_tools.py` | 兼容层导出更新（E5） |
| `tools/creation/advance_phase.py` | 新增 direction=backward + phase_labels 提前（G1） |
| `tools/perception/consistency_scan.py` | 情绪凝固 + 设定匹配优化 + foreshadowing 类型（F1-F3） |
| `tools/assist/suggest_foreshadowing.py` | 停用词 + 阈值提升 + 退化分支（J1） |

### 仅 docstring 修改（H1，~11 文件）

| 文件 | Prerequisites 内容 |
|------|-------------------|
| `creation/generate_chapter_content.py` | 本章大纲必须已确认；写入正文后使用 record_chapter_meta |
| `creation/record_chapter_meta.py` | generate_chapter_content 已写入章节正文 |
| `creation/generate_chapter_outline.py` | generate_outline 已创建总大纲 |
| `creation/rewrite_chapter.py` | 先 review_chapter 获取审查结果 |
| `perception/check_chapter_transition.py` | 第 N-1 章已有正文，第 N 章已有大纲 |
| `modification/propose_setting_change.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `modification/propose_outline_adjustment.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `modification/propose_chapter_rewrite.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `assist/expand_world_setting.py` | 与🔴设定冲突时自动创建变更提议 |
| `creation/advance_phase.py` | direction="forward" 前进（默认），direction="backward" 回退只允许退一级 |
| `creation/batch_confirm_outlines.py` | 需先 generate_chapter_outline 创建章节大纲 |

---

## 第 1 批: Bug 修复 + 参数爆炸

### Task 1: 修复 create_subplot docstring（A1）

**Files:**
- Modify: `backend/app/agents/tools/creation/subplot.py`

- [ ] **Step 1: 修复 docstring**

将 docstring 的 Args 部分重写为：
```
Args:
    name: 支线名称
    characters: JSON 字符串列表，参与角色名（默认 []）
    current_status: 支线状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)（默认 developing）
    raised_in_chapter: 支线提出的章节号（可选）
    planned_intersection_chapter: 计划与主线交汇的章节号（可选）
    expected_resolution_chapter: 预期解决的章节号（可选）
```

- [ ] **Step 2: 验证**

读取文件，确认 docstring Args 中的每个参数名都在函数签名中存在，反之亦然。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/creation/subplot.py
git commit -m "fix(workflow): correct create_subplot docstring to match signature"
```

### Task 2: 修复 create_plot_question docstring（A2）

**Files:**
- Modify: `backend/app/agents/tools/creation/plot_question.py`

- [ ] **Step 1: 修复 docstring**

将 docstring Args 重写为：
```
Args:
    question_text: 问题内容
    raised_in_chapter: 提出问题的章节号（可选）
    plot_block_id: 所属情节块 ID（可选）
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/creation/plot_question.py
git commit -m "fix(workflow): correct create_plot_question docstring to match signature"
```

### Task 3: 修复 update_plot_block chapter_range + docstring（A3）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_plot_block.py`

- [ ] **Step 1: 替换参数**

将 `chapter_range: str | None = None` 替换为 `chapter_start: int | None = None` 和 `chapter_end: int | None = None`。

- [ ] **Step 2: 更新 docstring**

```
Args:
    plot_block_id: 情节块 ID
    title: 情节块标题（可选，None 表示不修改）
    chapter_start: 情节块起始章节号（可选，None 表示不修改）
    chapter_end: 情节块结束章节号（可选，None 表示不修改）
    must_happen: JSON 字符串列表，必须发生的事件（可选）
    questions_to_raise: JSON 字符串列表，需要提出的问题（可选）
    questions_to_answer: JSON 字符串列表，需要回答的问题（可选）
    completion_summary: 完成总结（可选，None 表示不修改）
```

- [ ] **Step 3: 更新 update_data 构建逻辑**

将 `for field in ("title", "chapter_range", "completion_summary"):` 改为：
```python
for field in ("title", "chapter_start", "chapter_end", "completion_summary"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```

- [ ] **Step 4: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/creation/update_plot_block.py
git commit -m "fix(workflow): replace chapter_range with chapter_start/end in update_plot_block"
```

### Task 4: 修复 propose_chapter_rewrite docstring（A4）

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_chapter_rewrite.py`

- [ ] **Step 1: 删除 docstring 中的 focus 行**

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/propose_chapter_rewrite.py
git commit -m "fix(workflow): remove phantom focus param from propose_chapter_rewrite docstring"
```

### Task 5: 修复 create_plot_block docstring（A5）

**Files:**
- Modify: `backend/app/agents/tools/creation/plot_block.py`

- [ ] **Step 1: 修复 docstring**

将 `chapter_range` 替换为 `chapter_start` 和 `chapter_end`，并为 JSON 参数补充类型提示：
```
Args:
    title: 情节块标题
    chapter_start: 情节块起始章节号
    chapter_end: 情节块结束章节号
    must_happen: JSON 字符串列表，必须发生的事件（默认 []）
    questions_to_raise: JSON 字符串列表，需要提出的问题（默认 []）
    questions_to_answer: JSON 字符串列表，需要回答的问题（默认 []）
    expected_mood: 预期情绪基调（默认空）
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/creation/plot_block.py
git commit -m "fix(workflow): replace chapter_range and add JSON type hints in create_plot_block docstring"
```

### Task 6: 修复 update_subplot 幻影参数（A6，P0 Bug，v3.1 修正）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_subplot.py`

**根因:** Subplot 模型只有 `name` 字段，没有 `title`。`resolution` 也不在模型中。通过 `setattr` 设置的 `title` 和 `resolution` 不会持久化到 DB。

- [ ] **Step 1: 替换幻影参数**

将 `title: str | None = None` 替换为 `name: str | None = None`。
将 `resolution: str | None = None` 替换为 `expected_resolution_chapter: int | None = None`。

- [ ] **Step 2: 更新 docstring**

```
Args:
    subplot_id: 支线 ID
    name: 支线名称（可选，None 表示不修改）
    status: 新状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)（可选）
    expected_resolution_chapter: 预期解决的章节号（可选）
```

- [ ] **Step 3: 更新 update_data 构建逻辑**

将 `for field in ("title", "status", "resolution"):` 改为：
```python
for field in ("name", "status", "expected_resolution_chapter"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```

- [ ] **Step 4: 更新变更对比逻辑**

将 `before.get("title")` 和 `updated.get("title", before.get("title"))` 中的 `"title"` 替换为 `"name"`。

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/tools/creation/update_subplot.py
git commit -m "fix(workflow): replace phantom title/resolution params with name/expected_resolution_chapter in update_subplot"
```

### Task 7: 修复 propose_setting_change docstring 参数顺序（A7，v3 新增）

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_setting_change.py`

- [ ] **Step 1: 修复 docstring Args 顺序**

将 Args 顺序从 `target_type, target_id, description, new_value` 改为 `target_type, target_id, new_value, description`：
```
Args:
    target_type: 修改对象类型 - "world_setting", "character", "foreshadowing", "style", "outline", "relation"
    target_id: 修改对象的 ID
    new_value: 新值（JSON 字符串或普通字符串）
    description: 变更内容的自然语言描述
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/propose_setting_change.py
git commit -m "fix(workflow): fix propose_setting_change docstring param order"
```

### Task 7.5: 修复 update_plot_question 幻影参数（A8，P0 Bug，v3.1 新增）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_plot_question.py`

**根因:** PlotQuestion 模型只有 `question_text` 和 `answered_in_chapter` 字段，没有 `question` 和 `answer`。通过 `setattr` 设置的 `question` 和 `answer` 不会持久化到 DB。

- [ ] **Step 1: 替换幻影参数**

将 `question: str | None = None` 替换为 `question_text: str | None = None`。
将 `answer: str | None = None` 替换为 `answered_in_chapter: int | None = None`。

- [ ] **Step 2: 更新 docstring**

```
Args:
    question_id: 问题 ID
    question_text: 问题内容（可选，None 表示不修改）
    answered_in_chapter: 回答章节号（可选，标记问题被回答的章节）
    status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭)（可选）
```

- [ ] **Step 3: 更新 update_data 构建逻辑**

将 `for field in ("question", "answer", "status"):` 改为：
```python
for field in ("question_text", "answered_in_chapter", "status"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```

- [ ] **Step 4: 更新变更对比逻辑**

将 `before.get("question")` 等中的 `"question"` 替换为 `"question_text"`，`"answer"` 替换为 `"answered_in_chapter"`。

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/tools/creation/update_plot_question.py
git commit -m "fix(workflow): replace phantom question/answer params with question_text/answered_in_chapter in update_plot_question"
```

### Task 8: 精简 generate_chapter_content 参数（B1）

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_chapter_content.py`

- [ ] **Step 1: 删除废弃参数**

从函数签名中删除 10 个废弃参数。最终签名：
```python
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    word_count: int = 0,
) -> dict:
```

- [ ] **Step 2: 删除废弃功能代码**

1. 删除 `new_fs`/`reclaimed_ids` 的 `parse_json_param` 调用
2. 删除步骤 2（时间线创建）整个 `if timeline_summary:` 代码块
3. 删除步骤 3（创建新伏笔）整个 `for fs_data in new_fs:` 循环
4. 删除步骤 4（回收伏笔）整个 `for fs_id in reclaimed_ids:` 循环
5. 删除 `warnings` 列表中与上述步骤相关的所有 append
6. 保留步骤 1（保存章节正文）和步骤 5（风格快照）

- [ ] **Step 3: 统一 KB 获取方式**

将 `from app.agents.services.knowledge_base import KnowledgeBaseService` + `kb = KnowledgeBaseService(project_id)` 替换为 `kb = _kb()`。同时确保文件顶部有 `from app.agents.tools.utils import _kb, parse_json_param` 导入。

- [ ] **Step 4: 更新 docstring**

删除废弃参数说明。增加 Prerequisites 段落。

- [ ] **Step 5: 更新返回值**

删除 `timeline_entry`/`timeline_error`/`new_foreshadowings`/`new_foreshadowing_errors`/`reclaimed_foreshadowings`/`reclaim_errors`。保留 `action`/`chapter_number`/`title`/`word_count`/`style_snapshot_created`/`style_snapshot_error`/`message`/`warnings`。

- [ ] **Step 6: 验证 Hook 兼容性**

确认返回值仍包含 `chapter_number` 字段（Hook 链 `hooks.py` 依赖此字段）。

- [ ] **Step 7: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/tools/creation/generate_chapter_content.py
git commit -m "refactor(workflow): remove deprecated tracking params from generate_chapter_content"
```

---

## 第 2 批: 查询优化 + 缓存优化 + 修订上下文

### Task 9: knowledge_search 降级路径 token 控制（C1）

**Files:**
- Modify: `backend/app/agents/tools/perception/knowledge_search.py`

- [ ] **Step 1: 更新常量**

将 `_FALLBACK_MAX_PER_TYPE = 5` 改为 `_MAX_ITEMS_PER_TYPE = 10`。新增导入：
```python
from app.agents.token_budget import estimate_tokens
import json
MAX_FALLBACK_TOKENS = 4000
```

- [ ] **Step 2: 重构降级路径为步骤列表+循环**

将平铺的 `if target in (...)` 结构重构为 query_steps 列表+循环，添加 token 预算检查。详见 Spec C1。

关键点：
- token 预算检查只在 `target == "all"` 时执行
- `world_setting.get()` 和 `style_constraints` 返回单个 dict 不需要截断
- `recent_style_snapshots` 已通过 `last_n=5` 限制

- [ ] **Step 3: 简化关系匹配**

只在 `results` 中已有 characters 数据时执行关系匹配。只匹配结果中已有角色的关系。截断为 `_MAX_ITEMS_PER_TYPE` 条。

- [ ] **Step 4: 更新 docstring**

增加"降级模式下有 token 预算限制（4000 token），大数据集建议使用精确 target 参数"

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/tools/perception/knowledge_search.py
git commit -m "refactor(workflow): add token budget control to knowledge_search fallback path"
```

### Task 10: 修订阶段上下文预算控制（D1）

**Files:**
- Modify: `backend/app/agents/agent_context.py`

- [ ] **Step 1: 重写 _load_revision_context**

使用 BudgetTracker 做逐项控制。加载顺序和数据格式：

1. **world_setting**（v3 新增）: 精简版，`core_concept` + `red_settings` + `key_locations`
2. **characters**: 索引模式（id + name + role），与 writing 阶段一致
3. **foreshadowings**: 精简模式（id + content[:60] + status + planted_chapter + expected_resolve_chapter）
4. **timeline**: 最近 20 章摘要（`timeline[:20]`），每条 `chapter_number` + `summary[:80]` + `emotion_tag`
5. **plot_questions**: 只加载 pending 状态
6. **subplots**: 只加载非 abandoned 状态
7. **style_snapshots**: 只加载最近 10 条（`kb.styles.list_snapshots(last_n=10)`）
8. **style_constraints**: 保留（走预算检查）

每种数据加载后做 `budget.can_add` 检查，超限则跳过后续。

- [ ] **Step 2: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/agent_context.py
git commit -m "fix(workflow): add BudgetTracker to revision context and include world_setting"
```

### Task 11: ToolResultCache 前缀索引优化（I1）

**Files:**
- Modify: `backend/app/agents/tools/cache.py`
- Create: `backend/tests/test_tool_cache.py`

- [ ] **Step 1: 添加 _prefix_index 属性**

在 `__init__` 中新增 `self._prefix_index: dict[str, set[str]] = {}`

- [ ] **Step 2: 更新 set 方法**

同时更新 `_prefix_index`

- [ ] **Step 3: 更新 invalidate 方法**

改为基于索引的 O(1) 查找

- [ ] **Step 4: 更新 invalidate_by_prefix 方法**

统一处理 prefix 格式（`rstrip(":")`）

- [ ] **Step 5: 更新 clear 方法**

同时清空 `_prefix_index`

- [ ] **Step 6: 编写测试**

创建 `backend/tests/test_tool_cache.py`，覆盖: 命中/未命中、invalidate、invalidate_by_prefix、clear、前缀索引一致性、invalidate 不存在的工具不报错

- [ ] **Step 7: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v tests/test_tool_cache.py`

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/tools/cache.py backend/tests/test_tool_cache.py
git commit -m "refactor(workflow): add prefix index to ToolResultCache for O(1) invalidation"
```

---

## 第 3 批: 变更闭环 + 阶段回退

### Task 12: 新增 apply_change 工具（E1）

**Files:**
- Create: `backend/app/agents/tools/modification/apply_change.py`

- [ ] **Step 1: 创建工具文件**

核心逻辑：
1. `kb.changes.get(change_id)` 获取变更
2. 如果返回 None，返回 `{"error": f"变更 ID {change_id} 不存在"}`
3. 检查 status == proposed，否则返回错误
3. 根据 target_type 调用对应 Store 更新方法
4. Store 更新成功后 `kb.changes.update(change_id, {"status": "applied", "author_decision": "proceed"})`
5. Store 更新失败时不更新变更状态
6. `chapter_rewrite` 类型返回提示信息引导使用 `rewrite_chapter`
7. `outline_adjustment` 类型调用 `kb.outlines.update(new_value)`，忽略 target_id

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/apply_change.py
git commit -m "feat(workflow): add apply_change tool for change proposal workflow"
```

### Task 13: 新增 reject_change 工具（E2）

**Files:**
- Create: `backend/app/agents/tools/modification/reject_change.py`

- [ ] **Step 1: 创建工具文件**

核心逻辑：
1. `kb.changes.get(change_id)` → 如果 None 返回错误 → 检查 status == proposed
2. 更新 `{"status": "abandoned", "author_decision": "abandon"}`
3. 有 reason 时追加到 description
4. 返回 action/rejected/change_id/target_type/reason/message

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/reject_change.py
git commit -m "feat(workflow): add reject_change tool for change proposal workflow"
```

### Task 14: 新增 list_proposed_changes 工具（E3）

**Files:**
- Create: `backend/app/agents/tools/modification/list_proposed_changes.py`

- [ ] **Step 1: 创建工具文件**

核心逻辑：
1. `kb.changes.list_changes(status="proposed")`
2. 按 target_type 过滤
3. 每项返回 id/target_type/target_id/description[:80]/impact_level/created_at
4. 返回 total/changes/message

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/list_proposed_changes.py
git commit -m "feat(workflow): add list_proposed_changes tool"
```

### Task 15: 更新 expand_world_setting 走变更提议流程（E4）

**Files:**
- Modify: `backend/app/agents/tools/assist/expand_world_setting.py`

- [ ] **Step 1: 在写入之前新增 severity 判断**

源码当前是无条件写入（无 severity 判断）。在 `kb.world_setting.update_by_id(...)` 调用之前插入：

```python
if impact_level == "severe":
    change = kb.changes.create({
        "target_type": "world_setting",
        "target_id": ws["id"],
        "old_value": {"tiered_settings": tiered},
        "new_value": {"tiered_settings": updated_tiered},
        "description": f"扩展世界观（{aspect}）：{description[:100]}",
        "status": "proposed",
        "impact_report": {"level": impact_level, "contradictions": contradictions},
    })
    return {
        "action": "proposed",
        "change_id": change["id"],
        "impact_level": impact_level,
        "impact_detail": impact_detail,
        "contradictions": contradictions,
        "suggestion": "扩展与🔴设定冲突，已创建变更提议，请使用 apply_change 或 reject_change 决策",
        "written": False,
    }

# impact_level != severe 时保持现有直接写入逻辑
```

- [ ] **Step 2: 更新 docstring**

增加说明：与🔴设定冲突时自动创建变更提议而非直接写入。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/assist/expand_world_setting.py
git commit -m "fix(workflow): expand_world_setting creates change proposal on severe conflict"
```

### Task 16: 更新注册表和导出（E5）

**Files:**
- Modify: `backend/app/agents/tools/modification/__init__.py`
- Modify: `backend/app/agents/tools/registry.py`
- Modify: `backend/app/agents/tools/__init__.py`
- Modify: `backend/app/agents/agent_tools.py`

- [ ] **Step 1: 更新 modification/__init__.py**

新增三行导出

- [ ] **Step 2: 更新 registry.py**

在 modification 导入中新增三个工具。在 `_STRUCTURE_EXTRA` 列表末尾添加。

- [ ] **Step 3: 更新 tools/__init__.py**

在修改工具导入区新增三个工具。

- [ ] **Step 4: 更新 agent_tools.py 兼容层**

新增三个工具的导入。

- [ ] **Step 5: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/tools/modification/__init__.py backend/app/agents/tools/registry.py backend/app/agents/tools/__init__.py backend/app/agents/agent_tools.py
git commit -m "feat(workflow): register apply_change, reject_change, list_proposed_changes tools"
```

### Task 17: advance_phase 支持阶段回退（G1）

**Files:**
- Modify: `backend/app/agents/tools/creation/advance_phase.py`

- [ ] **Step 1: 新增 direction 参数**

函数签名新增 `direction: str = "forward"`

- [ ] **Step 2: 将 phase_labels 定义提前到回退逻辑之前**

当前源码中 `phase_labels` 定义在行锁代码之后、return 之前。需将其提前到前进/回退判断之前：

```python
phase_labels = {
    Phase.INCUBATION: "创意孵化",
    Phase.STRUCTURE: "结构设计",
    Phase.WRITING: "写作中",
    Phase.REVISION: "修订中",
}

if direction == "backward":
    # ... 回退逻辑
elif current_phase == Phase.INCUBATION:
    # ... 原有前进逻辑
```

- [ ] **Step 3: 添加回退逻辑**

详见 Spec G1。关键点：
- rollback_map: `{WRITING: STRUCTURE, STRUCTURE: INCUBATION}`
- REVISION 和 INCUBATION 不可回退
- 回退复用 `if advanced:` 的行锁写入逻辑

- [ ] **Step 4: 更新 docstring**

新增 direction 参数说明

- [ ] **Step 5: 更新返回值**

增加 `direction` 字段

- [ ] **Step 6: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/tools/creation/advance_phase.py
git commit -m "feat(workflow): add backward direction to advance_phase for phase rollback"
```

### Task 18: 更新测试文件

**Files:**
- Modify: `backend/tests/test_advance_phase.py`
- Modify: `backend/tests/test_agent_tools.py`
- Create: `backend/tests/test_change_workflow.py`

- [ ] **Step 1: 更新 test_advance_phase.py**

新增回退场景测试:
- `test_writing_rollback_to_structure`: WRITING + backward → STRUCTURE
- `test_structure_rollback_to_incubation`: STRUCTURE + backward → INCUBATION
- `test_incubation_cannot_rollback`: INCUBATION + backward → 不变
- `test_revision_cannot_rollback`: REVISION + backward → 不变

- [ ] **Step 2: 更新 test_agent_tools.py**

新增修改闭环工具注册测试:
```python
def test_change_workflow_tools_are_present(self):
    names = [t.name for t in WRITING_TOOLS]
    for expected in ['apply_change', 'reject_change', 'list_proposed_changes']:
        assert expected in names, f'Missing change workflow tool: {expected}'
```

- [ ] **Step 3: 创建 test_change_workflow.py**

测试 apply_change/reject_change/list_proposed_changes 的核心逻辑（mock KB）:
- apply_change: 非 proposed 时返回错误；各 target_type 正确路由；chapter_rewrite 引导；Store 失败不更新状态
- reject_change: 非 proposed 时返回错误；有 reason 追加 description
- list_proposed_changes: 空/有数据；target_type 过滤

- [ ] **Step 4: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/
git commit -m "test(workflow): add phase rollback and change workflow tests"
```

### Task 19: 工具调用时机 Prerequisites 文档（H1）

**Files:**
- Modify: ~11 个工具文件的 docstring（只改 docstring，不改逻辑）

- [ ] **Step 1: 逐文件更新 docstring**

在每个工具 docstring 的描述段落末尾增加 Prerequisites 块。详见 Plan 顶部 "仅 docstring 修改" 表格。

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/
git commit -m "docs(workflow): add Prerequisites section to tool docstrings"
```

---

## 第 4 批: 一致性检测增强 + 伏笔建议精度

### Task 20: consistency_scan 增加情绪凝固 + 设定匹配优化 + foreshadowing 类型（F1-F3）

**Files:**
- Modify: `backend/app/agents/tools/perception/consistency_scan.py`

- [ ] **Step 1: 新增情绪凝固检测（F1）**

在现有情绪跳跃检测之后，新增全局情绪凝固检测。详见 Spec F1。

- [ ] **Step 2: 优化设定引用矛盾检测（F2）**

将 `len(rule_text) >= 4` 改为 >= 6 用字符串匹配，4-5 用分词匹配。confidence 区分 low/very_low。长度 < 4 不检测。

- [ ] **Step 3: 新增 foreshadowing 检查类型（F3）**

1. `check_types` 参数新增 `"foreshadowing"` 选项
2. 新增伏笔一致性检测:
   - planted_chapter > expected_resolve_chapter（数据录入错误）
   - active 状态但 expected_resolve_chapter 已过 5+ 章（超期伏笔）。当前章节号从 `scan_chapter_numbers` 最大值推断
   - reclaimed 状态但 resolved_chapter 为空（数据不完整）
3. 更新 docstring

- [ ] **Step 4: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/perception/consistency_scan.py
git commit -m "feat(workflow): add emotion stagnation, foreshadowing checks and optimize setting matching"
```

### Task 21: suggest_foreshadowing 停用词过滤和阈值提升（J1）

**Files:**
- Modify: `backend/app/agents/tools/assist/suggest_foreshadowing.py`

- [ ] **Step 1: 新增局部停用词集合**

详见 Spec J1 的 `_SUGGEST_STOPWORDS`

- [ ] **Step 2: 更新过滤逻辑**

区分 jieba/非 jieba 模式的阈值:
```python
min_len = 4 if _jieba_available else 2
min_freq = 3 if _jieba_available else 5
```

需要在文件顶部导入 `from app.utils.text import _jieba_available`

- [ ] **Step 3: 更新 docstring**

说明阈值提升和停用词过滤

- [ ] **Step 4: 运行测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/assist/suggest_foreshadowing.py
git commit -m "refactor(workflow): add stopwords filter and adaptive thresholds for foreshadowing suggestions"
```

---

## 最终验证

### Task 22: 全量测试 + 重启后端

- [ ] **Step 1: 运行全部后端测试**

Run: `docker exec novelagent-backend-1 pytest -v`

- [ ] **Step 2: 重启后端**

Run: `docker compose restart backend`

- [ ] **Step 3: 检查后端日志**

Run: `docker compose logs backend --tail 20`
Expected: 无 import 错误，FastAPI 正常启动

- [ ] **Step 4: 最终 Commit**

```bash
git add -A
git commit -m "chore(workflow): agent tools optimization - all modules A-J complete (v3)"
```
