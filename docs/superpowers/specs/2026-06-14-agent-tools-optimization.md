# Agent 工具体系全面优化 Spec（v3.2 终审修正版）

## 背景

NovelAgent v0.8.11 的 Agent 工具体系共 29 个工具（感知 8 + 创作 18 + 修改 3 + 辅助 4）。经 v2 spec 三轮审查和本轮独立源码交叉验证，发现 v2 spec 存在 18 处遗漏/错误。本 spec 为全面重写版，基于逐文件源码审查结果，确保每一项优化都有精确的源码对应。

**审查版本:** v3 — 基于全部 29 个工具源码 + 注册表 + 上下文策略 + 缓存 + Hook 链的逐行交叉验证。

---

## 与 v2 spec 的关键差异

| # | v2 问题 | v3 修正 |
|---|---------|---------|
| 1 | A3 只关注 `chapter_range` → `chapter_start/end` | 补充 `must_happen`/`questions_to_raise`/`questions_to_answer` 三个 JSON 参数的 docstring 修复 |
| 2 | A1-A5 仅列 5 个 docstring bug | 新增 A6（`update_subplot`）、A7（`propose_setting_change`）两个遗漏的 docstring bug |
| 3 | B1 未说明 `status` 参数实际写入章节 | 明确 `status` 用于 `kb.chapters.save_content` 调用，删除后需保留默认值 |
| 4 | E4 描述"当前源码中写入逻辑在 `if impact_level != "severe"` 之后" | 源码实际是无条件写入，无 severity 判断。修正为先判断 severe 再写入 |
| 5 | F1 角色属性矛盾检测的"全局情绪"方案 | 改为只在有角色维度的时间线条目时启用，否则跳过。增加去重逻辑 |
| 6 | G1 未分析 `phase_labels` 作用域 | 明确 `phase_labels` 需在回退逻辑之前定义 |
| 7 | H1 遗漏 `check_chapter_transition` 的 Prerequisites | 补充 |
| 8 | H1 遗漏 `propose_setting_change` docstring 参数顺序错误 | 新增 A7 |
| 9 | I1 `invalidate_by_prefix` 的 `rstrip(":")` 假设不稳健 | 改为与 `invalidate` 统一的 tool_name 查询 |
| 10 | 未提及 `generate_chapter_content` 的 Hook 链兼容性 | B1 增加 Hook 兼容性验证步骤 |
| 11 | 未发现 `consistency_scan` 缺少 `foreshadowing` 类型 | 新增 F3 模块 |
| 12 | `generate_chapter_content` 的 `KnowledgeBaseService` 导入方式与其他工具不一致 | B1 统一为 `_kb()` |
| 13 | `update_subplot` docstring 参数完全不一致 | 新增 A6 |
| 14 | D1 revision 上下文未加载 `world_setting` | 补充 |
| 15 | `suggest_foreshadowing` 的 `tokenize_chinese` 退化为 bigram 时阈值应更高 | J1 补充退化分支说明 |
| 16 | `record_chapter_meta` 的 `reclaimed_foreshadowing_ids` 中伏笔回收缺少 `resolved_chapter` 设置说明 | 不算 bug（源码已有 `resolved_chapter: chapter_number`），但 docstring 应说明 |
| 17 | A6 将 `update_subplot` 的 `title` 参数仅视为 docstring 问题 | 实际是 P0 Bug：Subplot 模型只有 `name` 字段，`title` 传入后 setattr 设置但不会持久化到 DB。需将 `title` 改为 `name` |
| 18 | 未发现 `update_plot_question` 的 `question` 和 `answer` 参数是幻影参数 | PlotQuestion 模型只有 `question_text` 和 `answered_in_chapter`，`question` 和 `answer` 传入后不会持久化。新增 A8 |

---

## 模块总览

| 模块 | 优先级 | 类型 | 预计文件改动 |
|------|--------|------|-------------|
| A: Bug 修复 | P0 | 修 bug | 9 文件 |
| B: 消除参数爆炸 | P1 | 架构 | 1 文件 + Hook 验证 |
| C: 知识库查询优化 | P1 | 架构 | 1 文件 |
| D: 修订阶段上下文预算 | P1 | 架构 | 1 文件 |
| E: 修改提议闭环 | P2 | 新功能 | 7 文件 |
| F: 一致性检测增强 | P2 | 增强 | 1 文件 |
| G: 阶段回退能力 | P2 | 新功能 | 1 文件 |
| H: 工具调用时机指导 | P2 | 文档 | ~13 文件 docstring |
| I: 缓存性能优化 | P1 | 优化 | 1 文件 |
| J: 伏笔建议精度 | P2 | 增强 | 1 文件 |

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

**验证:** docstring Args 列出 6 个参数，签名也有 6 个参数，一一对应。

### A2: `create_plot_question` docstring 与签名不一致

**文件:** `backend/app/agents/tools/creation/plot_question.py`

