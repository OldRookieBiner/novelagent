# Agent 工具重构与优化规范

**项目**: NovelAgent  
**版本**: v0.8.11  
**日期**: 2025-06-08  
**状态**: 审核通过（v4.1 — 第三轮审查修正版）

---

## 1. 背景与目标

### 1.1 当前问题

- `agent_tools.py` 体积已达 82KB、29 个工具混在一起
- 难以阅读、维护、单独测试
- 部分工具功能不完整（consistency_check 只返回约束，不做实际对比）
- 检索能力有限，影响评估精度不足

### 1.2 优化目标

1. 将 29 个工具拆分为独立文件，按功能分组
2. 修复核心缺陷（方案 A：2 项有效修复）
3. 增强工具能力（方案 B：6 项）
4. 保持向后兼容，平滑迁移

---

## 2. 目录结构

```
backend/app/agents/
├── tools/
│   ├── __init__.py              # 统一导出所有工具 + 阶段列表 + 兼容导出
│   ├── utils.py                 # 共享工具函数（含 _build_state_for_review）
│   ├── registry.py              # 模块级常量 INCUBATION/STRUCTURE/WRITING_TOOLS + AGENT_TOOLS
│   ├── perception/              # 感知工具（6个）
│   │   ├── __init__.py
│   │   ├── knowledge_search.py
│   │   ├── foreshadowing_check.py
│   │   ├── consistency_check.py
│   │   ├── style_analysis.py
│   │   ├── progress_report.py
│   │   └── rhythm_analysis.py
│   ├── modification/            # 修改工具（3个）
│   │   ├── __init__.py
│   │   ├── propose_setting_change.py
│   │   ├── propose_outline_adjustment.py
│   │   └── propose_chapter_rewrite.py
│   ├── assist/                  # 创作辅助（4个）
│   │   ├── __init__.py
│   │   ├── writer_block_assist.py
│   │   ├── suggest_foreshadowing.py
│   │   ├── suggest_plot_twist.py
│   │   └── expand_world_setting.py
│   └── creation/                # 创作工具（16个）
│       ├── __init__.py
│       ├── world_setting.py
│       ├── character.py
│       ├── relation.py
│       ├── subplot.py
│       ├── plot_question.py
│       ├── timeline_entry.py
│       ├── style_constraints.py
│       ├── foreshadowing.py
│       ├── plot_block.py
│       ├── generate_outline.py
│       ├── generate_chapter_content.py
│       ├── generate_story_seed.py
│       ├── generate_world_setting_complete.py
│       ├── review_chapter.py
│       ├── rewrite_chapter.py
│       └── advance_phase.py
└── agent_tools.py               # 旧文件 → 兼容层 alias
```

---

## 3. 审核修正记录

### 3.1 ~~A1: 实现 create_character~~ → 已实现，无需修改

**审核发现**: `create_character` 在 `agent_tools.py` 中已有完整实现（行 861-918），签名与 Character 模型完全匹配。

**当前正确签名**:
```python
async def create_character(
    name: str,
    role: str,              # 必填！与 Character.role 一致
    personality: str = "",
    catchphrase: str = "",   # 不是 speech_style/dialogue_samples
    habit_action: str = "",
    deep_fear: str = "",
    core_motivation: str = "",
    growth_arc: str = "",    # 不是 character_arc
    appearance: str = "",
    backstory: str = "",
    signature_item: str = "",
) -> dict:
```

**决策**: 迁移时保留原始实现，不做修改。

### 3.2 ~~A2: 实现 writer_block_assist~~ → 已实现，改为增强

**审核发现**: `writer_block_assist` 在 `agent_tools.py` 中已有实现（行 586-643），基于超期伏笔、待解问题和情节块提供建议。实现是合理的。

**决策**: 迁移时保留原始实现。原有的 A2 任务改为"增强 writer_block_assist"（增加更多建议类型），降为方案 B 级别。但考虑到当前实现已经满足基本需求，本轮不修改。

### 3.3 共享函数一致性（严重问题）

**审核发现**: `tools/utils.py` 中已创建的共享函数与 `agent_tools.py` 原始实现存在严重不一致：

| 函数 | 问题 | 严重度 |
|------|------|--------|
| `_grade_impact` | 阈值不同：原始 `(<=1章,<=2段)=minor, (<=3章,<=5段)=moderate`，utils.py `(<=2章,<=3段)=minor, (<=5章,<=10段)=moderate` | 🔴 高 |
| `_grade_impact` | 参数名不同：原始 `affected_chapters`，utils.py `affected` | 🔴 高 |
| `_get_current_value` | 原始检查 `obj.id == target_id`，utils.py 不检查 ID | 🔴 高 |
| `_get_current_value` | 原始支持 6 种 target_type（world_setting/character/foreshadowing/style/outline/relation），utils.py 只支持 3 种 | 🔴 高 |
| `_extract_keywords` | 原始用 list 不过滤 key，utils.py 用 set 且只看 4 个 key | 🟠 中 |

