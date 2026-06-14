# Agent 工具全面优化设计文档

> 日期：2026-06-14
> 范围：`backend/app/agents/tools/` 全部 31 个工具 + 注册表 + 支撑模块
> 目标：修复数据安全缺陷、补齐核心能力、提升效率体验、演进架构

---

## 一、背景与问题总览

NovelAgent v0.8.11 的 Agent 工具体系包含 31 个工具，分布在 4 个目录（perception/creation/modification/assist），通过 `registry.py` 按阶段注册。经过对全部源码的深度审查，发现以下四类问题：

| 层级 | 核心问题 | 影响 |
|------|----------|------|
| P0 数据安全 | 静默吞异常、事务竞争、工具重叠、解析分散 | 追踪数据丢失、并发阶段倒退、Agent 选择混乱 |
| P1 能力缺失 | 无更新/删除工具、无全书扫描、无衔接检查、章节工具职责过重 | Agent 无法修改已有内容、长篇一致性失控、衔接断裂、参数出错率高 |
| P2 效率体验 | docstring 中英混杂、降级全量返回、感知工具无可操作性 | Agent 工具选择准确率低、token 浪费、需额外轮次才能行动 |
| P3 架构演进 | 静态注册、全量注入上下文、无自动触发链、无缓存 | 工具数量膨胀后选择噪音大、system prompt token 浪费、易遗漏检查 |

---

## 二、P0 — 数据安全与正确性

### 2.1 `generate_chapter_content` 异常处理

**文件**：`tools/creation/generate_chapter_content.py`
**问题**：第 148-181 行有 4 处 `except Exception: pass`，分别覆盖时间线创建、伏笔创建、伏笔回收、风格快照。任何一步失败后章节仍被标记为已保存，但追踪数据静默丢失。

**修复方案**：
- 每个 `except` 捕获具体异常并记录到返回结果的 `warnings` 列表
- 返回结构新增 `warnings: list[dict]`，每项包含 `{step, error, detail}`
- 如果时间线创建失败：`timeline_entry` 标记为 `false`，`timeline_error` 包含错误信息
- 伏笔创建/回收失败：`new_foreshadowings` / `reclaimed_foreshadowings` 中标记失败项
- 风格快照失败：`style_snapshot_created` 标记为 `false`，`style_snapshot_error` 包含错误信息

**修改后的返回结构**：
```python
{
    "action": "created" | "updated",
    "chapter_number": int,
    "title": str,
    "word_count": int,
    "timeline_entry": bool,
    "timeline_error": str | None,        # 新增
    "new_foreshadowings": int,
    "new_foreshadowing_errors": list,     # 新增
    "reclaimed_foreshadowings": int,
    "reclaim_errors": list,               # 新增
    "style_snapshot_created": bool,
    "style_snapshot_error": str | None,   # 新增
    "warnings": list[dict],               # 新增：汇总所有失败步骤
    "message": str,
}
```

### 2.2 `advance_phase` 事务合并

**文件**：`tools/creation/advance_phase.py`
**问题**：第 39-50 行读阶段用 Session A，第 90-103 行写阶段用 Session B，两次独立 `SessionLocal()` 之间无事务保护。

**修复方案**：
- 合并为单次 Session，在同一事务中完成读取+判断+写入
- 使用 `with_for_update()` 行锁防止并发推进
- 如果写入失败，整体回滚，`current_phase` 保持不变

```python
db = SessionLocal()
try:
    ws = db.query(WorkflowState).filter(
        WorkflowState.project_id == project_id
    ).with_for_update().first()
    current_phase = ws.stage if ws else Phase.INCUBATION
    # ... 判断逻辑 ...
    if advanced:
        ws.stage = suggested_phase
        db.commit()
finally:
    db.close()
```

### 2.3 合并 `report_progress` / `progress_report`

**文件**：`tools/assist/report_progress.py` + `tools/perception/progress_report.py` + `registry.py`
**问题**：两个工具功能重叠，Agent 选择时容易混淆。