**源码现状:**
- 函数签名: `question_text, raised_in_chapter=None, plot_block_id=None`
- docstring Args: `plot_block_id, question, question_type, raised_in_chapter` — `question` 应为 `question_text`，`question_type` 不存在于签名

**要求:** 重写 docstring Args:
```
Args:
    question_text: 问题内容
    raised_in_chapter: 提出问题的章节号（可选）
    plot_block_id: 所属情节块 ID（可选）
```

**验证:** 3 个参数一一对应。

### A3: `update_plot_block` 的 `chapter_range` 参数类型不一致

**文件:** `backend/app/agents/tools/creation/update_plot_block.py`

**源码现状:**
- 函数签名: `plot_block_id, title=None, chapter_range=None, must_happen=None, questions_to_raise=None, questions_to_answer=None, completion_summary=None`
- docstring Args 有 `chapter_range`，但 `create_plot_block` 用的是 `chapter_start + chapter_end` 两个 int
- Store 层的 `update_plot_block` 期望 `chapter_start`/`chapter_end` 字段
- `must_happen`/`questions_to_raise`/`questions_to_answer` 三个参数的 docstring 描述与实际类型（JSON 字符串→解析为 list）一致，但缺少"JSON 字符串列表"的类型提示

**要求:**
1. 将 `chapter_range: str | None = None` 替换为 `chapter_start: int | None = None` + `chapter_end: int | None = None`
2. 更新 docstring:
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
3. 更新 `update_data` 构建逻辑:
```python
for field in ("title", "chapter_start", "chapter_end", "completion_summary"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```

**验证:** `docker exec novelagent-backend-1 pytest -v`

### A4: `propose_chapter_rewrite` docstring 引用不存在的 `focus` 参数

**文件:** `backend/app/agents/tools/modification/propose_chapter_rewrite.py`

**源码现状:** docstring Args 有 `focus: 重写重点 - "plot", "character", "style", 或 "all"`，但签名只有 `chapter_number` 和 `reason`

**要求:** 删除 docstring 中 `focus` 的说明行

**验证:** docstring Args 只剩 `chapter_number` 和 `reason`

### A5: `create_plot_block` docstring 引用不存在的 `chapter_range` 参数

**文件:** `backend/app/agents/tools/creation/plot_block.py`

**源码现状:**
- 函数签名: `title, chapter_start, chapter_end, must_happen="[]", questions_to_raise="[]", questions_to_answer="[]", expected_mood=""`
- docstring Args 有 `chapter_range` 和 `must_happen/questions_to_raise/questions_to_answer`（缺少"JSON 字符串列表"类型提示）和 `expected_mood`

**要求:** 将 `chapter_range` 替换为 `chapter_start` 和 `chapter_end`，并为 JSON 参数补充类型提示:
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

**验证:** 7 个参数一一对应

### A6: `update_subplot` 的 `title` 参数是幻影参数（P0 Bug，v3.1 修正）

**文件:** `backend/app/agents/tools/creation/update_subplot.py`

**源码现状:**
- 函数签名: `subplot_id, title=None, status=None, resolution=None`
- Subplot 模型字段: `name, characters, current_status, raised_in_chapter, planned_intersection_chapter, expected_resolution_chapter`
- `title` 不在 Subplot 模型中！`create_subplot` 创建时用的字段是 `name`，但 `update_subplot` 更新时用的是 `title`
- Store 层 `update_subplot` 使用 `setattr(obj, key, value)` 遍历 dict，`title` 被 setattr 设置为 Python 属性但不会持久化到 DB（SQLAlchemy 只 flush 模型定义的列）
- 同样，`resolution` 也不在 Subplot 模型中，同样是幻影参数

**要求:**
1. 将 `title: str | None = None` 替换为 `name: str | None = None`
2. 将 `resolution: str | None = None` 替换为 `expected_resolution_chapter: int | None = None`（模型中有此字段）
3. 更新 `update_data` 构建逻辑:
```python
for field in ("name", "status", "expected_resolution_chapter"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```
4. 更新 docstring:
```
Args:
    subplot_id: 支线 ID
    name: 支线名称（可选，None 表示不修改）
    status: 新状态 - "developing"(发展中), "active"(活跃), "resolved"(已解决), "abandoned"(已废弃)（可选）
    expected_resolution_chapter: 预期解决的章节号（可选）
```
5. 更新变更对比逻辑中使用 `before.get("name")` 替代 `before.get("title")`

**验证:**
- 修改后通过 `update_subplot` 更新 `name` 字段应能正确持久化到 DB
- `docker exec novelagent-backend-1 pytest -v`

### A7: `propose_setting_change` docstring 参数顺序与签名不一致（v3 新增）

**文件:** `backend/app/agents/tools/modification/propose_setting_change.py`

**源码现状:**
- 函数签名: `target_type, target_id, new_value, description`
- docstring Args 顺序: `target_type, target_id, description, new_value` — `description` 和 `new_value` 位置反了

**要求:** 调整 docstring Args 顺序与签名一致:
```
Args:
    target_type: 修改对象类型 - "world_setting", "character", "foreshadowing", "style", "outline", "relation"
    target_id: 修改对象的 ID
    new_value: 新值（JSON 字符串或普通字符串）
    description: 变更内容的自然语言描述
```

