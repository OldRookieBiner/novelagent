# Agent 工具体系全面优化 Spec（v5.1 深度验证终版）

## 背景

NovelAgent v0.8.11 的 Agent 工具体系共 29 个工具（感知 8 + 创作 18 + 修改 3 + 辅助 4）。
本 spec 基于对全部源码文件的逐行独立审查，覆盖工具签名、docstring、Store 层接口、ORM 模型字段、
缓存机制、Hook 链、上下文策略、注册表递进关系。经过三轮审查确认。

**审查范围:** 29 个工具源码 + `registry.py` + `hooks.py` + `cache.py` + `agent_context.py` + `utils.py`
+ 全部相关 ORM 模型（plot_structure.py, character.py, foreshadowing.py, world_setting.py,
timeline.py, style_constraints.py, setting_change.py, chapter.py, outline.py）

**根因模式:** 所有 Store `update_*` 方法使用 `setattr(obj, key, value)` 遍历 dict。
非 ORM 模型列名的 key 被设为 Python 属性但不会持久化到 DB（SQLAlchemy 只 flush 映射列）。
这就是幻影参数（Phantom Parameter）问题的根因——工具参数名与模型列名不匹配时，setattr 静默成功
但数据永远不会写入 DB。

---

## 与 v4.0 spec 的关键差异

| # | v4.0 遗漏 | v5.0 新增/修正 |
|---|-----------|---------------|
| 1 | A6 只修 `title→name` 和 `resolution→expected_resolution_chapter`，**漏了 `status`** | A6 修正：`status→current_status` 也必须改（Subplot 模型字段是 `current_status`） |
| 2 | `generate_world_setting_complete` 有 3 个幻影参数未发现 | 新增 A10：`history`、`social_structure`、`magic_system` 不在 WorldSetting 模型中 |
| 3 | `propose_outline_adjustment` 返回值中 `chapter_range` 在 `chapter_start/end` 为 None 时输出 "None-None" | 新增 A11：格式化需处理 None |
| 4 | `update_subplot` 返回值中 `updated.get("title")` 和变更对比也使用了幻影字段名 | A6 补充：返回值和变更对比中 `"title"` → `"name"`，`"status"` → `"current_status"` |
| 5 | E1 `apply_change` 未对 `new_value` 的 key 做白名单过滤 | E1 新增：硬编码白名单 dict 校验 new_value key，防止幻影参数通过 Store setattr 静默丢失 |
| 6 | `timeline_store.update_timeline_entry` 有 `hasattr` 保护但其他 Store 层无此保护 | 记录为架构改进建议，不纳入本次优化范围（需改 Store 层接口） |

---

## 模块总览

| 模块 | 优先级 | 类型 | 预计文件改动 |
|------|--------|------|-------------|
| A: Bug 修复 | P0 | 修 bug | 12 文件 |
| B: 消除参数爆炸 | P1 | 架构 | 1 文件 + Hook 验证 |
| C: 知识库查询优化 | P1 | 架构 | 1 文件 |
| D: 修订阶段上下文预算 | P1 | 架构 | 1 文件 |
| E: 修改提议闭环 | P2 | 新功能 | 7 文件 |
| F: 一致性检测增强 | P2 | 增强 | 1 文件 |
| G: 阶段回退能力 | P2 | 新功能 | 1 文件 |
| H: 工具调用时机指导 | P2 | 文档 | ~13 文件 docstring |
| I: 缓存性能优化 | P1 | 优化 | 1 文件 |
| J: 伏笔建议精度 | P2 | 增强 | 1 文件 |
| K: 新发现 Bug | P0 | 修 bug | 2 文件 |
| L: Docstring 国际化 | P2 | 文档 | 5 文件 |

---

## 模块 A: Bug 修复

### A1: `create_subplot` docstring 与签名不一致

**文件:** `backend/app/agents/tools/creation/subplot.py`