**修复方案**：
- 保留 `progress_report`（功能更完整），删除 `report_progress`
- 在 `progress_report` 中新增 `detail_level` 参数：
  - `"brief"`：仅返回进度百分比和消息（原 `report_progress` 的功能）
  - `"full"`：返回完整统计+完稿预估+里程碑（现有功能）
- 默认值 `"full"`，保持向后兼容
- 从 `registry.py` 所有阶段的工具列表中移除 `report_progress`
- 从 `tools/assist/__init__.py` 中移除导出

**修改后的 `progress_report` 签名**：
```python
@tool
async def progress_report(detail_level: str = "full") -> dict:
    """生成写作进度报告。

    brief 模式返回进度概要，full 模式返回完整统计和完稿预估。

    Args:
        detail_level: 报告详细度 - "brief"（概要）或 "full"（完整统计）
    """
```

### 2.4 统一 JSON 字符串参数解析

**文件**：`tools/utils.py` + 13 个接受 JSON 字符串参数的工具
**问题**：每个工具各自写 `try/except JSONDecodeError`，解析失败时行为不一致。

**修复方案**：

在 `tools/utils.py` 新增统一解析函数：
```python
def parse_json_param(value: str | list | dict, default, param_name: str = "") -> tuple[Any, str | None]:
    """解析 JSON 字符串参数，返回 (解析结果, 警告信息)

    如果 value 已经是目标类型（list/dict），直接返回。
    如果解析失败，返回 default 和警告信息。

    Args:
        value: 输入值（可能是 JSON 字符串或已是目标类型）
        default: 解析失败时的默认返回值
        param_name: 参数名（用于警告信息）
    """
    if isinstance(value, type(default)):
        return value, None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, type(default)):
                return parsed, None
            warning = f"参数 {param_name} JSON 解析类型不匹配，使用默认值"
            return default, warning
        except json.JSONDecodeError as e:
            warning = f"参数 {param_name} JSON 解析失败({e})，使用默认值"
            return default, warning
    return default, f"参数 {param_name} 类型不支持，使用默认值"
```

受影响的 13 个工具（全部替换为调用 `parse_json_param`）：
- `create_world_setting`：`tiered_settings`, `key_locations`
- `generate_world_setting_complete`：`red_rules`, `yellow_rules`, `green_rules`, `key_locations`
- `create_style_constraints`：`taboo_words`, `forbidden_patterns`, `abstract_rules`
- `create_foreshadowing`：`related_characters`
- `create_plot_block`：`must_happen`, `questions_to_raise`, `questions_to_answer`
- `create_subplot`：`characters`
- `generate_chapter_content`：`new_foreshadowings`, `reclaimed_foreshadowing_ids`
- `generate_chapter_outline`：`key_scenes`

解析警告汇总到返回结果的 `param_parse_warnings` 字段中。

---

## 三、P1 — 核心能力缺失

### 3.1 新增更新/删除工具

Store 层已有 `update_character`、`update_plot_block`、`delete_plot_block`、`update_subplot`、`delete_subplot`、`update_plot_question`、`update_foreshadowing` 等方法，但工具层只有创建和提议变更。

**新增 6 个工具文件**：

| 工具名 | 文件 | 功能 | 阶段 |
|--------|------|------|------|
| `update_character` | `tools/creation/update_character.py` | 修改角色属性 | STRUCTURE, WRITING |
| `update_plot_block` | `tools/creation/update_plot_block.py` | 调整情节块范围/必须事件 | STRUCTURE, WRITING |
| `update_subplot` | `tools/creation/update_subplot.py` | 更新支线状态 | WRITING |
| `update_plot_question` | `tools/creation/update_plot_question.py` | 标记问题为已回答 | STRUCTURE, WRITING |
| `update_foreshadowing` | `tools/creation/update_foreshadowing.py` | 推进伏笔状态 | WRITING |
| `delete_plot_block` | `tools/creation/delete_plot_block.py` | 删除空情节块 | STRUCTURE |