### A8: `update_plot_question` 的 `question` 和 `answer` 参数是幻影参数（P0 Bug，v3.1 新增）

**文件:** `backend/app/agents/tools/creation/update_plot_question.py`

**源码现状:**
- 函数签名: `question_id, question=None, answer=None, status=None`
- PlotQuestion 模型字段: `plot_block_id, question_text, status, raised_in_chapter, answered_in_chapter`
- `question` 不在 PlotQuestion 模型中！模型字段是 `question_text`
- `answer` 也不在 PlotQuestion 模型中！模型只有 `answered_in_chapter`（整数，非文本）
- 两个参数通过 `setattr` 设置但不会持久化到 DB

**要求:**
1. 将 `question: str | None = None` 替换为 `question_text: str | None = None`
2. 将 `answer: str | None = None` 替换为 `answered_in_chapter: int | None = None`（标记回答时指定章节号）
3. 更新 `update_data` 构建逻辑:
```python
for field in ("question_text", "answered_in_chapter", "status"):
    value = locals()[field]
    if value is not None:
        update_data[field] = value
```
4. 更新 docstring:
```
Args:
    question_id: 问题 ID
    question_text: 问题内容（可选，None 表示不修改）
    answered_in_chapter: 回答章节号（可选，标记问题被回答的章节）
    status: 新状态 - "pending"(待回答), "answered"(已回答), "closed"(已关闭)（可选）
```
5. 更新变更对比逻辑中的字段名

**验证:**
- 修改后通过 `update_plot_question` 更新 `question_text` 和 `answered_in_chapter` 应能正确持久化到 DB
- `docker exec novelagent-backend-1 pytest -v`

---

## 模块 B: 消除参数爆炸

### B1: 精简 `generate_chapter_content` 参数

**文件:** `backend/app/agents/tools/creation/generate_chapter_content.py`

**源码现状分析:**

1. 函数有 17 个参数，其中 10 个标记为"已废弃，请用 record_chapter_meta"
2. `summary` 虽然被标记为废弃，但实际在步骤 2 中被用作 `timeline_summary` 的回退值: `timeline_summary or summary or ""`
3. `status` 参数实际传入章节保存逻辑，但源码中 `kb.chapters.save_content(chapter_number, content, word_count or len(content))` 只用了 `chapter_number`/`content`/`word_count`，`status` 实际并未传入 save_content。需要确认是否需要在保存时传入 status
4. 该工具使用了 `from app.agents.services.knowledge_base import KnowledgeBaseService` 而非其他工具统一的 `_kb()` 函数
5. `hooks.py` 中 `TOOL_HOOKS["generate_chapter_content"]` 引用了该工具，删除追踪参数后 Hook 中 `tool_result.get("chapter_number")` 仍然有效

**要求:**

1. 从函数签名中删除以下 10 个参数: `summary`, `status`, `scene_count`, `new_foreshadowings`, `reclaimed_foreshadowing_ids`, `timeline_summary`, `rhythm_score`, `tension_score`, `emotion_score`, `emotion_tag`

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
   - 步骤 2（时间线创建）: 删除整个 `if timeline_summary:` 代码块，包括 `timeline_created`、`timeline_error` 变量
   - 步骤 3（创建新伏笔）: 删除整个 `for fs_data in new_fs:` 循环，包括 `created_fs`、`new_foreshadowing_errors`
   - 步骤 4（回收伏笔）: 删除整个 `for fs_id in reclaimed_ids:` 循环，包括 `reclaim_errors`
   - `warnings` 列表中与上述步骤相关的 append: 删除 `new_fs_warn`、`reclaimed_ids_warn`、`timeline_error`、`new_foreshadowing_errors`、`reclaim_errors` 相关的 append
   - 保留步骤 1（保存章节正文）和步骤 5（风格快照）

4. 统一 KnowledgeBaseService 获取方式: 将 `from app.agents.services.knowledge_base import KnowledgeBaseService` + `kb = KnowledgeBaseService(project_id)` 替换为 `kb = _kb()`

5. 更新 docstring: 删除废弃参数的 Args 说明，增加 Prerequisites 段落

6. 更新返回值: 删除 `timeline_entry`、`timeline_error`、`new_foreshadowings`、`new_foreshadowing_errors`、`reclaimed_foreshadowings`、`reclaim_errors`。保留 `action`、`chapter_number`、`title`、`word_count`、`style_snapshot_created`、`style_snapshot_error`、`message`、`warnings`

7. Hook 兼容性: `hooks.py` 中 `_hook_foreshadowing_check` 和 `_hook_style_quick_check` 都通过 `tool_result.get("chapter_number")` 获取章节号，删除追踪参数后该字段仍在返回值中，Hook 无需修改。验证步骤需确认 Hook 链正常

**验证:**
- `docker exec novelagent-backend-1 pytest -v`
- 确认 Hook 链正常: `generate_chapter_content` 返回值仍包含 `chapter_number`