**源码现状:**
- 函数签名: `name, characters="[]", current_status="developing", raised_in_chapter=None, planned_intersection_chapter=None, expected_resolution_chapter=None`
- docstring Args: `name, description, characters, plot_block_id` — 其中 `description` 和 `plot_block_id` 在签名中不存在；`current_status`、`raised_in_chapter`、`planned_intersection_chapter`、`expected_resolution_chapter` 在 docstring 中缺失

**要求:** 重写 docstring Args，与签名完全一致:
```
Args:
    name: 支线名称
    characters: JSON 字符串列表，参与角色名（默认 []）
    current_status: 支线状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)（默认 developing）
    raised_in_chapter: 支线提出的章节号（可选）
    planned_intersection_chapter: 计划与主线交汇的章节号（可选）
    expected_resolution_chapter: 预期解决的章节号（可选）
```

### A2: `create_plot_question` docstring 与签名不一致

**文件:** `backend/app/agents/tools/creation/plot_question.py`

**要求:** 重写 docstring Args:
```
Args:
    question_text: 问题内容
    raised_in_chapter: 提出问题的章节号（可选）
    plot_block_id: 所属情节块 ID（可选）
```

### A3: `update_plot_block` 的 `chapter_range` 参数与模型不一致

**文件:** `backend/app/agents/tools/creation/update_plot_block.py`

**要求:**
1. 将 `chapter_range: str | None = None` 替换为 `chapter_start: int | None = None` + `chapter_end: int | None = None`
2. 更新 docstring Args
3. 更新 `update_data` 构建: `for field in ("title", "chapter_start", "chapter_end", "completion_summary")`

### A4: `propose_chapter_rewrite` docstring 引用不存在的 `focus` 参数

**文件:** `backend/app/agents/tools/modification/propose_chapter_rewrite.py`

**要求:** 删除 docstring 中 `focus` 的说明行

### A5: `create_plot_block` docstring 引用不存在的 `chapter_range` + 返回值字段名错误

**文件:** `backend/app/agents/tools/creation/plot_block.py`

**要求:**
1. 修复 docstring: `chapter_range` → `chapter_start` + `chapter_end`，JSON 参数补充类型提示
2. 返回值中 `chapter_range` 改为 `chapter_start` 和 `chapter_end` 分别返回（与模型字段一致）

### A6: `update_subplot` 的 `title`、`resolution`、`status` 均为幻影参数（P0 Bug）

**文件:** `backend/app/agents/tools/creation/update_subplot.py`

**源码现状:**
- 函数签名: `subplot_id, title=None, status=None, resolution=None`
- Subplot 模型字段: `name, characters, current_status, raised_in_chapter, planned_intersection_chapter, expected_resolution_chapter`
- `title` 不在模型中！`resolution` 也不在模型中！`status` 也不在模型中（模型字段是 `current_status`）！
- Store 层使用 `setattr(obj, key, value)` 遍历 dict，三个参数都被 setattr 设置为 Python 属性但不会持久化到 DB

**要求:**
1. 将 `title: str | None = None` 替换为 `name: str | None = None`
2. 将 `resolution: str | None = None` 替换为 `expected_resolution_chapter: int | None = None`
3. 将 `status: str | None = None` 替换为 `current_status: str | None = None`
4. 更新 `update_data` 构建: `for field in ("name", "current_status", "expected_resolution_chapter")`
5. 更新变更对比和返回值: `"title"` → `"name"`，`"status"` → `"current_status"`
6. 更新 docstring:
```
Args:
    subplot_id: 支线 ID
    name: 支线名称
    current_status: 支线状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)
    expected_resolution_chapter: 预期解决的章节号
```

### A7: `propose_setting_change` docstring 参数顺序与签名不一致

**文件:** `backend/app/agents/tools/modification/propose_setting_change.py`

**要求:** docstring Args 顺序从 `target_type, target_id, description, new_value` 改为 `target_type, target_id, new_value, description`

