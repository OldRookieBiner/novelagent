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
# R20 修正：先通过 KB 读取完整度（独立 session），再获取行锁写入。
# 行锁持有期间只做读取确认和写入，最小化锁持有时间。

# 1. 无锁读取当前阶段 + KB 完整度判断（省略，同现有逻辑）
current_phase = ...
suggested_phase = ...

# 2. 获取行锁写入（仅当需要推进时）
if advanced:
    db = SessionLocal()
    try:
        ws = db.query(WorkflowState).filter(
            WorkflowState.project_id == project_id
        ).with_for_update().first()
        # 二次确认：获取锁后检查是否被并发推进
        actual_phase = ws.stage if ws else Phase.INCUBATION
        if actual_phase != current_phase:
            return {"advanced": False, "reason": "并发推进检测"}
        if not ws:
            ws = WorkflowState(project_id=project_id, stage=suggested_phase)
            db.add(ws)
        else:
            ws.stage = suggested_phase
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"推进阶段失败: {e}"}
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

受影响的 9 个工具、23 个 JSON 参数（全部替换为调用 `parse_json_param`）：

**注意**：`propose_setting_change` 的 `new_value` 参数解析逻辑不同（解析失败时保留原始字符串），不适用 `parse_json_param`，保持原有逻辑。
- `create_world_setting`：`tiered_settings`, `key_locations`
- `generate_world_setting_complete`：`red_rules`, `yellow_rules`, `green_rules`, `key_locations`
- `create_style_constraints`：`taboo_words`, `forbidden_patterns`, `abstract_rules`
- `create_foreshadowing`：`related_characters`
- `create_plot_block`：`must_happen`, `questions_to_raise`, `questions_to_answer`
- `create_subplot`：`characters`
- `generate_chapter_content`：`new_foreshadowings`, `reclaimed_foreshadowing_ids`
- `generate_chapter_outline`：`key_scenes`
- `generate_outline`：`plot_points`, `emotional_curve`, `characters`

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
- 删除工具增加安全检查：如果情节块下有未回答的问题（status="pending"），拒绝删除并提示先回答或迁移；已回答的问题可随情节块删除断开关联（数据库 ondelete=SET NULL）
- 所有工具返回变更前后对比（`before` / `after`），方便 Agent 判断和用户审核

**`update_character` 签名示例**：
```python
@tool
async def update_character(
    character_id: int,
    name: str | None = None,
    role: str | None = None,
    personality: str | None = None,
    catchphrase: str | None = None,
    habit_action: str | None = None,
    deep_fear: str | None = None,
    core_motivation: str | None = None,
    growth_arc: str | None = None,
    appearance: str | None = None,
    backstory: str | None = None,
    signature_item: str | None = None,
) -> dict:
    """更新已有角色的属性。None 表示不修改，传入具体值则更新。要清空字段需传入空字符串 ""。

    Args:
        character_id: 角色 ID
        name: 角色名（None 不修改，"" 清空）
        ... 其余字段同理
    """
```

