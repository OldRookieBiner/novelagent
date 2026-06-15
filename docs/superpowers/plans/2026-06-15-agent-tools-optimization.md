# Agent 工具体系全面优化实施计划（v5.1 深度验证终版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 全面优化 NovelAgent v0.8.11 的 Agent 工具体系——修复 11 个 Bug（含 4 个 P0 幻影参数/安全检查失效）+ apply_change 白名单防护、消除参数爆炸、优化查询和缓存性能、增加变更闭环、增强检测能力、支持阶段回退、改进缓存结构、提升伏笔建议精度、修复单调检测逻辑错误

**Architecture:** 分 4 批按优先级递进实施。第 1 批修复 P0 Bug + 消除参数爆炸（无外部依赖），第 2 批优化查询和缓存性能，第 3 批增加变更闭环 + 阶段回退，第 4 批增强检测和精度 + docstring 统一。

**Tech Stack:** Python 3.11, LangChain/LangGraph, FastAPI, SQLAlchemy, pytest

**Spec:** `docs/superpowers/specs/2026-06-15-agent-tools-optimization.md`

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

### 修改文件（23 个）

| 文件 | 改动 |
|------|------|
| `tools/creation/subplot.py` | 修复 docstring（A1） |
| `tools/creation/plot_question.py` | 修复 docstring（A2） |
| `tools/creation/update_plot_block.py` | 替换 chapter_range + 修复 docstring（A3） |
| `tools/modification/propose_chapter_rewrite.py` | 删除 docstring 中的 focus（A4） |
| `tools/creation/plot_block.py` | 修复 docstring + 返回值（A5） |
| `tools/creation/update_subplot.py` | 修复幻影参数 title→name, status→current_status, resolution→expected_resolution_chapter（A6） |
| `tools/modification/propose_setting_change.py` | 修复 docstring 参数顺序（A7） |
| `tools/creation/update_plot_question.py` | 修复幻影参数 question→question_text, answer→answered_in_chapter（A8） |
| `tools/creation/delete_plot_block.py` | 修复 chapter_range→chapter_start/end（A9/K1） |
| `tools/creation/generate_world_setting_complete.py` | 幻影参数 history/social_structure/magic_system 合并到 tiered_settings（A10） |
| `tools/modification/propose_outline_adjustment.py` | chapter_range 格式化 None 安全处理（A11） |
| `tools/creation/generate_chapter_content.py` | 删除 10 个废弃参数 + 统一 KB 获取（B1） |
| `tools/perception/knowledge_search.py` | 降级路径 token 预算控制 + 关系匹配优化（C1） |
| `agents/agent_context.py` | 修订阶段 BudgetTracker + world_setting（D1） |
| `tools/assist/expand_world_setting.py` | severe 时走变更提议（E4） |
| `tools/modification/__init__.py` | 导出 3 个新工具（E5） |
| `tools/registry.py` | 注册 3 个新工具（E5） |
| `tools/__init__.py` | 总导出更新（E5） |
| `agents/agent_tools.py` | 兼容层导出更新（E5） |
| `tools/creation/advance_phase.py` | 新增 direction=backward + phase_labels 提前（G1） |
| `tools/perception/consistency_scan.py` | 情绪凝固 + 设定匹配优化 + foreshadowing 类型（F1-F3） |
| `tools/assist/suggest_foreshadowing.py` | 停用词 + 阈值提升 + 退化分支（J1） |
| `tools/perception/rhythm_analysis.py` | 单调检测逻辑修正（K2） |

### 仅 docstring 修改（H1 + L1，~16 文件）