---

## 模块 C: 知识库查询优化

### C1: `knowledge_search` 降级路径 token 控制

**文件:** `backend/app/agents/tools/perception/knowledge_search.py`

**源码现状:**
- 当语义检索不可用时降级为全量 DB 查询
- `target="all"` 时一次性拉取所有角色、伏笔、时间线、情节块、关系
- `_FALLBACK_MAX_PER_TYPE = 5`，但截断后仍可能总数据量巨大（9 个子类型 × 5 条 = 45 条完整对象）
- 降级路径是平铺的 `if target in ("all", ...)` 结构，无法 break 提前退出
- 关系匹配部分: `kb.characters.list_relations()` 无条件调用，截断为 5 条，但实际可能拉取全部关系后再截断

**要求:**

1. 新增 `_MAX_ITEMS_PER_TYPE = 10` 替换 `_FALLBACK_MAX_PER_TYPE = 5`（增大单类型上限，但通过总 token 预算控制总量）

2. 新增总 token 预算常量 `MAX_FALLBACK_TOKENS = 4000`

3. 将平铺 if 结构重构为步骤列表+循环，支持 break:

```python
from app.agents.token_budget import estimate_tokens
import json

query_steps = [
    ("world_setting", "world_setting", lambda: kb.world_setting.get()),
    ("characters", "characters", lambda: kb.characters.list_characters()),
    ("foreshadowings", "foreshadowing", lambda: kb.foreshadowings.list_foreshadowings()),
    ("timeline", "timeline", lambda: kb.timelines.list_timeline()),
    ("plot_blocks", "plot", lambda: kb.plots.list_plot_blocks()),
    ("plot_questions", "plot", lambda: kb.plots.list_plot_questions()),
    ("subplots", "plot", lambda: kb.plots.list_subplots()),
    ("style_constraints", "style", lambda: kb.styles.get_constraints()),
    ("recent_style_snapshots", "style", lambda: kb.styles.list_snapshots(last_n=5)),
]

estimated_tokens = 0

for result_key, target_match, query_fn in query_steps:
    if target not in ("all", target_match):
        continue
    data = query_fn()
    if data:
        if isinstance(data, list) and len(data) > _MAX_ITEMS_PER_TYPE:
            results[result_key] = data[:_MAX_ITEMS_PER_TYPE]
            results[f"{result_key}_total"] = len(data)
            truncated = True
        else:
            results[result_key] = data
    if target == "all":
        sub_json = json.dumps({result_key: results.get(result_key, {})}, ensure_ascii=False)
        estimated_tokens += estimate_tokens(sub_json)
        if estimated_tokens > MAX_FALLBACK_TOKENS:
            results["truncated"] = True
            results["truncation_reason"] = "降级路径 token 预算超限，请使用精确 target 参数"
            break
```

关键说明:
- `world_setting.get()` 返回单个 dict 而非 list，不需要截断
- `style_constraints` 是单个 dict，`recent_style_snapshots` 已通过 `last_n=5` 限制，都不需要截断
- `plot` target 对应 3 个子步骤（blocks/questions/subplots），每个独立查询和截断
- token 预算检查只在 `target == "all"` 时执行，单个 target 查询由 `_MAX_ITEMS_PER_TYPE` 控制数据量

4. 关系匹配部分简化:
- 只在 `results` 中已有 characters 数据时执行
- 只匹配结果中已有角色的关系
- 截断为 `_MAX_ITEMS_PER_TYPE` 条
- 无 characters 数据时跳过

5. 更新 docstring: 增加"降级模式下有 token 预算限制（4000 token），大数据集建议使用精确 target 参数"

**验证:** `docker exec novelagent-backend-1 pytest -v`

---

## 模块 D: 修订阶段上下文预算控制

### D1: `_load_revision_context` 增加 BudgetTracker

**文件:** `backend/app/agents/agent_context.py`

**源码现状:**
```python
def _load_revision_context(kb, budget, context):
    chars = kb.characters.list_characters()
    context["characters"] = chars          # 完整角色对象，含 backstory
    foreshadowings = kb.foreshadowings.list_foreshadowings()
    context["foreshadowings"] = foreshadowings  # 全部伏笔
    questions = kb.plots.list_plot_questions()
    context["plot_questions"] = questions  # 全部问题（含已回答）
    subplots = kb.plots.list_subplots()
    context["subplots"] = subplots        # 全部支线（含已废弃）
    timeline = kb.timelines.list_timeline()
    context["timeline"] = timeline         # 全部时间线
    style = kb.styles.get_constraints()
    if style:
        context["style_constraints"] = style
    snapshots = kb.styles.list_snapshots()
    context["style_snapshots"] = snapshots # 全部风格快照
```

问题: 不做 token 预算控制，直接赋值全量数据。遗漏了 `world_setting` 数据（修订阶段也需要查看世界观设定）。

**要求:**