### A8: `update_plot_question` 的 `question` 和 `answer` 是幻影参数（P0 Bug）

**文件:** `backend/app/agents/tools/creation/update_plot_question.py`

**源码现状:**
- 函数签名: `question_id, question=None, answer=None, status=None`
- PlotQuestion 模型字段: `plot_block_id, question_text, status, raised_in_chapter, answered_in_chapter`
- `question` 应为 `question_text`，`answer` 应为 `answered_in_chapter`（int 类型，非 str）

**要求:**
1. 将 `question: str | None = None` 替换为 `question_text: str | None = None`
2. 将 `answer: str | None = None` 替换为 `answered_in_chapter: int | None = None`
3. 更新 `update_data` 构建和变更对比逻辑

### A9: `delete_plot_block` 使用 `chapter_range` 字段做安全检查（P0 Bug）

**文件:** `backend/app/agents/tools/creation/delete_plot_block.py`

**源码现状:** `target.get("chapter_range", "")` 永远返回空串（模型中无此字段），活跃伏笔安全检查永远不触发。

**要求:**
```python
chapter_start = target.get("chapter_start")
chapter_end = target.get("chapter_end")
if chapter_start is not None and chapter_end is not None:
    for f in active_fs:
        expected = f.get("expected_resolve_chapter")
        if expected and chapter_start <= expected <= chapter_end:
            affected_foreshadowings.append(...)
```

### A10: `generate_world_setting_complete` 的 `history`、`social_structure`、`magic_system` 为幻影参数（P0 Bug，v5 新增）

**文件:** `backend/app/agents/tools/creation/generate_world_setting_complete.py`

**源码现状:**
- 函数签名包含 `history: str = ""`、`social_structure: str = ""`、`magic_system: str = ""`
- 代码中 `if history: data["history"] = history` 等条件将这三个字段加入 `data` dict
- `data` 传给 `kb.world_setting.create(data)` / `kb.world_setting.update_by_id(existing["id"], data)`
- WorldSetting 模型字段只有: `id, project_id, core_concept, tiered_settings, key_locations, created_at, updated_at`
- `history`、`social_structure`、`magic_system` 通过 setattr 被设为 Python 属性但**永远不会持久化到 DB**

**根因分析:** 这是世界观扩展需求与模型设计不匹配的典型案例。这些字段在创建时被 Agent 传入（来自 LLM 生成的世界观），但模型中没有对应列来存储。

**修复方案:** 将这三个参数的内容合并到 `tiered_settings` 中，具体：
1. `history` → 追加到 `tiered_settings["yellow"]` 列表（历史背景属于可灵活调整的规则）
2. `social_structure` → 追加到 `tiered_settings["yellow"]` 列表（社会结构属于有代价可违反的规则）
3. `magic_system` → 追加到 `tiered_settings["red"]` 列表（魔法体系属于核心不可违反的规则，类似物理定律）

实现:
```python
# 不再将 history/social_structure/magic_system 单独加入 data
# 而是合并到 tiered
if history:
    tiered.setdefault("yellow", []).append(f"[历史]{history}")
if social_structure:
    tiered.setdefault("yellow", []).append(f"[社会]{social_structure}")
if magic_system:
    tiered.setdefault("red", []).append(f"[魔法体系]{magic_system}")
```

4. 从函数签名中保留这三个参数（Agent 仍需要传入这些信息），但**不再单独加入 data dict**
5. 更新 docstring 说明合并逻辑
6. 返回值中增加 `merged_into_tiered: true` 标记

### A11: `propose_outline_adjustment` 返回值中 `chapter_range` 格式化不安全（v5 新增）

**文件:** `backend/app/agents/tools/modification/propose_outline_adjustment.py`

**源码现状:**
```python
"chapter_range": f"{b.get('chapter_start')}-{b.get('chapter_end')}"
```
当 `chapter_start` 或 `chapter_end` 为 None 时输出 "None-None"。