**设计原则**：
- 更新工具只修改传入的字段（部分更新），不覆盖未传入的字段
- 删除工具增加安全检查：有子实体的（情节块下有问题/伏笔）拒绝删除，提示先迁移
- 所有工具返回变更前后对比（`before` / `after`），方便 Agent 判断和用户审核

**`update_character` 签名示例**：
```python
@tool
async def update_character(
    character_id: int,
    name: str = "",
    role: str = "",
    personality: str = "",
    catchphrase: str = "",
    habit_action: str = "",
    deep_fear: str = "",
    core_motivation: str = "",
    growth_arc: str = "",
    appearance: str = "",
    backstory: str = "",
    signature_item: str = "",
) -> dict:
    """更新已有角色的属性。只修改传入的非空字段。

    Args:
        character_id: 角色 ID
        name: 角色名（留空不修改）
        ... 其余字段留空不修改
    """
```

**`update_foreshadowing` 签名示例**：
```python
@tool
async def update_foreshadowing(
    foreshadowing_id: int,
    level: str = "",
    status: str = "",
    content: str = "",
    expected_resolve_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。用于推进伏笔等级或标记回收。

    Args:
        foreshadowing_id: 伏笔 ID
        level: 新等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)，留空不修改
        status: 新状态 - "active", "pending_reclaim", "reclaimed"，留空不修改
        content: 伏笔内容，留空不修改
        expected_resolve_chapter: 预期回收章节号，None 不修改
    """
```

### 3.2 新增 `consistency_scan` 全书一致性扫描

**文件**：`tools/perception/consistency_scan.py`
**问题**：`consistency_check` 只能两章比对，无法全书扫描。

**设计方案**：
- 扫描所有已有章节，构建角色出场索引和设定引用索引
- 规则扫描，不调用 LLM
- 检测三类矛盾：
  1. **角色行为矛盾**：同一角色在不同章节的 `emotion_tag` 跳跃（如上一章"悲痛"，下一章无解释地"欢快"）
  2. **时间线矛盾**：时间线条目中 `chapter_number` 顺序与 `causal_chain` 描述矛盾
  3. **设定引用矛盾**：章节中引用了红色设定（tiered_settings.red）但不满足设定前提
- 返回疑似矛盾列表，每项包含 `{type, chapters, detail, confidence}`
- 注册到 WRITING 和 REVISION 阶段

```python
@tool
async def consistency_scan(
    check_types: str = "all",
    max_issues: int = 20,
) -> dict:
    """全书一致性扫描。自动检测角色行为矛盾、时间线矛盾和设定引用矛盾。

    不调用 LLM，纯规则扫描。适合长篇小说（20+ 章）定期检查。

    Args:
        check_types: 检查类型 - "character"(角色), "timeline"(时间线),
                     "setting"(设定), 或 "all"
        max_issues: 最多返回的矛盾数量（默认 20）
    """
```

### 3.3 新增 `check_chapter_transition` 章节衔接检查

**文件**：`tools/perception/check_chapter_transition.py`
**问题**：Agent 写第 N 章时没有工具检查第 N-1 章结尾和第 N 章开头的衔接性。

**设计方案**：
- 输入：`chapter_number`（要写的章节号）
- 读取第 N-1 章的结尾 500 字和情绪/场景状态
- 读取第 N 章的大纲开场信息（scene, opening_state, characters）
- 检测三种断裂：
  1. **情绪跳跃**：上一章结尾 `emotion_tag` 与当前章大纲 `emotional_arc` 起点不连续
  2. **场景不连续**：上一章结尾的场景与当前章大纲 `scene` 无过渡
  3. **角色凭空变化**：上一章末出场的角色在当前章大纲中凭空消失，或新角色凭空出现
- 返回衔接评估 + 建议过渡方式
- 注册到 WRITING 阶段