**决策**: 迁移时**必须使用原始 `agent_tools.py` 中的实现**，逐字复制函数签名和函数体。`tools/utils.py` 需要重写。

### 3.4 `_build_state_for_review` 归属与内部导入

**审核发现**: `review_chapter` 和 `rewrite_chapter` 共用的内部函数 `_build_state_for_review`（行 1270-1385）定义在 `agent_tools.py` 中。它依赖 `KnowledgeBaseService`、`SessionLocal`、`_serialize`。

**内部导入约束**（v4.1 新增）：原始代码中 `_build_state_for_review` 在函数体内导入了 `from app.database import SessionLocal`、`from app.models.outline import ChapterOutline`、`from app.agents.prompts import DEFAULT_PROMPTS`。这些导入在迁移到 `tools/utils.py` 时**必须保留在函数体内**，不能提升为文件级导入。原因：`app.models.outline` 和 `app.agents.prompts` 可能触发 SQLAlchemy metadata 初始化，提升为文件级导入会在模块加载时产生不必要的 DB 连接尝试或循环依赖。

**决策**: 将 `_build_state_for_review` 放入 `tools/utils.py`，所有函数体内导入保留在函数体内。

### 3.5 测试文件更新

**审核发现**: `tests/test_agent_tools.py` 直接从 `app.agents.agent_tools` 导入：
- 13 个工具函数（knowledge_search, foreshadowing_check, ...）
- 4 个常量（AGENT_TOOLS, INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS）
- 2 个内部函数（_extract_keywords, _grade_impact）
- 1 个延迟导入（_kb，在 test_kb_raises_without_project_id 中）

**决策**: 
1. `agent_tools.py` 兼容层需要重新导出所有上述名称
2. `tools/__init__.py` 需要导出所有 29 个工具 + 4 个常量 + 3 个内部函数（_kb, _extract_keywords, _grade_impact）
3. 迁移后更新测试文件中的导入路径（从 `app.agents.agent_tools` 改为 `app.agents.tools`）

### 3.6 `knowledge_search` 返回格式（v4.0 新增）

**审核发现**: 原始 `agent_tools.py` 中 `knowledge_search` 的 DB fallback 返回 `{"found": True, "results": filtered}`（无 `"method"` 键）。已创建的 `tools/perception/knowledge_search.py` 返回 `{"found": True, "method": "keyword", "results": filtered}`，多出了 `"method"` 键。

**决策**: 迁移时必须保留原始返回格式。`"method"` 键仅在语义检索路径中存在（原始代码已有），DB fallback 路径不应添加。

### 3.7 A4 设计中的 Subplot 字段名（v4.0 新增，v4.1 修正）

**审核发现**: A4 设计中描述"匹配 `title` 和 `description`"，但 Subplot 模型字段是 `name`（不是 `title`），且**Subplot 模型没有 `description` 字段**。Subplot 的 Column 属性为：`id`、`project_id`、`name`、`characters`（JSON）、`current_status`、`raised_in_chapter`、`planned_intersection_chapter`、`expected_resolution_chapter`、`created_at`、`updated_at`。

**决策**: A4 实现中搜索子情节时，匹配 `s.name` 和 `s.current_status`（这两个字段有搜索价值），不使用不存在的 `description` 字段。

### 3.8 A4 设计中的 Relation 访问安全（v4.0 新增）

**审核发现**: A4 设计中描述"匹配角色名和关系状态"，涉及 `r.character_a.name`。但 Relation 的 `character_a`/`character_b` 是 lazy-loaded relationship，KB service 返回的 ORM 对象在 session 关闭后为 detached 状态，访问会 `DetachedInstanceError`。

**决策**: A4 实现中只能访问 Column 属性（`r.character_a_id`、`r.character_b_id`、`r.relation_type`、`r.current_status`），不能访问 relationship 属性。如需角色名，需额外查询 `kb.get_characters()` 并按 ID 映射。

### 3.9 `registry.py` 导出方式（v4.0 新增）