**要求:**
```python
cs = b.get('chapter_start')
ce = b.get('chapter_end')
"chapter_range": f"{cs}-{ce}" if cs is not None and ce is not None else "未设定"
```

---

## 模块 B: 消除参数爆炸

### B1: 精简 `generate_chapter_content` 参数

**文件:** `backend/app/agents/tools/creation/generate_chapter_content.py`

**要求:**

1. 从函数签名中删除 10 个废弃参数: `summary`, `status`, `scene_count`, `new_foreshadowings`, `reclaimed_foreshadowing_ids`, `timeline_summary`, `rhythm_score`, `tension_score`, `emotion_score`, `emotion_tag`

2. 最终签名:
```python
async def generate_chapter_content(
    chapter_number: int,
    chapter_title: str,
    content: str,
    word_count: int = 0,
) -> dict:
```

3. 删除对应功能代码块:
   - `parse_json_param` 调用: 删除 `new_fs` 和 `reclaimed_ids` 的解析
   - 步骤 2（时间线创建）: 删除整个 `if timeline_summary:` 代码块
   - 步骤 3（创建新伏笔）: 删除整个 `for fs_data in new_fs:` 循环
   - 步骤 4（回收伏笔）: 删除整个 `for fs_id in reclaimed_ids:` 循环
   - `warnings` 列表中相关 append 全部删除
   - 保留步骤 1（保存章节正文）和步骤 5（风格快照）

4. 统一 KB 获取方式: 删除 `from app.agents.services.knowledge_base import KnowledgeBaseService` + `project_id = get_project_id()` + `kb = KnowledgeBaseService(project_id)` 替换为 `kb = _kb()`

5. 更新返回值: 删除 `timeline_entry`/`timeline_error`/`new_foreshadowings`/`new_foreshadowing_errors`/`reclaimed_foreshadowings`/`reclaim_errors`。保留 `action`/`chapter_number`/`title`/`word_count`/`style_snapshot_created`/`style_snapshot_error`/`message`/`warnings`

6. Hook 兼容性: 确认返回值仍包含 `chapter_number` 字段

---

## 模块 C: 知识库查询优化

### C1: `knowledge_search` 降级路径 token 控制 + 关系匹配优化

**文件:** `backend/app/agents/tools/perception/knowledge_search.py`

**要求:**

1. 新增 `_MAX_ITEMS_PER_TYPE = 10` 替换 `_FALLBACK_MAX_PER_TYPE = 5`
2. 新增 `MAX_FALLBACK_TOKENS = 4000`
3. 重构降级路径为步骤列表+循环
4. **关系匹配优化:** 只在 `results` 中已有 characters 数据时执行关系查询，且只匹配结果中已有角色的关系，截断为 `_MAX_ITEMS_PER_TYPE` 条

---

## 模块 D: 修订阶段上下文预算控制

### D1: `_load_revision_context` 增加 BudgetTracker + world_setting

**文件:** `backend/app/agents/agent_context.py`

**源码现状:** 完全没有 BudgetTracker 控制，没有 world_setting，characters 加载完整对象（含 backstory），全量加载无筛选。

**要求:** 使用 BudgetTracker 逐项控制，加载精简数据:
1. **world_setting**: 精简版（core_concept + red_settings + key_locations）
2. **characters**: 索引模式（id + name + role）
3. **foreshadowings**: 精简模式（id + content[:60] + status + planted_chapter + expected_resolve_chapter）
4. **timeline**: 最近 20 章摘要，每条 chapter_number + summary[:80] + emotion_tag
5. **plot_questions**: 只加载 pending 状态
6. **subplots**: 只加载非 abandoned 状态
7. **style_snapshots**: 只加载最近 10 条
8. **style_constraints**: 保留（走预算检查）
9. 每种数据加载后做 `budget.can_add` 检查，超限则跳过后续

---

## 模块 E: 修改提议闭环

### E1: 新增 `apply_change` 工具

**文件:** `backend/app/agents/tools/modification/apply_change.py`（新建）