```python
@tool
async def check_chapter_transition(chapter_number: int) -> dict:
    """检查章节间的衔接连贯性。分析上一章结尾和当前章大纲开场是否连贯。

    Args:
        chapter_number: 当前章节号（将检查第 N-1 章到第 N 章的衔接）
    """
```

### 3.4 拆分 `generate_chapter_content`

**文件**：`tools/creation/generate_chapter_content.py` + 新文件 `tools/creation/record_chapter_meta.py`
**问题**：一个工具 17 个参数，承担 5 个职责。

**设计方案**：

**Step 1**：新增 `record_chapter_meta` 工具：
```python
@tool
async def record_chapter_meta(
    chapter_number: int,
    timeline_summary: str = "",
    causal_chain: str = "",
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str = "",
    new_foreshadowings: str = "[]",
    reclaimed_foreshadowing_ids: str = "[]",
) -> dict:
    """记录章节的追踪元数据（时间线、伏笔、节奏评分等）。

    在 generate_chapter_content 保存章节正文后调用此工具补充追踪数据。
    也可以单独调用以补录遗漏的追踪数据。

    Args:
        chapter_number: 章节号
        timeline_summary: 时间线摘要
        causal_chain: 因果链描述
        rhythm_score: 节奏评分 1-5
        tension_score: 张力评分 1-5
        emotion_score: 情感评分 1-5
        emotion_tag: 情绪标签
        new_foreshadowings: JSON 字符串列表，本章新埋的伏笔
        reclaimed_foreshadowing_ids: JSON 字符串列表，本章回收的伏笔 ID
    """
```

**Step 2**：精简 `generate_chapter_content`：
- 核心参数：`chapter_number`, `chapter_title`, `content`, `summary`, `word_count`, `status`, `scene_count`
- 移除：`new_foreshadowings`, `reclaimed_foreshadowing_ids`, `timeline_summary`, `rhythm_score`, `tension_score`, `emotion_score`, `emotion_tag`
- 内部仍然自动创建风格快照（这是纯统计计算，不需要 Agent 手动输入）
- **向后兼容**：如果 Agent 传入了旧的伏笔/时间线参数，内部自动调用 `record_chapter_meta` 逻辑

**Step 3**：注册表更新：
- `record_chapter_meta` 注册到 WRITING 阶段

---

## 四、P2 — 效率与体验优化

### 4.1 工具 docstring 中文化

**文件**：全部 31 个工具文件 + 6 个新增工具
**问题**：docstring 用英文写，但系统是中文创作场景，Agent 工具选择准确率受影响。

**修改规则**：
- 工具 `description`（`@tool` 下第一段）统一改为中文
- `Args` 中参数描述改为中文
- 参数名、类型保持英文
- 示例值保持中文

**修改前后对比**：
```python
# Before
@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """Search the knowledge base for specific information.

    Use when the user asks about any aspect of the novel's settings,
    characters, plot, or style.

    Args:
        query: Natural language search query
        target: Which part to search - "world_setting", "characters", ...
    """

# After
@tool
async def knowledge_search(query: str, target: str = "all") -> dict:
    """搜索知识库中的特定信息。

    当用户询问小说的设定、角色、情节、风格等任何方面时使用。
    优先使用语义检索，不可用时降级为关键词匹配。

    Args:
        query: 自然语言搜索查询（如"主角的魔法限制"、"世界观核心规则"）
        target: 搜索范围 - "world_setting"(世界观), "characters"(角色),
                "foreshadowing"(伏笔), "timeline"(时间线), "plot"(情节),
                "style"(风格), 或 "all"(全部)
    """
```

### 4.2 `knowledge_search` 降级截断

**文件**：`tools/perception/knowledge_search.py`
**问题**：语义检索不可用时降级为全量 DB 查询，token 开销巨大。