1. 使用 BudgetTracker 逐项控制，与其他阶段一致
2. **world_setting**: 加载精简版（`core_concept` + `red_settings` + `key_locations`），与其他阶段的精简版一致
3. **characters**: 截断为索引模式（id + name + role），与 writing 阶段一致
4. **foreshadowings**: 截断为精简模式: id + content[:60] + status + planted_chapter + expected_resolve_chapter
5. **timeline**: 截断为最近 20 章摘要（`timeline[:20]`），每条只保留 `chapter_number` + `summary[:80]` + `emotion_tag`
6. **plot_questions**: 只加载 pending 状态
7. **subplots**: 只加载非 abandoned 状态
8. **style_snapshots**: 只加载最近 10 条（`kb.styles.list_snapshots(last_n=10)`）
9. **style_constraints**: 保留（但走预算检查）
10. 每种数据加载后做 `budget.can_add` 检查，超限则跳过后续

**验证:**
- `docker exec novelagent-backend-1 pytest -v`
- 确认 `_load_revision_context` 的返回值总 token 在 `max_tokens` 预算内

---

## 模块 E: 修改提议闭环

### E1: 新增 `apply_change` 工具

**文件:** `backend/app/agents/tools/modification/apply_change.py`（新建）

**功能:** 将 proposed 状态的变更应用到知识库。

**函数签名:**
```python
@tool
async def apply_change(change_id: int) -> dict:
    """应用已提议的变更到知识库。

    当作者确认要执行某项提议的变更时使用。变更状态从 proposed 变为 applied，
    并将 new_value 写入对应的知识库对象。

    Prerequisites:
    - 变更必须处于 proposed 状态

    Args:
        change_id: 变更提议的 ID
    """
```

**实现逻辑:**
1. `kb.changes.get(change_id)` 获取变更记录
2. 如果返回 None（变更不存在），返回 `{"error": f"变更 ID {change_id} 不存在"}`
3. 检查 `status == "proposed"`，否则返回 `{"error": f"变更状态为「{status}」，无法应用"}`
3. 根据 `target_type` 调用对应 Store 更新:
   - `"world_setting"` → `kb.world_setting.update_by_id(target_id, new_value)`
   - `"character"` → `kb.characters.update_character(target_id, new_value)`
   - `"foreshadowing"` → `kb.foreshadowings.update(target_id, new_value)`
   - `"style"` → `kb.styles.update_constraints_by_id(target_id, new_value)`
   - `"outline"` → `kb.outlines.update(new_value)`（大纲只有一个实例，忽略 target_id）
   - `"relation"` → `kb.characters.update_relation(target_id, new_value)`
   - `"outline_adjustment"` → `kb.outlines.update(new_value)`（与 outline 同，忽略 target_id。`target_id` 固定为 0）
   - `"chapter_rewrite"` → 不执行重写（重写需要 LLM 调用），返回提示引导使用 `rewrite_chapter`
4. Store 更新成功后: `kb.changes.update(change_id, {"status": "applied", "author_decision": "proceed"})`
5. Store 更新失败时: 不更新变更状态，返回错误信息
6. 返回 `action`/`applied`/`change_id`/`target_type`/`target_id`/`message`

**注意:**
- `new_value` 是 dict（从 SettingChange 的 JSON 字段读取），直接传给 Store 更新方法
- Store 使用 `setattr(obj, key, value)` 遍历 dict，仅 ORM 模型已有的列名会持久化，非 ORM 的 key 被静默忽略（setattr 设置 Python 属性但不持久化到 DB）。调用方应确保 `new_value` 的 key 与 Store 模型列名一致
- `outline_adjustment` 由 `propose_outline_adjustment` 创建，`target_id` 固定为 0（Integer nullable=False，0 是有效 int）

### E2: 新增 `reject_change` 工具

**文件:** `backend/app/agents/tools/modification/reject_change.py`（新建）

```python
@tool
async def reject_change(change_id: int, reason: str = "") -> dict:
    """拒绝已提议的变更。

    当作者决定不执行某项提议的变更时使用。变更状态从 proposed 变为 abandoned。

    Args:
        change_id: 变更提议的 ID
        reason: 拒绝原因（可选）
    """
```

实现:
1. `kb.changes.get(change_id)` → 如果 None 返回错误 → 检查 status == proposed
2. 更新: `{"status": "abandoned", "author_decision": "abandon"}`
3. 有 reason 时追加到 description: `existing_desc + f" | 拒绝原因: {reason}"`
4. `kb.changes.update(change_id, update_data)`
5. 返回 `action`/`rejected`/`change_id`/`target_type`/`reason`/`message`

### E3: 新增 `list_proposed_changes` 工具

**文件:** `backend/app/agents/tools/modification/list_proposed_changes.py`（新建）

```python
@tool
async def list_proposed_changes(target_type: str = "all") -> dict:
    """列出待决策的变更提议。

    当作者需要查看所有待处理的变更提议时使用。返回 proposed 状态的变更列表。

    Args:
        target_type: 筛选类型 - "world_setting", "character", "foreshadowing",
                     "style", "outline", "relation", "outline_adjustment",
                     "chapter_rewrite", 或 "all"
    """
```