**关键实现细节:**
1. `kb.changes.get(change_id)` 获取变更记录，如果返回 None 返回错误
2. 检查 `status == "proposed"`，否则返回错误
3. 根据 `target_type` 调用对应 Store 更新方法
4. `chapter_rewrite` 类型不直接 apply，返回提示引导使用 `rewrite_chapter`
5. `outline_adjustment` 类型调用 `kb.outlines.update(new_value)`，忽略 target_id（固定为 0）
6. Store 更新成功后 `kb.changes.update(change_id, {"status": "applied", "author_decision": "proceed"})`
7. Store 更新失败时不更新变更状态
8. **new_value 白名单过滤（防幻影参数）:** 在 apply 之前，根据 `target_type` 校验 `new_value` 的 key 是否为目标 ORM 模型的有效列名。非模型列名的 key 从 `new_value` 中移除并记录到 `filtered_keys` 警告列表。这防止了 Store 层裸 setattr 导致的幻影参数问题（A6/A8/A10 的根因）。

   白名单映射（target_type → 允许的列名集合）:
   - `world_setting` → `{core_concept, tiered_settings, key_locations}`
   - `character` → `{name, role, personality, catchphrase, habit_action, deep_fear, core_motivation, growth_arc, appearance, backstory, signature_item}`
   - `foreshadowing` → `{content, level, appearance_count, status, planted_chapter, expected_resolve_chapter, resolved_chapter, related_characters}`
   - `style` → `{taboo_words, forbidden_patterns, style_anchor, abstract_rules}`
   - `outline` → `{title, summary, plot_points, characters, world_setting, emotional_curve, collected_info, inspiration_template, messages, chapter_count_suggested, chapter_count_confirmed, confirmed}`
   - `relation` → `{character_a_id, character_b_id, relation_type, direction, current_status, trust_level}`
   - `outline_adjustment` → 同 `outline`

   **注意:** 不使用 `inspect()` 运行时反射，而是在代码中硬编码白名单 dict。运行时反射引入 ORM 依赖且可能因 session 状态异常，硬编码白名单更安全、更可测试。白名单排除了 `id`、`project_id`、`created_at`、`updated_at` 等系统字段，防止误覆盖。

### E2: 新增 `reject_change` 工具

**文件:** `backend/app/agents/tools/modification/reject_change.py`（新建）

### E3: 新增 `list_proposed_changes` 工具

**文件:** `backend/app/agents/tools/modification/list_proposed_changes.py`（新建）

### E4: 更新 `expand_world_setting` 走变更提议流程

**文件:** `backend/app/agents/tools/assist/expand_world_setting.py`

**要求:** 在写入之前新增 severity 判断: `if impact_level == "severe"` 时创建变更提议而非直接写入。

### E5: 更新注册表和导出

**文件:** `modification/__init__.py`, `registry.py`, `tools/__init__.py`, `agent_tools.py`

三个新工具加入 `_STRUCTURE_EXTRA` 列表（结构阶段及以上可用）。

---

## 模块 F: 一致性检测增强

### F1: `consistency_scan` 增加情绪凝固检测 + 正→负跳跃检测

- 遍历 `sorted_chapters` 中连续的 `emotion_tag`，如果同一 tag 持续 3+ 章未变化则标记
- 情绪跳跃检测补充正→负突变检测（当前只检测负→正）

### F2: 设定引用矛盾检测优化

- 字符串匹配阈值从 `>= 4` 改为 `>= 6`
- 长度 4-5 的规则改用分词匹配
- confidence 区分 `low`（字符串匹配）和 `very_low`（分词匹配）

### F3: 新增 `foreshadowing` 检查类型

- `check_types` 参数新增 `"foreshadowing"` 选项
- 检测: planted_chapter > expected_resolve_chapter、active 状态但超期 5+ 章、reclaimed 状态但 resolved_chapter 为空

---

## 模块 G: 阶段回退能力