**审核发现**: 原始 `agent_tools.py` 在模块级定义 `INCUBATION_TOOLS`、`STRUCTURE_TOOLS`、`WRITING_TOOLS`、`AGENT_TOOLS` 常量。`agent_graph.py` 直接 `from app.agents.agent_tools import INCUBATION_TOOLS, STRUCTURE_TOOLS, WRITING_TOOLS`。当前 `registry.py` 只有一个 `get_tools_by_phase()` 函数，没有模块级常量。

**决策**: `registry.py` 必须在模块级定义 `INCUBATION_TOOLS`、`STRUCTURE_TOOLS`、`WRITING_TOOLS`、`AGENT_TOOLS` 常量，与原始导出方式一致。使用延迟导入（在常量定义处导入工具函数）避免循环依赖。

**循环依赖安全**（v4.1 新增）：依赖链为 `registry.py` → `creation/__init__.py` → `creation/review_chapter.py` → `app.agents.tools.utils` → `app.agents.tool_context`。`tool_context` 不依赖 `tools/`，因此无循环。前提：各子模块 `__init__.py` 严格遵守"只从同目录导入"原则，不导入 `registry.py` 或 `tools/__init__.py`。

### 3.10 `generate_outline` 导入路径（v4.0 新增）

**审核发现**: 原始 `agent_tools.py` 中 `generate_outline` 的导入为 `from app.agents.services.outline_service import update_outline`，不是 `from app.api.outline import update_outline`。

**决策**: 迁移时必须使用原始导入路径 `app.agents.services.outline_service`。

### 3.11 原始 `AGENT_TOOLS` 重复定义（v4.0 新增）

**审核发现**: 原始 `agent_tools.py` 行 2326 和 2328 都有 `AGENT_TOOLS = WRITING_TOOLS`，重复赋值。

**决策**: 迁移时只保留一个 `AGENT_TOOLS = WRITING_TOOLS`。

---


### 3.12 `knowledge_search` 中 `_kb()` vs 直接实例化（v4.2 新增）

**审核发现**: 原始 `agent_tools.py` 中 `knowledge_search` 使用 `kb = _kb()`（行 79）获取 KnowledgeBaseService 实例。已创建的 `tools/perception/knowledge_search.py` 直接使用 `KnowledgeBaseService(project_id)`，跳过了 `_kb()` 辅助函数。这是功能性变更，违反忠实迁移原则。

**决策**: 迁移时必须使用 `kb = _kb()`，与原始代码一致。

### 3.13 `review_chapter` 内部导入完整性（v4.2 新增）

**审核发现**: `review_chapter` 在函数体内有多处内部导入：
- 行 1416-1417: `from app.database import SessionLocal` + `from app.models.outline import ChapterOutline`（读取大纲）
- 行 1465: `from app.models.chapter import Chapter`（保存审核结果）
- `SessionLocal` 在函数体内使用了两次（读大纲 + 保存结果）

这些都必须保留在函数体内，不能提升为文件级导入。

### 3.14 `generate_chapter_content` 双模式使用（v4.2 新增）

**审核发现**: Plan Task 6 描述"直接使用 `SessionLocal()`，不通过 KB service"，这是不准确的。原始 `generate_chapter_content` 同时使用两种模式：
- `kb = _kb()` — 用于创建/回收伏笔（行 1998 的 `kb.create_foreshadowing()` 和 `kb.update_foreshadowing()`）
- `SessionLocal()` — 用于章节 CRUD 和时间线条目创建（因为需要事务控制）

**决策**: 迁移时保留原始双模式使用，不做任何简化。

### 3.15 `generate_story_seed` 内部导入（v4.2 新增）

**审核发现**: `generate_story_seed` 在函数体内导入 `from app.database import SessionLocal` 和 `from app.models.outline import Outline`（行 1975-1976）。这些必须保留在函数体内。

## 4. 方案 A：快速修复（2 项有效）

### ~~A1: 实现 create_character~~ → 取消（已实现）

见 3.1 节。

### ~~A2: 实现 writer_block_assist~~ → 取消（已实现）

见 3.2 节。

### A3: 修复 `consistency_check` — 增加章节内容实际对比

**当前状态**: 只返回知识库约束，未做章节内容实际对比  
**目标文件**: `perception/consistency_check.py`  
**设计决策**: 不在工具内调用 LLM。改为：
1. 读取两章实际内容（通过 `kb.get_chapter_by_number()`）
2. 用 `_extract_names()` 和 `_extract_times()` 提取角色名和时间表达
3. 交叉对比：找出两章共同出现的角色/时间点
4. 返回交叉数据 + 知识库约束，由 Agent 判断是否有矛盾
5. 保留原有 `aspect` 参数和知识库约束返回（向后兼容）

### A4: 扩展 `knowledge_search` 关键词匹配覆盖

