# Agent 工具重构与优化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 29 个 Agent 工具从单一 82KB 文件拆分为独立文件（按功能分组），同时实现方案 A（2 项修正）和方案 B（6 项增强）。

**Architecture:** 按感知/修改/创作辅助/创作四类分组，每个工具独立文件。共享函数提取到 `tools/utils.py`（**以原始 agent_tools.py 实现为准，含参数名**），阶段工具注册提取到 `tools/registry.py`（**模块级常量**）。旧 `agent_tools.py` 保留为兼容层。

**Tech Stack:** Python 3.12, LangChain tools, SQLAlchemy, FastAPI

**Spec:** `docs/superpowers/specs/2025-06-08-agent-tools-refactor-design.md` (v4.2)

**重要原则:** 迁移阶段不做任何功能变更。功能增强在迁移完成后单独实施。

---

## 审核修正摘要

| 原计划 | 修正 | 原因 |
|--------|------|------|
| A1: 实现 create_character | **取消** | 已有完整实现（行 861-918） |
| A2: 实现 writer_block_assist | **取消** | 已有完整实现（行 586-643） |
| utils.py 简化版共享函数 | **必须重写** | `_grade_impact` 阈值+参数名不同、`_get_current_value` 缺少 ID 检查和 3 种 target_type、`_extract_keywords` 逻辑不同 |
| consistency_check 调 LLM | **改为不调 LLM** | Agent 工具只返回结构化数据 |
| _build_state_for_review 归属 | **放入 utils.py** | review_chapter 和 rewrite_chapter 共用 |
| knowledge_search 返回格式 | **保留原始格式** | DB fallback 不加 `"method"` 键 |
| A4 中 `s.title` | **改为 `s.name`** | Subplot 模型字段是 `name` |
| A4 中 `r.character_a.name` | **禁止访问 relationship** | detached ORM 对象访问 lazy-loaded relation 会 `DetachedInstanceError` |
| registry.py 只有函数 | **改为模块级常量** | `agent_graph.py` 直接导入常量 |
| generate_outline 导入路径 | **改为 `app.agents.services.outline_service`** | 原始代码如此，不是 `app.api.outline` |
| AGENT_TOOLS 重复定义 | **只保留一个** | 原始行 2326/2328 重复 |
| Subplot 无 description 字段 | **A4 匹配 `s.name` + `s.current_status`** | Subplot 模型只有 name/characters/current_status 等字段 |
| _build_state_for_review 内部导入 | **保留在函数体内** | SessionLocal/ChapterOutline/DEFAULT_PROMPTS 不能提升为文件级导入 |
| registry.py 依赖链安全 | **无循环（已验证）** | 依赖链 registry→creation→utils→tool_context，终点不依赖 tools/ |
| knowledge_search 直接实例化 KB | **必须用 `_kb()`** | 原始代码用 `kb = _kb()`，不是 `KnowledgeBaseService(project_id)` |
| review_chapter 内部导入不完整 | **补充 `from app.models.chapter import Chapter`** | 行 1465 的 Chapter 导入也在函数体内 |
| generate_chapter_content 描述不准确 | **同时使用 `_kb()` 和 `SessionLocal()`** | 不是"不通过 KB service"，而是双模式 |
| generate_story_seed 内部导入 | **保留在函数体内** | `SessionLocal` 和 `Outline` 在函数体内导入 |

---

## File Structure

### 新建文件