### G1: `advance_phase` 支持 `direction=backward`

**文件:** `backend/app/agents/tools/creation/advance_phase.py`

**要求:**
1. 函数签名新增 `direction: str = "forward"`
2. **`phase_labels` 需提前到回退逻辑之前定义**（当前源码中它在行锁代码之后）
3. 回退映射: `{WRITING: STRUCTURE, STRUCTURE: INCUBATION}`
4. REVISION 和 INCUBATION 不可回退
5. 回退复用 `if advanced:` 的行锁写入逻辑

---

## 模块 H: 工具调用时机指导

### H1: 在关键工具的 docstring 中增加 Prerequisites 段落

**涉及文件:** 11 个工具文件的 docstring（仅改 docstring，不改逻辑）

---

## 模块 I: 缓存性能优化

### I1: `ToolResultCache` 增加前缀索引

**文件:** `backend/app/agents/tools/cache.py`

**要求:**
1. 新增 `_prefix_index: dict[str, set[str]]`，key 为工具名，value 为 cache key 集合
2. `set` 方法同时更新 `_prefix_index`
3. `invalidate` 和 `invalidate_by_prefix` 改为基于索引的 O(1) 查找
4. `clear` 方法同时清空 `_prefix_index`

---

## 模块 J: 伏笔建议精度提升

### J1: `suggest_foreshadowing` 增加停用词过滤 + 自适应阈值

1. 新增 `_SUGGEST_STOPWORDS` 停用词集合
2. jieba 可用时: `min_len=4, min_freq=3`；bigram 模式: `min_len=2, min_freq=5`
3. 导入 `from app.utils.text import _jieba_available`

---

## 模块 K: 新发现 Bug

### K1: `delete_plot_block` 的 `chapter_range` 字段不存在（P0 Bug）

**已在 A9 中合并**

### K2: `rhythm_analysis` 单调检测逻辑错误

**文件:** `backend/app/agents/tools/perception/rhythm_analysis.py`

**问题:**
1. `reversed(recent)` 导致 start/end 颠倒
2. 每步 append 导致同一段单调区域被重复记录
3. `length` 计数不准确

**要求:** 改为正序遍历，只在序列结束时记录一次，阈值从 2 改为 3:

```python
monotone_sections = []
consecutive_same = 1
start_chapter = None
last_tag = None
prev_chapter = None

for entry in recent:
    tag = entry.get("emotion_tag")
    if tag and tag == last_tag and tag:
        consecutive_same += 1
    else:
        if consecutive_same >= 3 and last_tag:
            monotone_sections.append({
                "start_chapter": start_chapter,
                "end_chapter": prev_chapter,
                "emotion": last_tag,
                "length": consecutive_same,
            })
        consecutive_same = 1
        start_chapter = entry.get("chapter_number")
    prev_chapter = entry.get("chapter_number")
    last_tag = tag

# 检查最后一段
if consecutive_same >= 3 and last_tag:
    monotone_sections.append({
        "start_chapter": start_chapter,
        "end_chapter": prev_chapter,
        "emotion": last_tag,
        "length": consecutive_same,
    })
```

---

## 模块 L: Docstring 国际化统一

### L1: 多个工具 docstring 存在英文描述

**涉及文件:**

| 文件 | 问题 |
|------|------|
| `creation/relation.py` | `relation_type` 和 `direction` 描述含英文 |
| `creation/evolution_plan.py` | Args 描述全为英文格式 |
| `creation/foreshadowing.py` | `level` 和 `related_characters` 描述含英文 |
| `creation/timeline_entry.py` | `emotion_tag` 描述含英文 |
| `creation/character.py` | `role` 描述含英文 "Character role - one of:" |
| `perception/foreshadowing_check.py` | `current_chapter` 描述含英文 |

**要求:** 统一为中文描述，格式与 `create_subplot` 等工具的 docstring 一致。

---

## 幻影参数完整清单