**`update_foreshadowing` 签名示例**：
```python
@tool
async def update_foreshadowing(
    foreshadowing_id: int,
    level: str | None = None,
    status: str | None = None,
    content: str | None = None,
    appearance_count: int | None = None,
    expected_resolve_chapter: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
    """更新伏笔状态或属性。用于推进伏笔等级或标记回收。

    Args:
        foreshadowing_id: 伏笔 ID
        level: 新等级 - "hint"(暗示), "strengthened"(强化), "revealed"(揭示)，None 不修改
        status: 新状态 - "active", "pending_reclaim", "reclaimed"，None 不修改
        content: 伏笔内容，None 不修改
        appearance_count: 出现次数（用于判断升级：>=2 且 hint→strengthened），None 不修改
        expected_resolve_chapter: 预期回收章节号，None 不修改
        resolved_chapter: 实际回收章节号，None 不修改
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
    chapter_range: str = "recent",
    max_issues: int = 20,
) -> dict:
    """全书一致性扫描。自动检测角色行为矛盾、时间线矛盾和设定引用矛盾。

    不调用 LLM，纯规则扫描。适合长篇小说定期检查。

    Args:
        check_types: 检查类型 - "character"(角色), "timeline"(时间线),
                     "setting"(设定), 或 "all"
        chapter_range: 扫描范围 - "recent"(最近20章), "all"(全书),
                       或 JSON 列表如 "[1,5,10]" 指定章节
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
    timeline_summary: str | None = None,
    causal_chain: str | None = None,
    rhythm_score: int = 3,
    tension_score: int = 3,
    emotion_score: int = 3,
    emotion_tag: str | None = None,
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
- **向后兼容**：旧参数标记为 deprecated，内部不再执行伏笔/时间线逻辑，改为发出提示"请使用 record_chapter_meta 工具"。`record_chapter_meta` 检查该章节是否已有时间线条目，有则更新而非重复创建

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

    def invalidate_by_prefix(self, patterns: list[str]) -> None:
        """使匹配前缀的缓存失效（如 creation 类工具写入后使 perception 缓存失效）"""
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

---

## 九、审查修正附录（2026-06-14 深度审查）

> 本附录记录对全部 30+ 源码文件逐行审查后发现的 spec 缺陷与修正。
> 修正原则：从根源解决问题，不打补丁。

### R1. `_load_revision_context` 无 budget 控制（P0 级遗漏）

**发现位置**：`backend/app/agents/agent_context.py` 第 233-243 行
**问题**：`_load_revision_context` 直接塞入全量 `characters`、`foreshadowings`、`plot_questions`、`subplots`、`timeline`、`style_constraints`、`style_snapshots`，不走 `BudgetTracker`。而 `_load_writing_context` 严格按 budget 裁剪。这导致 revision 阶段上下文可能远超 token 限制，引发 LLM 截断或错误。

**修正方案**：
- 将 `_load_revision_context` 改为与 `_load_writing_context` 同等严格的 budget 控制
- revision 阶段按优先级加载：outline > characters > foreshadowings > timeline > style > snapshots
- 每个字段加载前检查 `budget.can_add()`

**影响范围**：3.4 节 `record_chapter_meta` 和 5.2 节 `上下文按需检索` 的实现需同步考虑此问题。

### R2. `report_progress` 是同步函数（P0 级遗漏）

**发现位置**：`backend/app/agents/tools/assist/report_progress.py`
**问题**：`report_progress` 定义为 `def report_progress(message, percent)`（同步），而其他所有 28 个工具都是 `async def`。LangChain 的 `@tool` 装饰器对同步和异步函数的处理不同，同步工具在 async 上下文中可能被事件循环阻塞。

**修正方案**：
- 在 2.3 节合并方案中，`progress_report` 已是 `async def`，删除 `report_progress` 后此问题自动消失
- 但需在实施计划 Task 5 中明确：删除 `report_progress` **前**确认没有代码直接调用它（而非通过 Agent tool 调用链）

### R3. `generate_chapter_content` 的 `existing_chapter` 判定逻辑错误（P0 级缺陷）

**发现位置**：`backend/app/agents/tools/creation/generate_chapter_content.py` 第 125 行
**问题**：`existing_chapter = chapter_result.get("id") is not None`。但 `ChapterStore.save_content` 始终返回包含 `id` 的 dict（新建也会 flush+refresh 获得 id），所以 `existing_chapter` 永远为 `True`，`action` 字段永远为 `"updated"`，即使实际是新建。

**修正方案**：
- `ChapterStore.save_content` 返回值新增 `is_new: bool` 字段
- 或在 `generate_chapter_content` 中通过查询章节是否已存在来判断（在保存前检查）

**影响范围**：2.1 节的返回结构需将 `action` 的判断逻辑修正为基于保存前的查询结果。

### R4. `__init__.py` 导出不一致（P1 级遗漏）

**发现位置**：多个 `__init__.py`

**问题 4a**：`tools/creation/__init__.py` 注释说"17个"但实际导出 18 个工具（遗漏了 `generate_chapter_outline`）。

**问题 4b**：`tools/__init__.py` 注释说"29 个"但实际只导出 26 个（缺少 `generate_chapter_outline`、`report_progress`、`create_timeline_entry` 三个工具的导入）。这意味着从 `app.agents.tools` 顶层包无法直接访问这三个工具。

**问题 4c**：`registry.py` 中 `INCUBATION_TOOLS` 包含 `report_progress` 和 `progress_report`，但 `tools/__init__.py` 只导入了 `report_progress`（从 assist 包），未导入 `progress_report`（从 perception 包）。而 registry.py 直接从子包导入，不受顶层 `__init__.py` 影响，所以功能不受影响。但顶层 `__init__.py` 的导出列表过时，可能误导开发者。

**修正方案**：
- 更新所有 `__init__.py` 的注释和导出列表，与实际工具数保持一致
- 在实施计划的 Task 27（注册表更新）中增加同步更新 `__init__.py` 的步骤

### R5. `retrieval.py` 的 `add_document_async` 缺少 `import asyncio`（P0 级现有缺陷）

**发现位置**：`backend/app/agents/services/retrieval.py` `RetrievalService.add_document_async` 方法
**问题**：代码使用 `asyncio.get_event_loop()` 但文件顶部没有 `import asyncio`。运行时会抛 `NameError`。同时 `add_chunk_to_index` 是当前文件的顶层函数，用 `from app.agents.services.retrieval import add_chunk_to_index` 做了冗余的自引用导入。

**修正方案**：
- 在 `retrieval.py` 顶部添加 `import asyncio`
- 将 `from app.agents.services.retrieval import add_chunk_to_index` 改为直接调用 `add_chunk_to_index`
- 此修正应在 Phase 1 开始前完成，属于现有代码缺陷

### R6. `retrieval.py` 索引构建引用了 Character 模型不存在的字段（P0 级现有缺陷）

**发现位置**：`backend/app/agents/services/retrieval.py` `_collect_documents_from_db` 和 `_collect_global_documents_from_db`
**问题**：索引构建代码引用了 `char.get("core_conflict")`、`char.get("character_arc")`、`char.get("knowledge_boundary")`、`char.get("speech_style")`、`char.get("dialogue_samples")`，但 Character 模型中不存在这些字段（模型只有 `personality`, `catchphrase`, `habit_action`, `deep_fear`, `core_motivation`, `growth_arc`, `appearance`, `backstory`, `signature_item`）。

**影响**：这些字段取值永远为 `None`/空字符串，导致角色相关的索引内容缺失关键信息，降低检索质量。但不会抛异常（`dict.get()` 返回 None）。

**修正方案**：
- 将 `core_conflict` → 删除（模型中不存在等价字段）
- 将 `character_arc` → `growth_arc`（模型中的实际字段名）
- 将 `knowledge_boundary` → `deep_fear`（作为内在约束的近似替代）
- 将 `speech_style` → `catchphrase`（作为语言特征的近似替代）
- 将 `dialogue_samples` → 删除（模型中不存在）
- 此修正应在 Phase 1 开始前完成

### R7. 中文分词问题广泛存在（P1 级遗漏）

**发现位置**：以下文件使用 `query.split()` / `description.split()` / `word.split()` 做中文关键词匹配：
- `tools/perception/knowledge_search.py`：`query_words = [w for w in query_lower.split() if len(w) >= 2]`
- `tools/assist/expand_world_setting.py`：`for word in description.split()`
- `tools/modification/propose_outline_adjustment.py`：`for word in description.split()`
- `tools/assist/suggest_plot_twist.py`：（间接通过 retrieval）

**问题**：中文文本没有空格分隔词语，`split()` 对中文几乎无效（整个句子变成一个"词"，或仅按标点断开）。

**修正方案**：
- 在 `tools/utils.py` 新增 `_tokenize_chinese` 函数（spec 4.2 节已提及，但未覆盖全部受影响文件）
- 将所有使用 `.split()` 做中文分词的地方替换为 `_tokenize_chinese`
- `retrieval.py` 中已有 `_tokenize_chinese` 实现（jieba/bigram），应复用而非重新实现

**影响范围**：spec 4.2 节的 `knowledge_search` 降级截断已提及分词，但遗漏了 `expand_world_setting` 和 `propose_outline_adjustment`。需在实施计划中补加替换步骤。

### R8. spec 2.4 节"13 个工具"计数不准确（P1 级修正）

**问题**：
- spec 列出 8 个工具文件 + `generate_chapter_content`（已在列表中）= 9 个工具
- 实际需要替换的文件：`world_setting`, `generate_world_setting_complete`, `style_constraints`, `foreshadowing`, `plot_block`, `subplot`, `generate_outline`, `generate_chapter_outline`, `generate_chapter_content` = 9 个文件
- `propose_setting_change` 的 `new_value` 参数解析逻辑不同（解析失败时保留原始字符串构造 `{"value": new_value}`），不应使用 `parse_json_param`
- JSON 参数总数：2+4+3+1+3+1+3+1+2 = 20 个参数（跨 9 个文件）

**修正**：
- 将 spec 中"13 个工具"修正为"9 个工具，20 个 JSON 参数"
- 明确排除 `propose_setting_change`
- 实施计划 Task 2 也需同步修正

### R9. spec 3.1 节 `update_character` 签名与 Character 模型不完全对齐（P2 级修正）

**问题**：`update_character` 签名与 `create_character` 一致，但 Character 模型还有 `project_id`（不应暴露给 Agent）、`knowledge_boundary`/`speech_style`/`dialogue_samples` 等不存在的字段。

**修正**：`update_character` 的参数列表应与 Character 模型的可修改字段完全一致：
```python
async def update_character(
    character_id: int,
    name: str | None = None,
    role: str | None = None,
    personality: str | None = None,
    catchphrase: str | None = None,
    habit_action: str | None = None,
    deep_fear: str | None = None,
    core_motivation: str | None = None,
    growth_arc: str | None = None,
    appearance: str | None = None,
    backstory: str | None = None,
    signature_item: str | None = None,
) -> dict:
```
（与 spec 原签名一致，确认无误。但 spec 中"其余字段留空不修改"的说明需明确：空字符串 `""` 表示不修改，这需要与字段的自然默认值区分。）

**进一步修正**：`update_character` 的部分更新逻辑需用 `None` 作为"不修改"标记而非空字符串，因为 `catchphrase=""` 可能是合法更新（清空口头禅）。建议：
- 参数默认值改为 `None`
- `if value is not None` 才写入

### R10. `consistency_scan` 性能问题（P2 级修正）

**发现位置**：spec 3.2 节
**问题**："扫描所有已有章节"在 50+ 章时需加载全部章节内容，DB 查询量巨大，单次调用可能耗时数秒。

**修正方案**：
- 新增 `chapter_range` 参数，限制扫描范围
- 默认只扫描最近 20 章（覆盖最近的写作区间）
- 全书扫描需显式传入 `chapter_range="all"`
- 结果分页：`max_issues` 默认 20，可调大

```python
@tool
async def consistency_scan(
    check_types: str = "all",
    chapter_range: str = "recent",
    max_issues: int = 20,
) -> dict:
    """全书一致性扫描。自动检测角色行为矛盾、时间线矛盾和设定引用矛盾。

    不调用 LLM，纯规则扫描。适合长篇小说定期检查。

    Args:
        check_types: 检查类型 - "character"(角色), "timeline"(时间线),
                     "setting"(设定), 或 "all"
        chapter_range: 扫描范围 - "recent"(最近20章), "all"(全书),
                       或 JSON 列表如 "[1,5,10]" 指定章节
        max_issues: 最多返回的矛盾数量（默认 20）
    """