**修复方案**：
- 降级路径每种子类型最多返回 5 条
- 返回结果增加 `truncated: true` 标记
- 关键词匹配使用 `_tokenize_chinese` 替代空格分词
- 如果 `target="all"` 且数据量大，建议 Agent 使用精确 `target` 参数

### 4.3 `consistency_check` 精确加载

**文件**：`tools/perception/consistency_check.py`
**问题**：每次检查都加载全部角色的 `knowledge_boundary`。

**修复方案**：
- 先用 `_extract_names` 从两章内容中提取出场角色名
- 只加载出场角色的约束信息
- 未出场角色的约束不加载，减少 token 噪音

### 4.4 感知工具增加可操作性建议

**文件**：`tools/perception/style_analysis.py` + `tools/perception/rhythm_analysis.py`

**`style_analysis` 增强**：
- 返回新增 `suggested_fixes: list[dict]`
- 每项包含 `{issue, suggestion, priority}`
- 示例：`{"issue": "最近3章对话比例0.45，整体平均0.25", "suggestion": "建议增加叙述和动作描写降低对话比例", "priority": "medium"}`

**`rhythm_analysis` 增强**：
- 返回新增 `suggested_adjustments: list[dict]`
- 单调段建议：`{"type": "单调段打破", "chapters": "8-10", "suggestion": "建议第11章加入冲突或转折事件"}`
- 偏差建议：`{"type": "节奏偏差", "chapter": 5, "suggestion": "情节块预期'紧张'但实际张力2分，建议增加紧迫感事件"}`

### 4.5 建议工具质量提升

**文件**：`tools/assist/suggest_foreshadowing.py` + `tools/assist/suggest_plot_twist.py`

**`suggest_foreshadowing` 增强**：
- 新增"未解释现象"扫描：读取最近 3 章内容，提取出现了但未在伏笔表中追踪的神秘元素（物品/人物/事件）
- 建议格式增加 `reasoning` 字段，解释为什么这是一个好的伏笔位置

**`suggest_plot_twist` 增强**：
- 分析所有主要角色的动机冲突（不限于第一个）
- 返回前 3 个最有反转潜力的角色，每个附带具体反转方向
- 新增"读者预期反转"：基于活跃伏笔的预期方向，建议相反方向的反转

### 4.6 批量操作工具

**新增 2 个工具文件**：

| 工具名 | 文件 | 功能 | 阶段 |
|--------|------|------|------|
| `batch_confirm_outlines` | `tools/creation/batch_confirm_outlines.py` | 批量确认章节大纲 | STRUCTURE |
| `batch_update_foreshadowing_status` | `tools/creation/batch_update_foreshadowing_status.py` | 批量更新伏笔状态 | WRITING |

**`batch_confirm_outlines`**：
```python
@tool
async def batch_confirm_outlines(chapter_numbers: str) -> dict:
    """批量确认章节大纲。将指定章节的大纲标记为已确认，使其可以开始写作。

    Args:
        chapter_numbers: JSON 字符串列表，要确认的章节号列表（如 "[1,2,3]"）
    """
```

**`batch_update_foreshadowing_status`**：
```python
@tool
async def batch_update_foreshadowing_status(updates: str) -> dict:
    """批量更新伏笔状态。适用于一次性推进多个伏笔的等级或回收状态。

    Args:
        updates: JSON 字符串列表，每项包含 {"id": int, "level": str, "status": str}
                 level 可选值：hint, strengthened, revealed
                 status 可选值：active, pending_reclaim, reclaimed
    """
```

---

## 五、P3 — 架构演进

### 5.1 动态工具注册表

**文件**：`tools/registry.py` 重构
**问题**：静态列表无法根据项目状态调整工具组合。