经三轮审查，确认以下所有幻影参数（工具参数名 ≠ 模型列名，通过 setattr 静默丢失）:

| 工具 | 幻影参数 | 正确列名 | 模型 |
|------|----------|----------|------|
| `update_subplot` | `title` | `name` | Subplot |
| `update_subplot` | `status` | `current_status` | Subplot |
| `update_subplot` | `resolution` | `expected_resolution_chapter` | Subplot |
| `update_plot_question` | `question` | `question_text` | PlotQuestion |
| `update_plot_question` | `answer` | `answered_in_chapter` | PlotQuestion |
| `update_plot_block` | `chapter_range` | `chapter_start` + `chapter_end` | PlotBlock |
| `delete_plot_block` | 读取 `chapter_range` | 应读取 `chapter_start` + `chapter_end` | PlotBlock |
| `generate_world_setting_complete` | `history` | 合并到 `tiered_settings.yellow` | WorldSetting |
| `generate_world_setting_complete` | `social_structure` | 合并到 `tiered_settings.yellow` | WorldSetting |
| `generate_world_setting_complete` | `magic_system` | 合并到 `tiered_settings.red` | WorldSetting |

---

## 测试要求

### 新增测试文件

| 文件 | 覆盖范围 |
|------|---------|
| `backend/tests/test_tool_cache.py` | ToolResultCache 的前缀索引、命中/失效/清空 |
| `backend/tests/test_change_workflow.py` | apply_change、reject_change、list_proposed_changes |

### 需更新的测试文件

| 文件 | 更新内容 |
|------|---------|
| `backend/tests/test_agent_tools.py` | 新增三个闭环工具注册检查 |
| `backend/tests/test_advance_phase.py` | 新增回退场景测试 |
| `backend/tests/test_rhythm_analysis.py` | 新增单调检测场景测试（如存在） |

### 幻影参数专项测试

为每个 P0 幻影参数修复编写测试：调用 update 工具后，通过 Store 层直接读取验证数据确实写入了 DB（而非仅 setattr）。

---

## 风险与约束

1. **不改变 Store 层接口** — 所有改动在工具层完成
2. **不改变数据库模型** — SettingChange 已支持 applied/abandoned 状态
3. **向后兼容** — `generate_chapter_content` 删除废弃参数后，旧调用方式会报错，这是预期行为
4. **阶段工具递进关系** — 新增 3 个闭环工具加入 `_STRUCTURE_EXTRA`
5. **兼容层更新** — `agent_tools.py` 是旧导入路径兼容层，需同步更新
6. **chapter_rewrite 的 apply_change 特殊处理** — 不直接 apply，引导使用 `rewrite_chapter`
7. **apply_change 的 new_value 白名单过滤** — 防止非模型列名的 key 通过 setattr 静默丢失（A6/A8/A10 的根因教训），硬编码白名单 dict 校验
8. **knowledge_search 重构风险** — C1 将平铺 if 结构重构为步骤列表+循环，必须确保单个 target 查询行为不变
9. **expand_world_setting 写入逻辑修正** — E4 需新增 severity 判断，是新增条件分支
10. **tokenize_chinese 退化模式** — J1 和 F2 都依赖 `tokenize_chinese`，jieba 不可用时退化为 bigram
11. **phase_labels 作用域** — G1 需将 `phase_labels` 定义提前到回退逻辑之前
12. **Hook 链兼容性** — B1 删除追踪参数后确认 `chapter_number` 字段仍在返回值中
13. **rhythm_analysis 单调检测修复** — K2 改为正序遍历+结束记录，需验证不再重复记录
14. **A10 合并策略** — `generate_world_setting_complete` 的 history/social_structure/magic_system 合并到 tiered_settings 后，前端如果依赖这些字段的返回值可能受影响（但前端从 DB 读取，这些字段本就未持久化，所以无影响）

---

## 修改后必须重建

所有改动均在 backend Python 代码:
```bash
docker compose restart backend
```