实现:
1. `kb.changes.list_changes(status="proposed")`
2. 按 `target_type` 过滤（非 all 时）
3. 每项返回 `id`/`target_type`/`target_id`/`description[:80]`/`impact_report.level`/`created_at`
4. 返回 `total`/`changes`/`message`

### E4: 更新 `expand_world_setting` 走变更提议流程

**文件:** `backend/app/agents/tools/assist/expand_world_setting.py`

**源码现状（关键修正）:** v2 spec 描述源码有 `if impact_level != "severe"` 的条件判断，但实际源码中 **没有这个判断**。源码是无条件写入数据库:

```python
# 实际源码 — 无条件写入
kb.world_setting.update_by_id(ws["id"], {"tiered_settings": updated_tiered})

return {
    ...
    "written": True,
    ...
}
```

**要求:**
1. 在写入之前新增 severity 判断:
```python
if impact_level == "severe":
    # 创建变更提议，不直接写入
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

2. 更新 docstring: 增加说明"与🔴设定冲突时自动创建变更提议而非直接写入，需用 apply_change 或 reject_change 决策"

### E5: 更新注册表和导出

**文件:** `backend/app/agents/tools/modification/__init__.py`、`backend/app/agents/tools/registry.py`、`backend/app/agents/tools/__init__.py`、`backend/app/agents/agent_tools.py`

**要求:**
1. `modification/__init__.py` 新增导出 `apply_change`、`reject_change`、`list_proposed_changes`
2. `registry.py` 中将三个新工具加入 `_STRUCTURE_EXTRA` 列表（结构阶段及以上可用）
3. `tools/__init__.py` 修改工具导入区新增三个工具
4. `agent_tools.py` 兼容层新增三个工具的导入

**验证:** `docker exec novelagent-backend-1 pytest -v`，特别是 `test_agent_tools.py` 的子集关系测试

---

## 模块 F: 一致性检测增强

### F1: `consistency_scan` 增加情绪凝固检测

**文件:** `backend/app/agents/tools/perception/consistency_scan.py`

**要求:** 在现有情绪跳跃检测之后，新增全局情绪凝固检测:

遍历 `sorted_chapters` 中连续的 `emotion_tag`，如果同一 tag 持续 5+ 章未变化:
```python
consecutive_same_emotion = 1
stagnant_entries = [sorted_chapters[0]] if sorted_chapters else []
for i in range(1, len(sorted_chapters)):
    if emotion_by_chapter.get(sorted_chapters[i]) == emotion_by_chapter.get(sorted_chapters[i - 1]):
        consecutive_same_emotion += 1
        stagnant_entries.append(sorted_chapters[i])
    else:
        if consecutive_same_emotion >= 5:
            tag = emotion_by_chapter[sorted_chapters[i - 1]]
            issues.append({
                "type": "emotion_stagnation",
                "chapters": stagnant_entries[:5],
                "detail": f"连续 {consecutive_same_emotion} 章情绪标签为「{tag}」，节奏可能过于单调",
                "confidence": "medium",
            })
        consecutive_same_emotion = 1
        stagnant_entries = [sorted_chapters[i]]
# 循环结束后检查最后一段
if consecutive_same_emotion >= 5:
    tag = emotion_by_chapter.get(sorted_chapters[-1], "")
    issues.append({...})
```

此检测基于全局时间线，在现有情绪跳跃检测之后添加。

### F2: 设定引用矛盾检测优化

**文件:** `backend/app/agents/tools/perception/consistency_scan.py`

**源码现状:** 用 `rule_text in ch_content` 做全文包含匹配，`len(rule_text) >= 4` 的长度过滤

**要求:**
1. 只对长度 >= 6 的规则做字符串匹配（将 `>= 4` 改为 `>= 6`）
2. 长度 4-5 的规则改用分词匹配: `tokenize_chinese(rule_text)` 后检查所有分词是否都在 `ch_content` 中出现
3. 更新 confidence: 字符串匹配为 `"low"`，分词匹配为 `"very_low"`
4. 长度 < 4 的规则不检测

**注意:** `tokenize_chinese` 使用 jieba 分词，jieba 不可用时退化为 bigram。bigram 模式下 4-5 字规则的分词结果为 3-4 个 bigram，匹配精度尚可接受

### F3: 新增 `foreshadowing` 检查类型（v3 新增）

**文件:** `backend/app/agents/tools/perception/consistency_scan.py`

**源码现状:** `check_types` 参数只支持 `"character"`、`"timeline"`、`"setting"`、`"all"`。缺少伏笔一致性检查。

**要求:**
1. `check_types` 新增 `"foreshadowing"` 选项
2. 在 `check_types in ("all", "foreshadowing")` 分支内新增伏笔一致性检测:
   - 检查是否有 planted_chapter > expected_resolve_chapter 的伏笔（数据录入错误）
   - 检查是否有 active 状态但 expected_resolve_chapter 已经过去 5+ 章的伏笔（超期伏笔）。**当前章节号**从 `scan_chapter_numbers` 的最大值推断（`max(scan_chapter_numbers)`），如果没有扫描范围则从 `timeline` 的最新条目推断。如果两者都为空则跳过超期检测
   - 检查是否有 reclaimed 状态但 resolved_chapter 为空的伏笔（数据不完整）
3. 更新 docstring 中 `check_types` 的可选值说明

---

## 模块 G: 阶段回退能力

### G1: `advance_phase` 支持 `direction` 参数

**文件:** `backend/app/agents/tools/creation/advance_phase.py`

**要求:**

1. 函数签名新增 `direction: str = "forward"`

2. docstring 更新:
```
direction: 推进方向 - "forward"(前进，默认) 或 "backward"(回退)
回退只允许退一级（WRITING→STRUCTURE、STRUCTURE→INCUBATION），REVISION 和 INCUBATION 不可回退。
```

3. 新增回退逻辑（**关键: `phase_labels` 需在回退判断之前定义**）:

```python
# 先定义 phase_labels（回退和前进都需要）
phase_labels = {
    Phase.INCUBATION: "创意孵化",
    Phase.STRUCTURE: "结构设计",
    Phase.WRITING: "写作中",
    Phase.REVISION: "修订中",
}