| 文件 | 职责 |
|------|------|
| `backend/app/agents/tools/__init__.py` | 统一导出所有 29 个工具 + 4 个常量 + 3 个内部函数 |
| `backend/app/agents/tools/utils.py` | 共享函数（**以原始 agent_tools.py 实现为准**） |
| `backend/app/agents/tools/registry.py` | 模块级常量 INCUBATION/STRUCTURE/WRITING_TOOLS + AGENT_TOOLS |
| `backend/app/agents/tools/perception/__init__.py` | 感知工具导出（只从同目录导入） |
| `backend/app/agents/tools/perception/knowledge_search.py` | 知识库检索 |
| `backend/app/agents/tools/perception/foreshadowing_check.py` | 伏笔检查 |
| `backend/app/agents/tools/perception/consistency_check.py` | 一致性检查 |
| `backend/app/agents/tools/perception/style_analysis.py` | 风格分析 |
| `backend/app/agents/tools/perception/progress_report.py` | 进度报告 |
| `backend/app/agents/tools/perception/rhythm_analysis.py` | 节奏分析 |
| `backend/app/agents/tools/modification/__init__.py` | 修改工具导出（只从同目录导入） |
| `backend/app/agents/tools/modification/propose_setting_change.py` | 提议设定变更 |
| `backend/app/agents/tools/modification/propose_outline_adjustment.py` | 提议大纲调整 |
| `backend/app/agents/tools/modification/propose_chapter_rewrite.py` | 提议章节重写 |
| `backend/app/agents/tools/assist/__init__.py` | 创作辅助导出（只从同目录导入） |
| `backend/app/agents/tools/assist/writer_block_assist.py` | 写作卡壳辅助 |
| `backend/app/agents/tools/assist/suggest_foreshadowing.py` | 伏笔建议 |
| `backend/app/agents/tools/assist/suggest_plot_twist.py` | 反转建议 |
| `backend/app/agents/tools/assist/expand_world_setting.py` | 扩展世界观 |
| `backend/app/agents/tools/creation/__init__.py` | 创作工具导出（只从同目录导入） |
| `backend/app/agents/tools/creation/world_setting.py` | 创建世界观 |
| `backend/app/agents/tools/creation/character.py` | 创建角色（**保留原始签名**） |
| `backend/app/agents/tools/creation/relation.py` | 创建关系 |
| `backend/app/agents/tools/creation/subplot.py` | 创建子情节 |
| `backend/app/agents/tools/creation/plot_question.py` | 创建问题链 |
| `backend/app/agents/tools/creation/timeline_entry.py` | 创建时间线条目 |
| `backend/app/agents/tools/creation/style_constraints.py` | 创建风格约束 |
| `backend/app/agents/tools/creation/foreshadowing.py` | 创建伏笔 |
| `backend/app/agents/tools/creation/plot_block.py` | 创建情节块 |
| `backend/app/agents/tools/creation/generate_outline.py` | 生成大纲 |
| `backend/app/agents/tools/creation/generate_chapter_content.py` | 生成章节内容 |
| `backend/app/agents/tools/creation/generate_story_seed.py` | 生成故事种子 |
| `backend/app/agents/tools/creation/generate_world_setting_complete.py` | 生成完整世界观 |
| `backend/app/agents/tools/creation/review_chapter.py` | 审核章节 |
| `backend/app/agents/tools/creation/rewrite_chapter.py` | 重写章节 |
| `backend/app/agents/tools/creation/advance_phase.py` | 推进阶段 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/app/agents/agent_tools.py` | 清空，改为从 tools/ 导入的兼容层（含所有 13 工具 + 4 常量 + 3 内部函数重导出） |
| `backend/app/agents/agent_graph.py` | 改为从 tools/ 导入工具列表 |
| `backend/tests/test_agent_tools.py` | 更新导入路径 |

---

## Task 1: 重写 tools/utils.py — 以原始实现为准

**Files:**
- Rewrite: `backend/app/agents/tools/utils.py`

- [ ] **Step 1: 用原始 agent_tools.py 的实现重写 utils.py**

必须包含的函数（**逐字复制原始实现，包括参数名**）：
- `_kb()` — 获取 KnowledgeBaseService（原始行 37-44）
- `_serialize(obj)` — ORM 对象序列化（原始行 47-55，递归处理列表）
- `_get_current_value(kb, target_type, target_id)` — **必须检查 obj.id == target_id，支持 6 种 target_type**（原始行 1627-1659）
- `_extract_keywords(old_value, new_value, description)` — 原始实现（原始行 1659-1675，用 list 不过滤 key）
- `_grade_impact(affected_chapters, target_type, new_value, old_value)` — **必须使用原始参数名和阈值**（原始行 1676-1700，参数名 `affected_chapters`，阈值 <=1章<=2段=minor, <=3章<=5段=moderate）
- `_build_state_for_review(project_id, chapter_number)` — 从 agent_tools.py 行 1270-1385 提取
- **内部导入保留在函数体内**：`_build_state_for_review` 原始代码在函数体内导入了 `SessionLocal`、`ChapterOutline`、`DEFAULT_PROMPTS`。迁移时必须保留在函数体内，不能提升为文件级导入（避免 SQLAlchemy metadata 初始化和循环依赖）

新增的辅助函数（方案 B 增强所需，标注为占位符或简化实现）：
- `_mood_to_tension(mood)` — 情绪标签转张力分值
- `_compare_with_anchor(content, anchor)` — 风格锚点对比
- `_extract_names(text)` — 从文本提取角色名
- `_extract_times(text)` — 从文本提取时间表达
- `_has_conflict(names_a, names_b, name)` — TODO: 实现实际冲突检测逻辑
- `_has_time_conflict(times_a, times_b, time)` — TODO: 实现实际时间冲突检测逻辑

- [ ] **Step 2: 验证函数签名与原始逐字一致**

逐一对比原始 `agent_tools.py` 中 `_grade_impact`, `_get_current_value`, `_extract_keywords`, `_kb`, `_serialize` 的参数名、类型注解和默认行为，确保完全一致。

- [ ] **Step 3: 本地验证导入**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools.utils import _kb, _serialize, _get_current_value, _extract_keywords, _grade_impact, _build_state_for_review; print('utils.py OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/tools/utils.py
git commit -m "refactor(tools): rewrite utils.py with original implementations"
```