| 文件 | 改动 |
|------|------|
| `creation/generate_chapter_content.py` | Prerequisites（H1） |
| `creation/record_chapter_meta.py` | Prerequisites（H1） |
| `creation/generate_chapter_outline.py` | Prerequisites（H1） |
| `creation/rewrite_chapter.py` | Prerequisites（H1） |
| `perception/check_chapter_transition.py` | Prerequisites（H1） |
| `modification/propose_setting_change.py` | Prerequisites（H1） |
| `modification/propose_outline_adjustment.py` | Prerequisites（H1） |
| `modification/propose_chapter_rewrite.py` | Prerequisites（H1） |
| `assist/expand_world_setting.py` | Prerequisites（H1） |
| `creation/advance_phase.py` | Prerequisites（H1） |
| `creation/batch_confirm_outlines.py` | Prerequisites（H1） |
| `creation/relation.py` | docstring 中文化（L1） |
| `creation/evolution_plan.py` | docstring 中文化（L1） |
| `creation/foreshadowing.py` | docstring 中文化（L1） |
| `creation/timeline_entry.py` | docstring 中文化（L1） |
| `creation/character.py` | docstring 中文化（L1） |
| `perception/foreshadowing_check.py` | docstring 中文化（L1） |

---

## 第 1 批: Bug 修复 + 参数爆炸

### Task 1: 修复 create_subplot docstring（A1）

**Files:**
- Modify: `backend/app/agents/tools/creation/subplot.py`

- [ ] **Step 1: 重写 docstring Args** — 与函数签名 6 个参数一一对应
- [ ] **Step 2: 验证** — 读取文件确认 Args 与签名一致
- [ ] **Step 3: Commit** — `fix(workflow): correct create_subplot docstring to match signature`

### Task 2: 修复 create_plot_question docstring（A2）

**Files:**
- Modify: `backend/app/agents/tools/creation/plot_question.py`

- [ ] **Step 1: 重写 docstring Args**
- [ ] **Step 2: Commit** — `fix(workflow): correct create_plot_question docstring to match signature`

### Task 3: 修复 update_plot_block chapter_range + docstring（A3）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_plot_block.py`

- [ ] **Step 1:** 将 `chapter_range: str | None = None` 替换为 `chapter_start: int | None = None` + `chapter_end: int | None = None`
- [ ] **Step 2:** 更新 docstring Args
- [ ] **Step 3:** 更新 `update_data` 构建: `for field in ("title", "chapter_start", "chapter_end", "completion_summary")`
- [ ] **Step 4:** 运行测试 `docker exec novelagent-backend-1 pytest -v`
- [ ] **Step 5: Commit** — `fix(workflow): replace chapter_range with chapter_start/end in update_plot_block`

### Task 4: 修复 propose_chapter_rewrite docstring（A4）

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_chapter_rewrite.py`

- [ ] **Step 1:** 删除 docstring 中的 focus 行
- [ ] **Step 2: Commit** — `fix(workflow): remove phantom focus param from propose_chapter_rewrite docstring`

### Task 5: 修复 create_plot_block docstring + 返回值（A5）

**Files:**
- Modify: `backend/app/agents/tools/creation/plot_block.py`

- [ ] **Step 1:** 修复 docstring: `chapter_range` → `chapter_start` + `chapter_end`
- [ ] **Step 2:** 修复返回值: `"chapter_range": f"{chapter_start}-{chapter_end}"` → `"chapter_start": chapter_start, "chapter_end": chapter_end`
- [ ] **Step 3: Commit** — `fix(workflow): fix create_plot_block docstring and return value chapter_range`

### Task 6: 修复 update_subplot 幻影参数（A6，P0 Bug）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_subplot.py`

**根因:** Subplot 模型只有 `name`（非 `title`）、`current_status`（非 `status`）和 `expected_resolution_chapter`（非 `resolution`）。三个参数通过 `setattr` 设置但不持久化。

- [ ] **Step 1:** 将 `title` → `name`，`status` → `current_status`，`resolution` → `expected_resolution_chapter`
- [ ] **Step 2:** 更新 docstring
- [ ] **Step 3:** 更新 `update_data` 构建: `for field in ("name", "current_status", "expected_resolution_chapter")`
- [ ] **Step 4:** 更新变更对比和返回值: `"title"` → `"name"`，`"status"` → `"current_status"`
- [ ] **Step 5:** 运行测试
- [ ] **Step 6: Commit** — `fix(workflow): replace phantom title/status/resolution params in update_subplot`