**当前状态**: DB fallback 路径只覆盖部分数据类型  
**目标文件**: `perception/knowledge_search.py`  
**设计决策**: 在 DB fallback 路径中新增子情节、关系、风格快照的搜索。  
**关键约束**（见 3.7、3.8）：
- Subplot 搜索匹配 `s.name` 和 `s.current_status`（Subplot 模型无 `description` 字段）
- Relation 只访问 Column 属性（`r.character_a_id`、`r.character_b_id`、`r.relation_type`、`r.current_status`），不访问 `r.character_a`/`r.character_b` relationship
- 如需角色名，先查 `kb.get_characters()` 构建 ID→name 映射，再用 `r.character_a_id` 查找
- 复用 DB fallback 已获取的 subplots 数据，避免重复查询

---

## 5. 方案 B：功能增强（6 项）

### B2: `foreshadowing_check` 增强

**目标**: 健康度评分 + 回收建议  
**设计决策**: 健康度评分算法：基础分 100，超期伏笔每个扣 15 分（上限 60），待回收超 3 个每个扣 5 分（上限 20），最低 0。回收建议根据伏笔等级（hint/其他）推荐不同回收方式。

### B3: `style_analysis` 增强

**目标**: 情感词汇密度 + 修辞统计 + 锚点对比  
**设计决策**: 情感词表定义三类（紧张/悲伤/温暖），各含 5 个典型词。修辞统计三类（比喻/夸张/排比）。锚点对比复用 `tools/utils.py` 的 `_compare_with_anchor()`。

### B4: `rhythm_analysis` 增强

**目标**: 高潮/低谷分布 + 情节块预期对比  
**设计决策**: tension_score >= 4 为 peak，<= 2 为 valley。情节块对比用 `_mood_to_tension()` 转换，偏差 > 1 时生成警告。

### B5: `propose_setting_change` 增强

**目标**: 语义检索影响评估  
**设计决策**: 用 `RetrievalService.search()` 替代 `kb.search_chapters_for_references()`。索引不可用时降级回关键词匹配。语义检索结果按相关性排序，取前 5 个。

### B6: `progress_report` 增强

**目标**: 完稿时间预估 + 里程碑提醒  
**设计决策**: 取最近 3 个时间线条目的 `created_at` 计算写作速度。里程碑检测 10%/50%/90% 节点。

---

## 6. 迁移原则

1. **忠实迁移**：每个工具的函数签名、docstring、函数体必须与原始 `agent_tools.py` 逐字一致，不做任何功能变更
2. **返回格式不变**：迁移时保留原始返回格式，不添加新字段（如 `"method": "keyword"`）
3. **功能优化独立**：方案 A/B 的功能增强在迁移完成后单独实施，不在迁移过程中混入
4. **共享函数以原始实现为准**：`_grade_impact`、`_get_current_value`、`_extract_keywords` 等函数必须使用原始 `agent_tools.py` 中的实现，包括参数名
5. **内部导入保留在函数体内**：原始代码中在函数体内导入的模块（如 `SessionLocal`、`ChapterOutline`、`DEFAULT_PROMPTS`、`WorkflowState`、`Phase`），迁移时必须保留在函数体内，不能提升为文件级导入
6. **每步验证**：每完成一个 Phase，验证所有导入路径正确
7. **兼容层完整**：`agent_tools.py` 兼容层需重新导出所有公开名称（包括 `_kb`、`_extract_keywords`、`_grade_impact`），确保测试文件无需立即修改
8. **ORM 对象安全**：KB service 返回的 ORM 对象在 session 关闭后为 detached 状态，只能访问 Column 属性，不能访问 lazy-loaded relationship 属性
9. **子模块 __init__.py 隔离**：各子模块 `__init__.py` 只从同目录导入，不依赖 `tools/__init__.py` 或 `registry.py`，避免循环导入

---

## 7. 验收标准

1. 所有 29 个工具可正常导入
2. 阶段切换工具列表正确（INCUBATION/STRUCTURE/WRITING/REVISION）
3. 旧导入路径 `from app.agents.agent_tools import ...` 仍可用（含 13 个工具 + 4 个常量 + 3 个内部函数）
4. `tests/test_agent_tools.py` 更新导入路径后全部通过
5. `agent_graph.py` 可正常创建 Agent
6. 方案 A3/A4 优化功能可用且不引入 `DetachedInstanceError` 或 `AttributeError`
7. 方案 B2/B3/B4/B5/B6 优化功能可用

---

**文档版本**: 4.2（第四轮审查修正版）  
**编写日期**: 2025-06-08