---

## Task 2: 重写 tools/registry.py — 模块级常量

**Files:**
- Rewrite: `backend/app/agents/tools/registry.py`

- [ ] **Step 1: 重写 registry.py 为模块级常量**

结构：
```python
"""工具注册表 — 按阶段注册可用工具"""

# 延迟导入，避免循环依赖
from app.agents.tools.perception import (
    knowledge_search, foreshadowing_check, consistency_check,
    style_analysis, progress_report, rhythm_analysis,
)
from app.agents.tools.modification import (
    propose_setting_change, propose_outline_adjustment, propose_chapter_rewrite,
)
from app.agents.tools.assist import (
    writer_block_assist, suggest_foreshadowing, suggest_plot_twist, expand_world_setting,
)
from app.agents.tools.creation import (
    create_world_setting, create_character, create_relation, create_subplot,
    create_plot_question, create_timeline_entry, create_style_constraints,
    create_foreshadowing, create_plot_block,
    generate_outline, generate_chapter_content, generate_story_seed,
    generate_world_setting_complete, review_chapter, rewrite_chapter, advance_phase,
)

INCUBATION_TOOLS = [...]  # 与原始完全一致
STRUCTURE_TOOLS = [...]   # 与原始完全一致
WRITING_TOOLS = [...]     # 与原始完全一致
AGENT_TOOLS = WRITING_TOOLS  # 只一个，不重复
```

工具列表内容必须与原始 `agent_tools.py` 行 2233-2326 **逐项一致**。