if direction == "backward":
    rollback_map = {
        Phase.WRITING: Phase.STRUCTURE,
        Phase.STRUCTURE: Phase.INCUBATION,
    }
    if current_phase not in rollback_map:
        return {
            "current_phase": current_phase,
            "suggested_phase": current_phase,
            "advanced": False,
            "reason": f"阶段「{current_phase}」不可回退" if current_phase == Phase.REVISION else f"孵化阶段已是初始阶段，无法回退",
        }
    suggested_phase = rollback_map[current_phase]
    reason = f"从{phase_labels[current_phase]}回退到{phase_labels[suggested_phase]}"
    advanced = True
```

4. 回退时的写入逻辑与前进完全相同（获取行锁 → 双重检查 → 更新），复用 `if advanced:` 代码块

5. 更新返回值增加 `direction` 字段

**验证:**
- `docker exec novelagent-backend-1 pytest -v`
- 需要在 `test_advance_phase.py` 中新增回退场景测试

---

## 模块 H: 工具调用时机指导

### H1: 在关键工具的 docstring 中增加 Prerequisites 段落

**涉及文件:**

| 文件 | Prerequisites |
|------|--------------|
| `creation/generate_chapter_content.py` | 本章大纲必须已确认（通过 batch_confirm_outlines）；写入正文后使用 record_chapter_meta 记录追踪数据 |
| `creation/record_chapter_meta.py` | generate_chapter_content 已写入章节正文 |
| `creation/generate_chapter_outline.py` | generate_outline 已创建总大纲 |
| `creation/rewrite_chapter.py` | 先 review_chapter 获取审查结果 |
| `creation/check_chapter_transition`（perception） | 第 N-1 章已有正文内容，第 N 章已有大纲 |
| `modification/propose_setting_change.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `modification/propose_outline_adjustment.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `modification/propose_chapter_rewrite.py` | 变更提议后需 apply_change 或 reject_change 决策 |
| `assist/expand_world_setting.py` | 与🔴设定冲突时自动创建变更提议，需 apply_change 或 reject_change 决策 |
| `creation/advance_phase.py` | direction="forward" 前进（默认），direction="backward" 回退只允许退一级 |
| `creation/batch_confirm_outlines.py` | 需先 generate_chapter_outline 创建章节大纲 |

**要求:** 在每个工具的 docstring 描述段落末尾，增加格式统一的 Prerequisites 块

**验证:** 每个修改的 docstring 中都包含 `Prerequisites:` 关键词

---

## 模块 I: 缓存性能优化

### I1: `ToolResultCache` 增加前缀索引

**文件:** `backend/app/agents/tools/cache.py`

**源码现状:** `invalidate_by_prefix` 每次扫描全部 cache key（8 个前缀 × N 个缓存项）。`invalidate` 也用 `startswith` 扫描。

**要求:**

1. 新增 `_prefix_index: dict[str, set[str]]` 属性，key 为工具名（如 `"knowledge_search"`），value 为以该工具名为前缀的 cache key 集合

2. `set` 方法同时更新 `_prefix_index`:
```python
def set(self, tool_name: str, params: dict, result: Any) -> None:
    key = self._key(tool_name, params)
    self._cache[key] = result
    if tool_name not in self._prefix_index:
        self._prefix_index[tool_name] = set()
    self._prefix_index[tool_name].add(key)
```

3. `invalidate` 方法改为基于索引:
```python
def invalidate(self, tool_name: str) -> None:
    keys_to_remove = self._prefix_index.pop(tool_name, set())
    for k in keys_to_remove:
        self._cache.pop(k, None)