**设计方案**：
```python
class ToolRegistry:
    """动态工具注册表"""

    def __init__(self, project_id: int, phase: str):
        self.project_id = project_id
        self.phase = phase

    def get_tools(self) -> list:
        """根据项目规模和阶段动态返回工具列表"""
        base_tools = _PHASE_BASE_TOOLS[self.phase]

        # 根据项目规模裁剪
        kb = KnowledgeBaseService(self.project_id)
        outline = kb.outlines.get()
        total_chapters = 0
        if outline:
            total_chapters = outline.get("chapter_count_confirmed") or outline.get("chapter_count_suggested") or 0

        # 大型项目：启用高级感知工具
        if total_chapters >= 20:
            base_tools = base_tools + _LARGE_PROJECT_TOOLS

        # 小型项目：禁用部分工具减少噪音
        if total_chapters <= 10:
            base_tools = [t for t in base_tools if t.name not in _SMALL_PROJECT_EXCLUDE]

        return base_tools
```

**阶段基线工具**（保持 `INCUBATION ⊆ STRUCTURE ⊆ WRITING` 递进关系）：
- `_PHASE_BASE_TOOLS` 替代现有 `INCUBATION_TOOLS` / `STRUCTURE_TOOLS` / `WRITING_TOOLS`
- `_LARGE_PROJECT_TOOLS`：`consistency_scan`, `check_chapter_transition`
- `_SMALL_PROJECT_EXCLUDE`：`rhythm_analysis`（章节太少无意义）

**兼容性**：
- 保留 `INCUBATION_TOOLS` / `STRUCTURE_TOOLS` / `WRITING_TOOLS` 作为常量（向后兼容测试）
- `create_agent_graph` 改为调用 `ToolRegistry.get_tools()`
- 新增 `project_id` 参数传递

### 5.2 上下文按需检索

**文件**：`agents/agent_context.py` + `agents/agent_graph.py`
**问题**：`build_agent_context` 把所有相关数据塞进 system prompt，token 利用率低。

**设计方案**：

**Phase 1 — 精简 system prompt**：
- system prompt 只包含核心索引：
  - 角色名+ID 列表（不包含完整 backstory）
  - 大纲标题+总章数
  - 当前阶段 + 当前章节号
  - 关键红色设定（最多 3 条）
- 预期从 ~12K token 降到 ~3K token

**Phase 2 — 增强 knowledge_search**：
- Agent 按需查询详细信息
- 增加快捷查询模式：`target="current_chapter"` 一次返回当前章所需的全部上下文

**Phase 3 — 预取优化**：
- `build_agent_context` 返回轻量索引
- 写作阶段自动预取当前章节大纲 + 上一章结尾（这两项几乎每次都需要）
- 其余数据按需检索

### 5.3 工具调用后自动触发链

**文件**：新增 `tools/hooks.py` + 修改 `agents/agent_graph.py`
**问题**：写完章节后需手动调用感知工具检查，容易遗漏。

**设计方案**：
```python
# tools/hooks.py

TOOL_HOOKS: dict[str, list[str]] = {
    "generate_chapter_content": ["foreshadowing_check", "style_analysis"],
}

async def run_post_hooks(tool_name: str, tool_result: dict, project_id: int) -> dict:
    """工具调用后的自动检查链

    仅在工具成功时触发。检查结果附在 tool_result 的 auto_check_results 中。
    严重问题生成 warning 事件。
    """
    hooks = TOOL_HOOKS.get(tool_name, [])
    if not hooks:
        return tool_result

    auto_results = {}
    for hook_name in hooks:
        try:
            hook_fn = _HOOK_FUNCTIONS[hook_name]
            result = await hook_fn(project_id, tool_result)
            auto_results[hook_name] = result
            # 严重问题 → warning 事件
            if result.get("warning"):
                # 通过 contextvars 或回调通知 SSE 流
                pass
        except Exception:
            pass  # hook 失败不影响主流程

    tool_result["auto_check_results"] = auto_results
    return tool_result
```

**Hook 实现为轻量版**：
- `foreshadowing_check` hook：只检查超期伏笔，不返回完整列表
- `style_analysis` hook：只比较最近 3 章的对话比和句长，不返回完整统计