**循环依赖安全**：依赖链为 `registry.py` → `creation/__init__.py` → `creation/review_chapter.py` → `app.agents.tools.utils` → `app.agents.tool_context`。`tool_context` 不依赖 `tools/`，因此无循环。前提：各子模块 `__init__.py` 严格遵守"只从同目录导入"原则，不导入 `registry.py` 或 `tools/__init__.py`。

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/registry.py
git commit -m "refactor(tools): rewrite registry.py with module-level constants"
```

---

## Task 3: 迁移感知工具 — perception/（6 个文件）

**Files:**
- Create: `backend/app/agents/tools/perception/__init__.py`
- Rewrite: `backend/app/agents/tools/perception/knowledge_search.py`（删除已有的含 A4 增强版本）
- Create: `backend/app/agents/tools/perception/foreshadowing_check.py`
- Create: `backend/app/agents/tools/perception/consistency_check.py`
- Create: `backend/app/agents/tools/perception/style_analysis.py`
- Create: `backend/app/agents/tools/perception/progress_report.py`
- Create: `backend/app/agents/tools/perception/rhythm_analysis.py`

- [ ] **Step 1: 创建 perception/__init__.py**

只从同目录导入，不依赖 `tools/__init__.py`：
```python
from .knowledge_search import knowledge_search
from .foreshadowing_check import foreshadowing_check
from .consistency_check import consistency_check
from .style_analysis import style_analysis
from .progress_report import progress_report
from .rhythm_analysis import rhythm_analysis
```

- [ ] **Step 2: 重写 knowledge_search.py**

从 `agent_tools.py` 提取 `knowledge_search` 函数**完整实现**（行 55-118）。导入改为 `from app.agents.tools.utils import _kb, _serialize`。**关键**：
- 不包含 A4 增强（A4 在 Task 9 中实现）
- **必须使用 `kb = _kb()`**，与原始代码一致，不能直接 `KnowledgeBaseService(project_id)`
- DB fallback 返回 `{"found": True, "results": filtered}`，**不加 `"method": "keyword"`**
- 语义检索路径返回 `{"found": True, "method": "semantic", "results": results}`（与原始一致）

- [ ] **Step 3: 创建 foreshadowing_check.py**

从 `agent_tools.py` 提取 `foreshadowing_check` 函数**完整实现**（行 120-166）。**不包含 B2 增强**。

- [ ] **Step 4: 创建 consistency_check.py**

从 `agent_tools.py` 提取 `consistency_check` 函数**完整实现**（行 168-205）。**不包含 A3 修复**。

- [ ] **Step 5: 创建 style_analysis.py**

从 `agent_tools.py` 提取 `style_analysis` 函数**完整实现**（行 207-269）。**不包含 B3 增强**。

- [ ] **Step 6: 创建 progress_report.py**

从 `agent_tools.py` 提取 `progress_report` 函数**完整实现**（行 271-309）。**不包含 B6 增强**。

- [ ] **Step 7: 创建 rhythm_analysis.py**

从 `agent_tools.py` 提取 `rhythm_analysis` 函数**完整实现**（行 311-380）。**不包含 B4 增强**。

- [ ] **Step 8: Commit**

```bash
git add backend/app/agents/tools/perception/
git commit -m "refactor(tools): migrate perception tools (faithful copy)"
```

---

## Task 4: 迁移修改工具 — modification/（3 个文件）

**Files:**
- Create: `backend/app/agents/tools/modification/__init__.py`
- Create: `backend/app/agents/tools/modification/propose_setting_change.py`
- Create: `backend/app/agents/tools/modification/propose_outline_adjustment.py`
- Create: `backend/app/agents/tools/modification/propose_chapter_rewrite.py`

- [ ] **Step 1: 创建 modification/__init__.py**

只从同目录导入。

- [ ] **Step 2: 创建 propose_setting_change.py**

从 `agent_tools.py` 提取 `propose_setting_change` 完整实现（行 381-446）。导入 `_kb`, `_serialize`, `_get_current_value`, `_extract_keywords`, `_grade_impact` 均来自 `app.agents.tools.utils`。**不包含 B5 增强**。

- [ ] **Step 3: 创建 propose_outline_adjustment.py**

从 `agent_tools.py` 提取完整实现（行 447-535）。

- [ ] **Step 4: 创建 propose_chapter_rewrite.py**

从 `agent_tools.py` 提取完整实现（行 536-585）。

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/tools/modification/
git commit -m "refactor(tools): migrate modification tools (faithful copy)"
```

---

## Task 5: 迁移创作辅助工具 — assist/（4 个文件）

**Files:**
- Create: `backend/app/agents/tools/assist/__init__.py`
- Create: `backend/app/agents/tools/assist/writer_block_assist.py`
- Create: `backend/app/agents/tools/assist/suggest_foreshadowing.py`
- Create: `backend/app/agents/tools/assist/suggest_plot_twist.py`
- Create: `backend/app/agents/tools/assist/expand_world_setting.py`

- [ ] **Step 1: 创建 assist/__init__.py**

只从同目录导入。

- [ ] **Step 2: 创建 writer_block_assist.py**

从 `agent_tools.py` 提取完整实现（行 586-643）。**保留原始实现，不做修改**。

- [ ] **Step 3: 创建 suggest_foreshadowing.py**

从 `agent_tools.py` 提取完整实现（行 644-686）。

- [ ] **Step 4: 创建 suggest_plot_twist.py**