```

### R11. `generate_chapter_content` 拆分策略的向后兼容问题（P1 级修正）

**发现位置**：spec 3.4 节
**问题**：spec 说"旧参数标记为 deprecated，内部不再执行伏笔/时间线逻辑，改为发出提示"请使用 record_chapter_meta 工具"。`record_chapter_meta` 检查该章节是否已有时间线条目，有则更新而非重复创建"，但这意味着 `generate_chapter_content` 仍需保留旧参数并做兼容处理，与"精简参数"的目标矛盾。而且旧参数与新工具可能产生重复写入（Agent 既传了旧参数又调了 `record_chapter_meta`）。

**修正方案**：
- **Phase 1**（P0 阶段）：先修复异常处理（2.1 节），保留全部旧参数
- **Phase 2**（P1 阶段）：新增 `record_chapter_meta`，同时在 `generate_chapter_content` 中标记旧参数为 `deprecated`（在 docstring 中说明）
- **不删除旧参数**：保留旧参数但内部不再执行伏笔/时间线逻辑，改为发出提示"请使用 record_chapter_meta 工具"
- **防重复写入**：`record_chapter_meta` 检查该章节是否已有时间线条目，有则更新而非重复创建

### R12. `batch_read_for_index` 中的重复查询（P2 级现有缺陷）

**发现位置**：`backend/app/agents/services/knowledge_base.py` `batch_read_for_index`
**问题**：`self.plots._read_all_with_session(db)` 返回 `{"plot_blocks": [...], "plot_questions": [...], "subplots": [...]}`，但在 `batch_read_for_index` 中被调用后，用 `.get("plot_blocks", [])` 等取值。而 `_read_all_with_session` 在同一个 db session 中执行了 3 次 query，每次返回全部三种数据。这意味着同一 session 中查询了 3 次 PlotBlock、3 次 PlotQuestion、3 次 Subplot。

**修正方案**：
- `_read_all_with_session` 改为一次调用返回全部数据（当前已如此），但 `batch_read_for_index` 应只调用一次并缓存结果
- 将 `_read_all_with_session(db)` 的返回值赋给一个变量，然后从中提取三个字段

### R13. 注册表递进关系维护风险（P2 级修正）

**发现位置**：`backend/app/agents/tools/registry.py`
**问题**：`INCUBATION_TOOLS` / `STRUCTURE_TOOLS` / `WRITING_TOOLS` 是三个独立列表，手动维护递进关系。每次新增工具需同时修改三个列表，容易遗漏。现有代码中 `STRUCTURE_TOOLS` 包含 `review_chapter` 和 `rewrite_chapter`（这两者需要 LLM 调用），但在 `INCUBATION_TOOLS` 中没有——这是正确的设计（孵化阶段不需要审核章节），但手动维护的列表容易出错。

**修正方案**：
- 在 5.1 节动态注册表设计中，将 `_PHASE_BASE_TOOLS` 改为基于集合运算的声明式定义：
```python
_INCUBATION_TOOL_NAMES = {"advance_phase", "knowledge_search", ...}
_STRUCTURE_EXTRA_NAMES = {"foreshadowing_check", "review_chapter", ...}
_WRITING_EXTRA_NAMES = {"consistency_check", "style_analysis", ...}