**集成方式**：
- 在 `create_react_agent` 的 tool 调用回调中，对匹配 `TOOL_HOOKS` 的工具自动执行 hook
- 使用 LangGraph 的 `tool_node` 后置处理

### 5.4 工具结果缓存

**文件**：新增 `tools/cache.py`
**问题**：多个感知工具在同一轮对话中被重复调用，每次都全量查询 DB。

**设计方案**：
```python
# tools/cache.py

import hashlib
import json
from typing import Any

class ToolResultCache:
    """单次 SSE 请求内的工具结果缓存

    以 (tool_name, params_hash) 为 key，缓存感知工具的结果。
    写入类工具调用后自动使相关缓存失效。
    请求结束自动清理。
    """

    def __init__(self):
        self._cache: dict[str, Any] = {}

    def _key(self, tool_name: str, params: dict) -> str:
        params_json = json.dumps(params, sort_keys=True, ensure_ascii=False)
        params_hash = hashlib.md5(params_json.encode()).hexdigest()[:8]
        return f"{tool_name}:{params_hash}"

    def get(self, tool_name: str, params: dict) -> Any | None:
        return self._cache.get(self._key(tool_name, params))

    def set(self, tool_name: str, params: dict, result: Any) -> None:
        self._cache[self._key(tool_name, params)] = result

    def invalidate(self, tool_name: str) -> None:
        """使某工具的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"{tool_name}:")]
        for k in keys_to_remove:
            del self._cache[k]

    def invalidate_by_pattern(self, patterns: list[str]) -> None:
        """使匹配模式的缓存失效（如 creation 类工具写入后使 perception 缓存失效）"""
        keys_to_remove = []
        for k in self._cache:
            for pattern in patterns:
                if k.startswith(pattern):
                    keys_to_remove.append(k)
                    break
        for k in keys_to_remove:
            del self._cache[k]
```

**缓存策略**：
- 感知工具（perception/）结果可缓存，TTL = 请求生命周期
- 创作工具（creation/）调用后使全部 perception 缓存失效
- 修改工具（modification/）调用后使 perception + creation 缓存失效
- 辅助工具（assist/）结果不缓存（每次可能不同）

**集成方式**：
- 通过 `tool_context.py` 的 ContextVar 传递缓存实例
- SSE 请求开始时创建缓存，结束时清理
- 感知工具在查询 DB 前检查缓存

---

## 六、注册表变更汇总

### 新增工具（11 个）

| 工具名 | 类别 | 阶段 | 对应 Spec |
|--------|------|------|-----------|
| `update_character` | creation | STRUCTURE, WRITING | 3.1 |
| `update_plot_block` | creation | STRUCTURE, WRITING | 3.1 |
| `update_subplot` | creation | WRITING | 3.1 |
| `update_plot_question` | creation | STRUCTURE, WRITING | 3.1 |
| `update_foreshadowing` | creation | WRITING | 3.1 |
| `delete_plot_block` | creation | STRUCTURE | 3.1 |
| `consistency_scan` | perception | WRITING, REVISION | 3.2 |
| `check_chapter_transition` | perception | WRITING | 3.3 |
| `record_chapter_meta` | creation | WRITING | 3.4 |
| `batch_confirm_outlines` | creation | STRUCTURE | 4.6 |
| `batch_update_foreshadowing_status` | creation | WRITING | 4.6 |

### 删除工具（1 个）

| 工具名 | 原因 | 替代 |
|--------|------|------|
| `report_progress` (assist) | 与 progress_report 重叠 | progress_report(detail_level="brief") |

### 修改工具（15 个）