从 `agent_tools.py` 提取完整实现（行 687-742）。

- [ ] **Step 5: 创建 expand_world_setting.py**

从 `agent_tools.py` 提取完整实现（行 743-805）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/tools/assist/
git commit -m "refactor(tools): migrate assist tools (faithful copy)"
```

---

## Task 6: 迁移创作工具 — creation/（16 个文件）

**Files:**
- Create: `backend/app/agents/tools/creation/__init__.py`
- Create: `backend/app/agents/tools/creation/world_setting.py` （行 806-860）
- Create: `backend/app/agents/tools/creation/character.py` （行 861-918，**保留原始签名**）
- Create: `backend/app/agents/tools/creation/relation.py` （行 920-963）
- Create: `backend/app/agents/tools/creation/subplot.py` （行 964-1010）
- Create: `backend/app/agents/tools/creation/plot_question.py` （行 1011-1043）
- Create: `backend/app/agents/tools/creation/timeline_entry.py` （行 1044-1091）
- Create: `backend/app/agents/tools/creation/style_constraints.py` （行 1092-1152）
- Create: `backend/app/agents/tools/creation/foreshadowing.py` （行 1153-1200）
- Create: `backend/app/agents/tools/creation/plot_block.py` （行 1201-1269）
- Create: `backend/app/agents/tools/creation/generate_outline.py` （行 1705-1794）
- Create: `backend/app/agents/tools/creation/generate_chapter_content.py` （行 1795-1948）
- Create: `backend/app/agents/tools/creation/generate_story_seed.py` （行 1949-2017）
- Create: `backend/app/agents/tools/creation/generate_world_setting_complete.py` （行 2018-2117）
- Create: `backend/app/agents/tools/creation/review_chapter.py` （行 1386-1494）
- Create: `backend/app/agents/tools/creation/rewrite_chapter.py` （行 1494-1620）
- Create: `backend/app/agents/tools/creation/advance_phase.py` （行 2118-2232）

- [ ] **Step 1: 创建 creation/__init__.py**

只从同目录导入。

- [ ] **Step 2-17: 逐个创建工具文件**

每个文件包含：
- 文件级 docstring
- 必要的 import（从 `app.agents.tools.utils` 导入共享函数）
- `@tool` 装饰器 + **原始完整函数签名和 docstring**
- **原始完整函数体**

关键注意事项：
- `character.py`: **保留原始签名**（`role` 必填，`catchphrase`/`habit_action`/`growth_arc` 等字段名与 Character 模型对齐）
- `review_chapter.py` 和 `rewrite_chapter.py`: 导入 `_build_state_for_review` 从 `app.agents.tools.utils`
- `review_chapter.py`: 函数体内有 `from app.database import SessionLocal`（两处）、`from app.models.outline import ChapterOutline`、`from app.models.chapter import Chapter`，全部保留在函数体内
- `review_chapter.py`: 导入 `_build_review_messages`, `parse_review_result`, `check_review_passed` 从 `app.agents.review_utils`
- `rewrite_chapter.py`: 导入 `_build_rewrite_messages`, `clean_chapter_content` 从 `app.agents.rewrite_utils`
- `generate_chapter_content.py`: 同时使用 `kb = _kb()`（伏笔 CRUD）和 `SessionLocal()`（章节/时间线 CRUD），双模式
- `generate_outline.py`: 导入 `update_outline` 从 **`app.agents.services.outline_service`**（不是 `app.api.outline`）
- `generate_story_seed.py`: 函数体内有 `from app.database import SessionLocal` 和 `from app.models.outline import Outline`，保留在函数体内
- `advance_phase.py`: 内部导入 `WorkflowState` 和 `Phase`（与原始一致）
- 所有工具文件：原始代码中在函数体内的导入（如 `from app.database import SessionLocal`、`from app.models.outline import ChapterOutline`、`from app.agents.prompts import DEFAULT_PROMPTS`、`from app.agents.constants import Phase`、`from app.models.workflow_state import WorkflowState`）**必须保留在函数体内**，不能提升为文件级导入

- [ ] **Step 18: Commit**

```bash
git add backend/app/agents/tools/creation/
git commit -m "refactor(tools): migrate creation tools (faithful copy)"
```

---

## Task 7: 创建 tools/__init__.py — 统一导出 + 兼容层

**Files:**
- Create: `backend/app/agents/tools/__init__.py`
- Modify: `backend/app/agents/agent_tools.py` → 兼容层
- Modify: `backend/app/agents/agent_graph.py` → 改导入路径
- Modify: `backend/tests/test_agent_tools.py` → 更新导入路径

- [ ] **Step 1: 创建 __init__.py**

完整导出清单：
```python
"""Agent 工具统一导出"""