### Task 7: 修复 propose_setting_change docstring 参数顺序（A7）

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_setting_change.py`

- [ ] **Step 1:** 调整 docstring Args 顺序: `new_value` 在 `description` 之前
- [ ] **Step 2: Commit** — `fix(workflow): fix propose_setting_change docstring param order`

### Task 8: 修复 update_plot_question 幻影参数（A8，P0 Bug）

**Files:**
- Modify: `backend/app/agents/tools/creation/update_plot_question.py`

**根因:** PlotQuestion 模型字段是 `question_text`（非 `question`）和 `answered_in_chapter`（非 `answer`）。

- [ ] **Step 1:** 将 `question` → `question_text`，`answer` → `answered_in_chapter`
- [ ] **Step 2:** 更新 docstring
- [ ] **Step 3:** 更新 `update_data` 和变更对比逻辑
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `fix(workflow): replace phantom question/answer params in update_plot_question`

### Task 9: 修复 delete_plot_block chapter_range 安全检查（A9/K1，P0 Bug）

**Files:**
- Modify: `backend/app/agents/tools/creation/delete_plot_block.py`

**根因:** PlotBlock 模型中无 `chapter_range` 字段，`target.get("chapter_range", "")` 永远返回空串，活跃伏笔安全检查永远不触发。

- [ ] **Step 1:** 替换为:
```python
chapter_start = target.get("chapter_start")
chapter_end = target.get("chapter_end")
if chapter_start is not None and chapter_end is not None:
    for f in active_fs:
        expected = f.get("expected_resolve_chapter")
        if expected and chapter_start <= expected <= chapter_end:
            affected_foreshadowings.append(...)
```
- [ ] **Step 2:** 运行测试
- [ ] **Step 3: Commit** — `fix(workflow): fix delete_plot_block safety check using chapter_start/end`

### Task 10: 修复 generate_world_setting_complete 幻影参数（A10，P0 Bug）

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_world_setting_complete.py`

**根因:** WorldSetting 模型没有 `history`/`social_structure`/`magic_system` 列。这三个参数通过 setattr 被设为 Python 属性但不会持久化到 DB。

**修复策略:** 合并到 tiered_settings 而非单独字段：
- `history` → `tiered["yellow"]`（历史背景属于可灵活调整的规则）
- `social_structure` → `tiered["yellow"]`（社会结构属于有代价可违反的规则）
- `magic_system` → `tiered["red"]`（魔法体系属于核心不可违反的规则）

- [ ] **Step 1:** 修改数据构建逻辑，将三个参数内容合并到 `tiered` dict 中，不再单独加入 `data`
- [ ] **Step 2:** 保留函数签名中的三个参数（Agent 仍需传入），更新 docstring 说明合并行为
- [ ] **Step 3:** 返回值中增加 `merged_into_tiered: true` 标记
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `fix(workflow): merge phantom history/social_structure/magic_system into tiered_settings`