| 工具名 | 修改内容 | 对应 Spec |
|--------|----------|-----------|
| `generate_chapter_content` | 异常处理+拆分参数 | 2.1, 3.4 |
| `advance_phase` | 事务合并 | 2.2 |
| `progress_report` | 新增 detail_level 参数 | 2.3 |
| 13 个含 JSON 参数的工具 | 统一 parse_json_param | 2.4 |
| `knowledge_search` | 降级截断+分词优化 | 4.2 |
| `consistency_check` | 精确加载 | 4.3 |
| `style_analysis` | 增加 suggested_fixes | 4.4 |
| `rhythm_analysis` | 增加 suggested_adjustments | 4.4 |
| `suggest_foreshadowing` | 增加未解释现象扫描 | 4.5 |
| `suggest_plot_twist` | 多角色分析 | 4.5 |
| 全部工具 | docstring 中文化 | 4.1 |

### 注册表结构变更

```
INCUBATION_TOOLS:  advance_phase, knowledge_search, progress_report, expand_world_setting,
                   generate_outline, generate_story_seed, generate_world_setting_complete,
                   create_world_setting, create_character, create_relation,
                   create_evolution_plan, create_style_constraints, create_foreshadowing

STRUCTURE_TOOLS:   INCUBATION + foreshadowing_check, review_chapter, rewrite_chapter,
                   rhythm_analysis, generate_chapter_outline, propose_outline_adjustment,
                   suggest_foreshadowing, create_plot_block,
                   create_plot_question, create_subplot, create_foreshadowing,
                   update_character, update_plot_block, update_plot_question,
                   delete_plot_block, batch_confirm_outlines

WRITING_TOOLS:     STRUCTURE + consistency_check, style_analysis,
                   generate_chapter_content, record_chapter_meta,
                   propose_setting_change, propose_chapter_rewrite,
                   writer_block_assist, suggest_plot_twist,
                   create_timeline_entry,
                   consistency_scan,
                   check_chapter_transition, update_subplot,
                   update_foreshadowing, batch_update_foreshadowing_status

REVISION_TOOLS:    WRITING
```

---

## 七、实施顺序与依赖

```
Phase 1 (P0, ~2.5d) ─ 无外部依赖，可立即开始
├── 2.1 generate_chapter_content 异常处理
├── 2.2 advance_phase 事务合并
├── 2.3 合并 report_progress / progress_report
└── 2.4 统一 JSON 参数解析

Phase 2 (P1, ~6d) ─ 依赖 Phase 1 的 parse_json_param
├── 3.1 新增更新/删除工具 (6 个)
├── 3.2 consistency_scan
├── 3.3 check_chapter_transition
└── 3.4 拆分 generate_chapter_content

Phase 3 (P2, ~5d) ─ 可与 Phase 2 并行
├── 4.1 docstring 中文化 (全部工具)
├── 4.2 knowledge_search 降级截断
├── 4.3 consistency_check 精确加载
├── 4.4 感知工具可操作性建议
├── 4.5 建议工具质量提升
└── 4.6 批量操作工具

Phase 4 (P3, ~7.5d) ─ 依赖 Phase 2 的工具集稳定
├── 5.1 动态工具注册表
├── 5.2 上下文按需检索
├── 5.3 自动触发链
└── 5.4 工具结果缓存
```

---

## 八、测试策略

### P0 测试（必须覆盖）
- `generate_chapter_content`：模拟伏笔创建失败，验证 `warnings` 返回
- `advance_phase`：模拟并发推进，验证行锁生效
- `progress_report`：验证 `detail_level` 参数
- `parse_json_param`：覆盖正常/类型不匹配/解析失败三种场景

### P1 测试（必须覆盖）
- 更新/删除工具：验证部分更新不覆盖未传入字段
- `consistency_scan`：构造含矛盾的测试数据，验证检出率
- `check_chapter_transition`：验证情绪/场景/角色三种断裂检测
- `record_chapter_meta`：验证与 `generate_chapter_content` 的协同

### P2 测试
- `knowledge_search` 降级路径截断验证
- 感知工具建议可操作性验证（非空且有具体建议）
- 批量操作的原子性验证（部分失败时的处理）

### P3 测试
- `ToolRegistry` 动态裁剪验证
- 缓存命中/失效验证
- Hook 链执行和失败不影响主流程验证