# 感知工具
from app.agents.tools.perception import (
    knowledge_search, foreshadowing_check, consistency_check,
    style_analysis, progress_report, rhythm_analysis,
)
# 修改工具
from app.agents.tools.modification import (
    propose_setting_change, propose_outline_adjustment, propose_chapter_rewrite,
)
# 创作辅助
from app.agents.tools.assist import (
    writer_block_assist, suggest_foreshadowing, suggest_plot_twist, expand_world_setting,
)
# 创作工具
from app.agents.tools.creation import (
    create_world_setting, create_character, create_relation, create_subplot,
    create_plot_question, create_timeline_entry, create_style_constraints,
    create_foreshadowing, create_plot_block,
    generate_outline, generate_chapter_content, generate_story_seed,
    generate_world_setting_complete, review_chapter, rewrite_chapter, advance_phase,
)
# 阶段工具列表
from app.agents.tools.registry import (
    INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS, AGENT_TOOLS,
)
# 内部函数（测试兼容）
from app.agents.tools.utils import _kb, _extract_keywords, _grade_impact
```

- [ ] **Step 2: 更新 agent_tools.py 为兼容层**

```python
"""向后兼容层 — 所有导入已迁移到 app.agents.tools"""
from app.agents.tools import *  # noqa: F401,F403
from app.agents.tools import (
    INCUBATION_TOOLS,
    STRUCTURE_TOOLS,
    WRITING_TOOLS,
    AGENT_TOOLS,
    _kb,
    _extract_keywords,
    _grade_impact,
)
```

- [ ] **Step 3: 更新 agent_graph.py**

将 `from app.agents.agent_tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS` 改为 `from app.agents.tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS`。

- [ ] **Step 4: 更新 test_agent_tools.py**

将所有 `from app.agents.agent_tools import ...` 改为 `from app.agents.tools import ...`。

- [ ] **Step 5: 本地验证导入**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools import AGENT_TOOLS; print(f'{len(AGENT_TOOLS)} tools loaded')"
```
Expected: `28 tools loaded`（WRITING_TOOLS 有 28 个条目，29 个工具函数中 generate_story_seed 不在 WRITING_TOOLS 中）

- [ ] **Step 6: 本地验证旧路径兼容**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.agent_tools import AGENT_TOOLS, _kb; print('Compat OK')"
```
Expected: `Compat OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/agents/tools/__init__.py backend/app/agents/agent_tools.py backend/app/agents/agent_graph.py backend/tests/test_agent_tools.py
git commit -m "refactor(tools): wire up unified exports, compat layer, and test updates"
```

---

## Task 8: [A3] 修复 consistency_check — 增加章节内容实际对比

**Files:**
- Modify: `backend/app/agents/tools/perception/consistency_check.py`

- [ ] **Step 1: 重写 consistency_check 函数**

在保留原有知识库约束返回的基础上，新增章节内容交叉分析：
1. 读取两章实际内容（`kb.get_chapter_by_number()`）
2. 用 `_extract_names()` 和 `_extract_times()` 提取角色名和时间表达
3. 返回交叉数据（两章共同出现的角色/时间点）
4. 保留原有 `aspect` 参数和知识库约束返回（向后兼容）
5. 不调用 LLM（由 Agent 判断矛盾）

- [ ] **Step 2: 本地验证**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools.perception.consistency_check import consistency_check; print(f'OK: {consistency_check.name}')"
```
Expected: `OK: consistency_check`

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/consistency_check.py
git commit -m "fix(tools): consistency_check now reads actual chapter content (A3)"
```

---

## Task 9: [A4] 扩展 knowledge_search 关键词匹配覆盖

**Files:**
- Modify: `backend/app/agents/tools/perception/knowledge_search.py`

- [ ] **Step 1: 在 DB fallback 路径中添加子情节、关系、风格快照搜索**

新增（在 `filtered` 构建之前）：
- 子情节搜索：复用已获取的 `subplots` 数据（避免重复查询），匹配 `s.name` 和 `s.current_status`（Subplot 模型无 `description` 字段，不应使用）
- 关系搜索：遍历 `kb.get_relations()`，只访问 Column 属性 `r.character_a_id`、`r.character_b_id`、`r.relation_type`、`r.current_status`。如需角色名，先查 `kb.get_characters()` 构建 `{c.id: c.name for c in chars}` 映射
- 风格快照搜索：复用已获取的 `snapshots` 数据（避免重复查询），按章节号匹配

- [ ] **Step 2: 本地验证**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools.perception.knowledge_search import knowledge_search; print(f'OK: {knowledge_search.name}')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/knowledge_search.py
git commit -m "feat(tools): extend knowledge_search keyword matching to subplots/relations/snapshots (A4)"
```