### Task 11: 修复 propose_outline_adjustment chapter_range 格式化（A11）

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_outline_adjustment.py`

- [ ] **Step 1:** 修改 `chapter_range` 格式化，处理 `chapter_start`/`chapter_end` 为 None 的情况
- [ ] **Step 2: Commit** — `fix(workflow): handle None in propose_outline_adjustment chapter_range formatting`

### Task 12: 精简 generate_chapter_content 参数（B1）

**Files:**
- Modify: `backend/app/agents/tools/creation/generate_chapter_content.py`

- [ ] **Step 1:** 从签名中删除 10 个废弃参数
- [ ] **Step 2:** 删除废弃功能代码块（时间线/伏笔创建/回收步骤 + 相关 warnings）
- [ ] **Step 3:** 统一 KB 获取: 删除 `KnowledgeBaseService(project_id)` 直接使用，改为 `kb = _kb()`
- [ ] **Step 4:** 更新 docstring（删除废弃参数说明，增加 Prerequisites）
- [ ] **Step 5:** 更新返回值（删除追踪相关字段）
- [ ] **Step 6:** 验证 Hook 兼容性 — 返回值仍包含 `chapter_number`
- [ ] **Step 7:** 运行测试
- [ ] **Step 8: Commit** — `refactor(workflow): remove deprecated tracking params from generate_chapter_content`

### Task 13: 修复 rhythm_analysis 单调检测逻辑（K2）

**Files:**
- Modify: `backend/app/agents/tools/perception/rhythm_analysis.py`

**根因:** 逆序遍历导致 start/end 颠倒，每步 append 导致重复记录，length 计数不准确。

- [ ] **Step 1:** 改为正序遍历 + 只在序列结束时记录一次
- [ ] **Step 2:** 阈值从 2 改为 3（3 章以上相同情绪才算单调）
- [ ] **Step 3:** 运行测试
- [ ] **Step 4: Commit** — `fix(workflow): correct rhythm_analysis monotone detection logic`

---

## 第 2 批: 查询优化 + 缓存优化 + 修订上下文

### Task 14: knowledge_search 降级路径 token 控制（C1）

**Files:**
- Modify: `backend/app/agents/tools/perception/knowledge_search.py`

- [ ] **Step 1:** 更新常量 `_MAX_ITEMS_PER_TYPE = 10`，新增 `MAX_FALLBACK_TOKENS = 4000`
- [ ] **Step 2:** 重构降级路径为步骤列表+循环，添加 token 预算检查
- [ ] **Step 3:** 关系匹配只在有 characters 数据时执行，只匹配已有角色
- [ ] **Step 4:** 更新 docstring
- [ ] **Step 5:** 运行测试
- [ ] **Step 6: Commit** — `refactor(workflow): add token budget control to knowledge_search fallback`

### Task 15: 修订阶段上下文预算控制（D1）

**Files:**
- Modify: `backend/app/agents/agent_context.py`

- [ ] **Step 1:** 重写 `_load_revision_context` 使用 BudgetTracker 逐项控制
- [ ] **Step 2:** 加载精简数据: world_setting 精简版、characters 索引、foreshadowings 精简、timeline 最近 20 章、pending 问题、非 abandoned 支线、最近 10 快照
- [ ] **Step 3:** 运行测试
- [ ] **Step 4: Commit** — `fix(workflow): add BudgetTracker to revision context and include world_setting`

### Task 16: ToolResultCache 前缀索引优化（I1）

**Files:**
- Modify: `backend/app/agents/tools/cache.py`
- Create: `backend/tests/test_tool_cache.py`

- [ ] **Step 1:** 添加 `_prefix_index` 属性
- [ ] **Step 2:** 更新 `set`/`invalidate`/`invalidate_by_prefix`/`clear` 方法
- [ ] **Step 3:** 编写 `test_tool_cache.py`
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `refactor(workflow): add prefix index to ToolResultCache for O(1) invalidation`

---

## 第 3 批: 变更闭环 + 阶段回退

### Task 17: 新增 apply_change 工具（E1）

**Files:**
- Create: `backend/app/agents/tools/modification/apply_change.py`

- [ ] **Step 1:** 创建工具文件，实现核心逻辑
- [ ] **Step 2:** 实现 new_value 白名单过滤 — 硬编码 `_ALLOWED_KEYS` dict（target_type → 允许的列名集合），apply 前过滤非模型列名的 key，记录 `filtered_keys` 警告
- [ ] **Step 3:** 运行测试
- [ ] **Step 4: Commit** — `feat(workflow): add apply_change tool with new_value whitelist filtering`

### Task 18: 新增 reject_change 工具（E2）

**Files:**
- Create: `backend/app/agents/tools/modification/reject_change.py`

- [ ] **Step 1:** 创建工具文件
- [ ] **Step 2: Commit** — `feat(workflow): add reject_change tool`

### Task 19: 新增 list_proposed_changes 工具（E3）

**Files:**
- Create: `backend/app/agents/tools/modification/list_proposed_changes.py`

- [ ] **Step 1:** 创建工具文件
- [ ] **Step 2: Commit** — `feat(workflow): add list_proposed_changes tool`

### Task 20: 更新 expand_world_setting 走变更提议流程（E4）

**Files:**
- Modify: `backend/app/agents/tools/assist/expand_world_setting.py`

- [ ] **Step 1:** 在写入前新增 `if impact_level == "severe"` 分支
- [ ] **Step 2:** 更新 docstring
- [ ] **Step 3: Commit** — `fix(workflow): expand_world_setting creates change proposal on severe conflict`

### Task 21: 更新注册表和导出（E5）

**Files:**
- Modify: `tools/modification/__init__.py`, `registry.py`, `tools/__init__.py`, `agent_tools.py`

- [ ] **Step 1:** 新增导出和注册
- [ ] **Step 2:** 运行测试
- [ ] **Step 3: Commit** — `feat(workflow): register apply_change, reject_change, list_proposed_changes tools`

### Task 22: advance_phase 支持阶段回退（G1）

**Files:**
- Modify: `backend/app/agents/tools/creation/advance_phase.py`

- [ ] **Step 1:** 新增 `direction` 参数
- [ ] **Step 2:** 将 `phase_labels` 定义提前
- [ ] **Step 3:** 添加回退逻辑
- [ ] **Step 4:** 更新 docstring 和返回值
- [ ] **Step 5:** 运行测试
- [ ] **Step 6: Commit** — `feat(workflow): add backward direction to advance_phase for phase rollback`

### Task 23: 更新测试文件

**Files:**
- Modify: `backend/tests/test_advance_phase.py`
- Modify: `backend/tests/test_agent_tools.py`
- Create: `backend/tests/test_change_workflow.py`

- [ ] **Step 1:** 新增回退场景测试
- [ ] **Step 2:** 新增闭环工具注册测试
- [ ] **Step 3:** 创建 `test_change_workflow.py`
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `test(workflow): add phase rollback and change workflow tests`

### Task 24: 工具调用时机 Prerequisites 文档（H1）

**Files:**
- Modify: ~11 个工具文件的 docstring

- [ ] **Step 1:** 逐文件更新 docstring
- [ ] **Step 2: Commit** — `docs(workflow): add Prerequisites section to tool docstrings`

---

## 第 4 批: 一致性检测增强 + 伏笔建议精度 + docstring 统一

### Task 25: consistency_scan 增加 F1-F3（情绪凝固 + 设定匹配 + foreshadowing 类型）

**Files:**
- Modify: `backend/app/agents/tools/perception/consistency_scan.py`

- [ ] **Step 1:** 新增情绪凝固检测（F1）+ 正→负跳跃检测补充
- [ ] **Step 2:** 优化设定引用矛盾检测（F2）
- [ ] **Step 3:** 新增 foreshadowing 检查类型（F3）
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `feat(workflow): add emotion stagnation, foreshadowing checks and optimize setting matching`

### Task 26: suggest_foreshadowing 停用词 + 自适应阈值（J1）

**Files:**
- Modify: `backend/app/agents/tools/assist/suggest_foreshadowing.py`

- [ ] **Step 1:** 新增停用词集合
- [ ] **Step 2:** 区分 jieba/bigram 模式阈值
- [ ] **Step 3:** 更新 docstring
- [ ] **Step 4:** 运行测试
- [ ] **Step 5: Commit** — `refactor(workflow): add stopwords filter and adaptive thresholds for foreshadowing suggestions`

### Task 27: Docstring 中文化统一（L1）

**Files:**
- Modify: `creation/relation.py`, `creation/evolution_plan.py`, `creation/foreshadowing.py`, `creation/timeline_entry.py`, `creation/character.py`, `perception/foreshadowing_check.py`

- [ ] **Step 1:** 逐文件将英文 Args 描述改为中文
- [ ] **Step 2: Commit** — `docs(workflow): standardize tool docstrings to Chinese`

---

## 最终验证

### Task 28: 全量测试 + 重启后端

- [ ] **Step 1:** `docker exec novelagent-backend-1 pytest -v`
- [ ] **Step 2:** `docker compose restart backend`
- [ ] **Step 3:** `docker compose logs backend --tail 20` — 确认无 import 错误
- [ ] **Step 4:** 最终 Commit — `chore(workflow): agent tools optimization - all modules A-L complete (v5)`