```

4. `invalidate_by_prefix` 改为基于索引:
```python
def invalidate_by_prefix(self, prefixes: list[str]) -> None:
    for prefix in prefixes:
        # 统一处理: prefix 可能是 "tool_name:" 或 "tool_name"
        tool_name = prefix.rstrip(":")
        keys_to_remove = self._prefix_index.pop(tool_name, set())
        for k in keys_to_remove:
            self._cache.pop(k, None)
```

5. `clear` 方法同时清空 `_prefix_index`

**验证:**
- `docker exec novelagent-backend-1 pytest -v`
- 新增 `backend/tests/test_tool_cache.py`，覆盖: 缓存命中/未命中、invalidate、invalidate_by_prefix、clear、前缀索引一致性、invalidate 不存在的工具不报错

---

## 模块 J: 伏笔建议精度提升

### J1: `suggest_foreshadowing` 增加停用词过滤

**文件:** `backend/app/agents/tools/assist/suggest_foreshadowing.py`

**源码现状:** `tokenize_chinese` 分词后统计词频 ≥ 2 次且长度 ≥ 3 就标记为"未解释现象"，但产生大量噪音（如"一个人"、"这件事"）

**要求:**

1. 新增局部停用词集合:
```python
_SUGGEST_STOPWORDS = {
    "一个人", "这件事", "那个", "这个", "什么", "怎么", "已经",
    "可以", "不是", "没有", "知道", "看到", "就是", "还是",
    "一个", "自己", "他们", "我们", "你们", "她们", "这里",
    "那里", "这些", "那些", "一样", "时候", "地方", "东西",
    "这样", "那样", "如何", "为什么", "因为", "所以", "但是",
    "而且", "或者", "如果", "虽然", "不过", "然后", "于是",
}
```

2. 过滤逻辑改为:
```python
for word, freq in sorted(word_freq.items(), key=lambda x: -x[1]):
    if (freq >= 3  # 阈值 2 → 3
        and len(word) >= 4  # 阈值 3 → 4
        and word not in _SUGGEST_STOPWORDS
        and word not in tracked_contents):
        unexplained.append({"element": word, "occurrences": freq})
        if len(unexplained) >= 3:
            break
```

3. `tokenize_chinese` 退化分支说明: 当 jieba 不可用时退化为 bigram，bigram 模式下词长固定为 2，`len(word) >= 4` 条件永远不满足。此时应降级为 `len(word) >= 2 and freq >= 5`:
```python
min_len = 4 if _jieba_available else 2
min_freq = 3 if _jieba_available else 5

for word, freq in sorted(word_freq.items(), key=lambda x: -x[1]):
    if (freq >= min_freq
        and len(word) >= min_len
        and word not in _SUGGEST_STOPWORDS
        and word not in tracked_contents):
        ...
```

4. 更新 docstring 说明检测逻辑变更

**验证:** `docker exec novelagent-backend-1 pytest -v`

---

## 测试要求

### 必跑测试

每次改动后运行:
```bash
docker exec novelagent-backend-1 pytest -v
```

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

---

## 修改后必须重建

所有改动均在 backend Python 代码，不涉及依赖变更或数据库模型变更:
```bash
docker compose restart backend
```

---

## 风险与约束

1. **不改变 Store 层接口** — 所有改动在工具层和辅助层完成
2. **不改变数据库模型** — SettingChange 已支持 applied/abandoned 状态，无需 alembic
3. **向后兼容** — `generate_chapter_content` 删除废弃参数后，旧调用方式会报错，这是预期行为（之前有重复写入风险）
4. **阶段工具递进关系** — 新增 3 个闭环工具加入 `_STRUCTURE_EXTRA`，保证 INCUBATION ⊆ STRUCTURE ⊆ WRITING ⊆ REVISION
5. **兼容层更新** — `agent_tools.py` 是旧导入路径的兼容层，新增工具必须同步更新
6. **chapter_rewrite 的 apply_change 特殊处理** — 不直接 apply，引导使用 `rewrite_chapter`
7. **outline_adjustment 的 apply_change 处理** — `target_id` 固定为 0，apply 时直接调用 `kb.outlines.update()`
8. **apply_change 的 new_value 语义** — `new_value` 的 key 应与 Store 模型列名一致，否则被 setattr 静默忽略
9. **knowledge_search 重构风险** — C1 将平铺 if 结构重构为步骤列表+循环，必须确保单个 target 查询行为不变
10. **expand_world_setting 写入逻辑修正** — E4 需新增 severity 判断（源码当前无条件写入），这是新增条件分支而非修改现有逻辑，回归风险低
11. **tokenize_chinese 退化模式** — J1 和 F2 都依赖 `tokenize_chinese`，jieba 不可用时退化为 bigram，阈值需适配
12. **phase_labels 作用域** — G1 需将 `phase_labels` 定义提前到回退逻辑之前，当前源码中它在行锁代码之后，需确认提前不影响其他逻辑
13. **Hook 链兼容性** — B1 删除追踪参数后，`hooks.py` 中 `generate_chapter_content` 的 post hooks 仍依赖 `chapter_number` 字段，确认该字段在返回值中保留