---

## Task 10: [B2] foreshadowing_check 增强

**Files:**
- Modify: `backend/app/agents/tools/perception/foreshadowing_check.py`

- [ ] **Step 1: 添加健康度评分计算**

评分规则：基础分 100，超期伏笔每个扣 15 分（上限 60），待回收超 3 个每个扣 5 分（上限 20），最低 0。

- [ ] **Step 2: 添加超期伏笔回收建议**

为每个超期伏笔生成 `suggested_chapter` 和 `suggested_method`。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/foreshadowing_check.py
git commit -m "feat(tools): add health score and recovery suggestions to foreshadowing_check (B2)"
```

---

## Task 11: [B3] style_analysis 增强

**Files:**
- Modify: `backend/app/agents/tools/perception/style_analysis.py`

- [ ] **Step 1: 添加情感词汇密度统计**

定义三类情感词表（紧张/悲伤/温暖），计算每千字出现次数。

- [ ] **Step 2: 添加修辞手法统计**

统计比喻、夸张、排比频次。

- [ ] **Step 3: 添加风格锚点对比**

如果 `style_constraints.style_anchor` 存在，调用 `_compare_with_anchor()` 进行对比。

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/tools/perception/style_analysis.py
git commit -m "feat(tools): add emotion density, rhetoric stats, anchor comparison to style_analysis (B3)"
```

---

## Task 12: [B6] progress_report 增强

**Files:**
- Modify: `backend/app/agents/tools/perception/progress_report.py`

- [ ] **Step 1: 添加基于历史写作速度的完稿时间预估**

取最近 3 个时间线条目的 `created_at` 计算写作速度，用剩余章数除以速度得到预估天数。

- [ ] **Step 2: 添加里程碑提醒**

检测 10%/50%/90% 进度节点。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/progress_report.py
git commit -m "feat(tools): add completion estimate and milestones to progress_report (B6)"
```

---

## Task 13: [B4] rhythm_analysis 增强

**Files:**
- Modify: `backend/app/agents/tools/perception/rhythm_analysis.py`

- [ ] **Step 1: 添加高潮/低谷分布数据**

tension_score >= 4 为 peak，<= 2 为 valley。

- [ ] **Step 2: 添加情节块预期节奏对比**

用 `_mood_to_tension()` 转换，偏差 > 1 时生成警告。

- [ ] **Step 3: Commit**

```bash
git add backend/app/agents/tools/perception/rhythm_analysis.py
git commit -m "feat(tools): add peaks/valleys and block deviation to rhythm_analysis (B4)"
```

---

## Task 14: [B5] propose_setting_change 增强

**Files:**
- Modify: `backend/app/agents/tools/modification/propose_setting_change.py`

- [ ] **Step 1: 替换关键词匹配为语义检索**

用 `RetrievalService.search()` 替代 `kb.search_chapters_for_references()`。索引不可用时降级回关键词匹配。

- [ ] **Step 2: Commit**

```bash
git add backend/app/agents/tools/modification/propose_setting_change.py
git commit -m "feat(tools): use semantic search for impact assessment in propose_setting_change (B5)"
```

---

## Task 15: 最终验证

- [ ] **Step 1: 本地验证所有工具可导入**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools import AGENT_TOOLS; print(f'{len(AGENT_TOOLS)} tools')"
```
Expected: `28 tools`