STRUCTURE_TOOL_NAMES = _INCUBATION_TOOL_NAMES | _STRUCTURE_EXTRA_NAMES
WRITING_TOOL_NAMES = STRUCTURE_TOOL_NAMES | _WRITING_EXTRA_NAMES
REVISION_TOOL_NAMES = WRITING_TOOL_NAMES
```
- 然后在 `ToolRegistry.get_tools()` 中根据名称从工具注册表中查找实际工具对象
- 这样只需维护增量集合，递进关系由集合运算保证

### R14. `ToolResultCache` 方法命名不一致（P2 级修正）

**发现位置**：spec 5.4 节
**问题**：spec 中方法名为 `invalidate_by_prefix`，但实施计划 Task 29 代码中为 `invalidate_by_prefix`。两者语义相同但命名不一致。

**修正**：统一为 `invalidate_by_prefix`（更准确地描述了实际行为——前缀匹配而非模式匹配）。

### R15. `update_foreshadowing` 缺少 `appearance_count` 和 `resolved_chapter` 参数（P2 级修正）

**发现位置**：spec 3.1 节
**问题**：Foreshadowing 模型有 `appearance_count`（出现次数，用于判断升级）和 `resolved_chapter`（实际回收章节号），但 `update_foreshadowing` 签名中没有。Agent 无法通过工具推进伏笔的出现次数或记录回收章节号。

**修正**：
```python
@tool
async def update_foreshadowing(
    foreshadowing_id: int,
    level: str | None = None,
    status: str | None = None,
    content: str | None = None,
    appearance_count: int | None = None,
    expected_resolve_chapter: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
```

### R16. `delete_plot_block` 安全检查方案不完整（P2 级修正）

**发现位置**：spec 3.1 节
**问题**：spec 说"有子实体的（情节块下有问题/伏笔）拒绝删除"，但 PlotQuestion 通过 `plot_block_id` 外键关联 PlotBlock，且数据库设置了 `ondelete='SET NULL'`（即删除情节块时问题链的 `plot_block_id` 被置为 NULL 而非级联删除）。这意味着删除情节块不会丢失问题链数据，只是断开关联。

**修正方案**：
- 安全检查改为：如果情节块下有未回答的问题（`status="pending"`），拒绝删除并提示先回答或迁移
- 已回答的问题（`status="answered"/"closed"`）可以随情节块删除断开关联
- 伏笔检查：如果情节块范围内有活跃伏笔的 `expected_resolve_chapter`，提示确认

### R17. `hooks.py` 中 `except Exception: pass` 与 P0 修复原则矛盾（P2 级修正）

**发现位置**：spec 5.3 节 + 实施计划 Task 30
**问题**：hooks 的设计中说"Hook 失败不影响主流程"，代码中用 `except Exception: pass` 处理 hook 失败。但这与 P0 修复 2.1 节"禁止 `except Exception: pass`"的原则矛盾。虽然 hook 失败确实不应影响主流程，但完全静默吞异常不利于调试。

**修正方案**：
- Hook 失败时记录到 `auto_check_results` 中：`{"checked": False, "error": str(e)}`
- 同时用 `logging.warning` 记录日志
- 不影响主流程的返回结果

---

### 审查修正汇总

| 编号 | 级别 | 修正类型 | 影响 spec 章节 | 影响 plan Task |
|------|------|----------|---------------|----------------|
| R1 | P0 | 新增问题 | 5.2 | Task 33 |
| R2 | P0 | 修正方案 | 2.3 | Task 5 |
| R3 | P0 | 修正方案 | 2.1 | Task 4 |
| R4 | P1 | 补充步骤 | 六 | Task 27 |
| R5 | P0 | 新增任务 | 无（现有缺陷） | 新增前置 Task |
| R6 | P0 | 新增任务 | 无（现有缺陷） | 新增前置 Task |
| R7 | P1 | 扩大范围 | 4.2 | Task 18 |
| R8 | P1 | 修正计数 | 2.4 | Task 2 |
| R9 | P2 | 修正签名 | 3.1 | Task 7-12 |
| R10 | P2 | 修正方案 | 3.2 | Task 13 |
| R11 | P1 | 修正方案 | 3.4 | Task 15 |
| R12 | P2 | 新增任务 | 无（现有缺陷） | 新增 Task |
| R13 | P2 | 修正方案 | 5.1 | Task 31 |
| R14 | P2 | 统一命名 | 5.4 | Task 29 |
| R15 | P2 | 修正签名 | 3.1 | Task 11 |
| R16 | P2 | 修正方案 | 3.1 | Task 12 |
| R17 | P2 | 修正方案 | 5.3 | Task 30 |

---

## 十、第二遍深度审查修正（2026-06-14）

> 本附录记录对 spec 和 plan 的第二遍审查发现。验证第一轮修正的内部一致性，
> 交叉对比源码，深挖遗漏的技术债。修正原则不变：从根源解决问题，不打补丁。

### R18. `batch_read_for_index` 三次重复调用 `_read_all_with_session`（P0 级缺陷，R12 修正不完整）

**发现位置**：`backend/app/agents/services/knowledge_base.py` `batch_read_for_index`
**问题**：R12 只说"只调用一次并缓存结果"，但没有指出根本原因——`batch_read_for_index` 方法中对 `self.plots._read_all_with_session(db)` 调用了 **3 次**（分别取 `plot_blocks`、`plot_questions`、`subplots`），每次调用都执行 3 条 SQL 查询，共 **9 次查询**。同理，`self.timelines._read_all_with_session(db)` 也调用了 **2 次**（取 `timeline` 和 `scene_entries`），共 4 次查询。
**修正方案**：
- `batch_read_for_index` 应只调用 `self.plots._read_all_with_session(db)` 一次，赋值给 `plots_data`，然后从中提取三个字段
- 同理，`self.timelines._read_all_with_session(db)` 只调用一次，赋值给 `timelines_data`
- 修正后查询次数从 9+4=13 降到 3+2=5

### R19. `consistency_check` 仍然引用 Character 模型不存在的字段（P0 级缺陷）

**发现位置**：`backend/app/agents/tools/perception/consistency_check.py`
**问题**：R6 修正了 `retrieval.py` 中索引构建的字段映射，但 `consistency_check.py` 第 37 行仍有：
```python
"knowledge_boundary": char.get("knowledge_boundary") or char.get("deep_fear") or "",
```
`char.get("knowledge_boundary")` 永远返回 `None`（Character 模型无此字段），回退到 `deep_fear`。这虽然不会报错，但字段名 `knowledge_boundary` 在返回结果中误导 Agent 认为存在独立的知识边界字段。R6 修正范围不够——只修了 retrieval.py，遗漏了 consistency_check.py。
**修正方案**：
- `consistency_check.py` 中的字段名改为 `deep_fear`（与模型一致）
- 或改为 `inner_constraint` 并注释说明来源是 `deep_fear`

### R20. `advance_phase` 事务合并后 KB 查询仍在事务外（P0 级设计缺陷）

**发现位置**：spec 2.2 节 + plan Task 3
**问题**：spec 和 plan 的 `advance_phase` 合并方案将读取和写入放在同一 Session + `with_for_update()` 行锁中。但在读取阶段后，代码调用了 `kb.outlines.get()`、`kb.characters.list_characters()` 等方法——这些方法使用 `_kb()` 返回的 KnowledgeBaseService，而 KB 内部每个方法都创建独立的 `SessionLocal()` session。这意味着：
1. 行锁锁住的是 WorkflowState 行，但 KB 查询的数据不在同一事务中
2. 在行锁持有期间，KB 查询的数据可能被其他请求修改（虽然概率低）
3. 行锁持有时间过长（KB 查询 6 次，每次一个 session），可能导致其他请求等待

**根本原因**：`_kb()` 返回的 KnowledgeBaseService 和 `advance_phase` 自己的 `SessionLocal()` 是完全独立的 session，无法形成真正的事务一致性保证。

**修正方案**：
- 将 `advance_phase` 的判断逻辑改为纯 SQL 查询（不通过 KB facade），在同一个 session 中完成：
  - 查 WorkflowState（with_for_update）
  - 查 Outline（判断是否存在）
  - 查 Character（判断数量 >= 1）
  - 查 WorldSetting（判断是否存在）
  - 如果需要推进，更新 WorkflowState 并 commit
- 或者，将 KB 的完整度判断放在获取行锁之前（先读取状态判断是否可能推进，再获取行锁确认并写入），这样行锁持有时间极短
- 推荐后者，因为改动更小，且实际并发风险极低（Agent 不会真正并发推进同一项目）

### R21. `_extract_keywords` 中 `description.split()` 对中文无效（P1 级，R7 修正范围不够）

**发现位置**：`backend/app/agents/tools/utils.py` `_extract_keywords` 函数
**问题**：R7 指出了 `knowledge_search.py`、`expand_world_setting.py`、`propose_outline_adjustment.py` 中使用 `.split()` 的问题，但遗漏了 `utils.py` 中 `_extract_keywords` 函数的同样问题。`_extract_keywords` 被 `propose_setting_change.py` 调用，是变更影响评估的关键函数。`description.split()` 对中文描述几乎无效，导致关键词提取失败，影响评估不准确。
**修正方案**：
- 在 R7 修正范围中补入 `utils.py` 的 `_extract_keywords` 函数
- 将 `description.split()` 替换为 `_tokenize_chinese(description)`
- 将内部 `val.split()` 也替换为 `_tokenize_chinese(val)`

### R22. `generate_outline` 的 3 个 JSON 参数未列入 spec 2.4 的受影响工具（P1 级遗漏）

**发现位置**：spec 2.4 节
**问题**：spec 2.4 节列出受影响的 9 个工具文件，其中包括 `generate_outline.py`，但受影响的参数列表中没有列出 `plot_points`、`emotional_curve`、`characters` 这 3 个 JSON 参数。plan Task 2 Step 7 只说"3 个 JSON 参数：`plot_points`, `emotional_curve`, `characters`"，与 spec 参数表不一致。
**根因**：spec 正文受影响参数列表缺失 `generate_outline` 的参数。
**修正方案**：在 spec 2.4 节的受影响工具列表中补充 `generate_outline` 的 3 个参数。

### R23. `update_character` 签名中空字符串 `""` 默认值的语义歧义（P1 级，R9 修正不完整）

**发现位置**：spec 3.1 节
**问题**：R9 指出"参数默认值改为 None"，但 spec 正文 3.1 节的 `update_character` 签名仍显示 `str = ""`。R9 在附录中说了"参数默认值改为 None"，但正文未同步修改。这是第一轮修正的内部不一致。
**修正方案**：将 spec 3.1 节 `update_character` 签名中的 `str = ""` 全部改为 `str | None = None`，并更新说明："`None` 表示不修改，传入具体值则更新。要清空字段需传入空字符串 `""`。"

### R24. `record_chapter_meta` 防重复逻辑未定义——TimelineStore 无按 chapter_number 查询+更新方法（P1 级设计缺陷）

**发现位置**：spec 3.4 节
**问题**：spec 说"`record_chapter_meta` 检查该章节是否已有时间线条目，有则更新而非重复创建"。但 TimelineStore 当前只有 `create_timeline_entry`（创建）和 `list_timeline`（列表），没有 `get_by_chapter_number`（按章节号查询）或 `update_timeline_entry`（更新）方法。这意味着 `record_chapter_meta` 的防重复逻辑无法实现。
**修正方案**：
- 在 TimelineStore 中新增 `get_by_chapter_number(chapter_number: int) -> dict | None` 方法
- 在 TimelineStore 中新增 `update_timeline_entry(entry_id: int, data: dict) -> dict` 方法
- 或复用已有的 `_create_with_session`（需先查再决定创建/更新）
- plan Task 15 需补充修改 TimelineStore 的步骤

### R25. `retrieval.py` 的 `_keyword_fallback` 也引用了 Character 模型不存在的字段（P1 级，R6 修正范围不够）

**发现位置**：`backend/app/agents/services/retrieval.py` `_keyword_fallback` 函数
**问题**：R6 修正了 `_collect_documents_from_db` 和 `_collect_global_documents_from_db` 中的字段映射，但 `_keyword_fallback` 函数中仍有 `char.get('knowledge_boundary', '')` 和 `char.get('speech_style', '')`（第 488-490 行），同样永远返回空字符串。
**修正方案**：
- 将 `_keyword_fallback` 中的 `knowledge_boundary` → `deep_fear`
- 将 `speech_style` → `catchphrase`
- 与 R6 修正保持一致

### R26. `generate_story_seed` 工具未在 spec/plan 中提及任何修改（P2 级遗漏）

**发现位置**：spec + plan
**问题**：`generate_story_seed` 存在于 `tools/creation/` 目录，注册在 INCUBATION_TOOLS 中，但 spec 和 plan 中未提及它的任何修改（docstring 中文化、JSON 参数替换等都没有）。虽然它没有 JSON 字符串参数需要替换，但它也需要 docstring 中文化（P2 4.1 节说"全部 31 个工具"）。
**修正方案**：确认 `generate_story_seed` 在 Task 26（docstring 中文化）的覆盖范围内，无需额外处理。

### R27. `_tokenize_chinese` 的归属问题——retrieval.py 和 tools/utils.py 各有一份（P2 级设计问题）

**发现位置**：spec 4.2 节 + R7 修正
**问题**：`retrieval.py` 中已有 `_tokenize_chinese` 实现（jieba/bigram），spec 4.2 节说"关键词匹配使用 `_tokenize_chinese` 替代空格分词"，plan Task 1 在 `tools/utils.py` 新增该函数。但两个文件各有一份实现，违反 DRY 原则。如果未来修改分词逻辑（如加入自定义词典），需要同时改两处。
**修正方案**：
- 将 `_tokenize_chinese` 统一放在 `tools/utils.py`（工具层公共函数）
- `retrieval.py` 从 `tools/utils.py` 导入
- 或者统一放在更底层的公共模块（如 `app/utils/text.py`），两处都从那里导入
- 推荐放在 `tools/utils.py`，因为 retrieval.py 对 tools 层有反向依赖风险，放 `app/utils/text.py` 更干净
- 但需注意 `retrieval.py` 是服务层，不应依赖工具层。因此最终推荐放在 `app/utils/text.py`

### R28. Plan Task 2 "修改文件"列表仍写"13 个含 JSON 参数的工具"（P1 级，R8 修正不完整）

**发现位置**：plan Task 2 的文件列表
**问题**：plan "修改文件（约 20 个）"表格中仍有"13 个含 JSON 参数的工具"行，与 R8 修正的"9 个工具"不一致。同时 Task 2 的 Steps 列了 10 个文件（含 `propose_setting_change.py`），但 Step 10 说"不替换"——那它不应出现在修改文件列表中。
**修正方案**：将"13 个含 JSON 参数的工具"改为"9 个含 JSON 参数的工具"，从文件列表中移除 `propose_setting_change.py`。

### R29. `expand_world_setting` 中 `description.split()` 匹配红色设定的逻辑会误报（P2 级）

**发现位置**：`backend/app/agents/tools/assist/expand_world_setting.py`
**问题**：R7 提到了 `expand_world_setting.py` 使用 `description.split()` 的问题，但未深入分析匹配逻辑。当前代码 `for word in description.split()` 对中文几乎无效（整个描述变成一个词或按标点断开），导致 `contradictions` 几乎永远为空列表，红色设定冲突检测形同虚设。
**修正方案**：
- 替换为 `_tokenize_chinese(description)`
- 同时将 `word in rule_text` 改为更精确的子串匹配或关键词包含检查

---

### 第二遍审查修正汇总

| 编号 | 级别 | 修正类型 | 影响 spec 章节 | 影响 plan Task |
|------|------|----------|---------------|----------------|
| R18 | P0 | 补充修正 | 无（现有缺陷） | Task 33b |
| R19 | P0 | 扩大修正范围 | 无（现有缺陷） | 新增 Task 0c |
| R20 | P0 | 修正设计 | 2.2 | Task 3 |
| R21 | P1 | 扩大修正范围 | 4.2 | Task 18 |
| R22 | P1 | 补充遗漏 | 2.4 | Task 2 |
| R23 | P1 | 正文同步 | 3.1 | Task 7-12 |
| R24 | P1 | 补充设计 | 3.4 | Task 15 |
| R25 | P1 | 扩大修正范围 | 无（现有缺陷） | Task 0b |
| R26 | P2 | 确认覆盖 | 无 | Task 26 |
| R27 | P2 | 归属设计 | 4.2 | Task 1 |
| R28 | P1 | 正文同步 | 无 | Task 2 |
| R29 | P2 | 扩大修正范围 | 4.2 | Task 18 |