- [ ] **Step 2: 本地验证阶段工具列表**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS; print(f'I:{len(INCUBATION_TOOLS)} S:{len(STRUCTURE_TOOLS)} W:{len(WRITING_TOOLS)}')"
```
Expected: `I:12 S:17 W:28`

- [ ] **Step 3: 本地验证旧路径兼容**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.agent_tools import AGENT_TOOLS, _kb, _extract_keywords, _grade_impact; print('Compat OK')"
```
Expected: `Compat OK`

- [ ] **Step 4: 本地验证 agent_graph 可创建**

```bash
cd /Users/biner/Dev/novelagent/backend && PYTHONPATH=. python -c "from app.agents.agent_graph import create_agent_graph; print('agent_graph OK')"
```
Expected: `agent_graph OK`

- [ ] **Step 5: Docker 内运行测试（如容器可用）**

```bash
docker exec novelagent-backend-1 pytest tests/test_agent_tools.py -v
```
Expected: PASS

- [ ] **Step 6: 最终 Commit**

```bash
git add -A backend/
git commit -m "refactor(tools): complete agent tools restructure with A+B optimizations"
```

---

## Self-Review

### Spec Coverage Check

| Spec 需求 | 对应 Task | 状态 |
|-----------|----------|------|
| ~~A1: 实现 create_character~~ | 取消 | ✅ 已有实现 |
| ~~A2: 实现 writer_block_assist~~ | 取消 | ✅ 已有实现 |
| A3: 修复 consistency_check | Task 8 | ✅ |
| A4: 关键词匹配扩展 | Task 9 | ✅ |
| B2: foreshadowing_check 增强 | Task 10 | ✅ |
| B3: style_analysis 增强 | Task 11 | ✅ |
| B4: rhythm_analysis 增强 | Task 13 | ✅ |
| B5: propose_setting_change 增强 | Task 14 | ✅ |
| B6: progress_report 增强 | Task 12 | ✅ |
| 目录拆分 29 个工具 | Task 3-6 | ✅ |
| 向后兼容 | Task 7 | ✅ |
| 验证测试 | Task 15 | ✅ |

### Placeholder Scan

无 TBD/TODO（占位符函数 `_has_conflict`/`_has_time_conflict` 在 utils.py 中标注 TODO）。所有步骤包含具体实现描述或验证命令。

### Type Consistency

- `create_character` 保留原始签名（`role` 必填，字段名与 Character 模型对齐）
- `_grade_impact` 使用原始参数名 `affected_chapters` 和原始阈值（<=1章<=2段=minor, <=3章<=5段=moderate）
- `_get_current_value` 检查 `obj.id == target_id`，支持 6 种 target_type
- `_extract_keywords` 使用原始实现（list，不过滤 key）
- `_build_state_for_review` 从 `tools/utils.py` 导入，`review_chapter.py` 和 `rewrite_chapter.py` 共用
- `generate_outline` 导入 `update_outline` 从 `app.agents.services.outline_service`
- `registry.py` 导出模块级常量，与原始导出方式一致
- `AGENT_TOOLS` 只定义一次
- A4 中 Subplot 匹配 `s.name` + `s.current_status`（无 `description` 字段）
- `_build_state_for_review` 内部导入保留在函数体内
- 所有工具文件中函数体内的导入保留在函数体内
- A4 中 Subplot 用 `s.name`，Relation 只访问 Column 属性
- `knowledge_search` 使用 `kb = _kb()` 而非直接实例化 `KnowledgeBaseService(project_id)`
- `generate_chapter_content` 双模式：`kb = _kb()` 用于伏笔 CRUD + `SessionLocal()` 用于章节/时间线 CRUD
- `review_chapter` 函数体内有 `SessionLocal`（两处）、`ChapterOutline`、`Chapter`，全部保留在函数体内
- `generate_story_seed` 函数体内有 `SessionLocal` 和 `Outline`，保留在函数体内
