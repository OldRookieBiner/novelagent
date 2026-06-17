# Agent 工具质量优化设计

> 日期：2026-06-17
> 范围：P0+P1，共 4 项优化
> 目标：减少工具数量、消除 N+1 查询、集中硬编码常量、封装 DB session
> v2：第二轮审查后修正 7 处问题

---

## 背景

当前 Agent 工具体系有 33 个工具，按 4 类组织（perception 6、creation 19、modification 6、assist 2）。经质量评估发现以下结构性问题：

- 5 对 create/update 工具接口重复，Agent 认知负担重
- 4 个 update 工具用 list 全量遍历找目标，存在 N+1 查询
- 感知/写入工具名在 3 处硬编码维护，新增工具易遗漏
- advance_phase 工具直接操作 SessionLocal + 行锁，接缝泄漏

本次优化仅覆盖 P0+P1 共 4 项，P2+P3 项留待后续迭代。

注：`create_relation` 和 `create_evolution_plan` 没有对应的独立 update 工具（relation 更新走 modification 层的 `apply_change`），因此实际需要合并的是 5 对而非 6 对。

---

## 优化 #1：create/update 合并

### 问题

5 对 create + update 工具共 10 个，update 的参数列表与 create 几乎完全重复。Agent 每次需要先判断用哪个工具、再填写几乎相同的参数签名。接口浅薄——宽度与实现同宽，深度不足。

### 方案

删除 5 个 `update_*` 工具，将 update 能力注入对应的 create 工具。检测逻辑统一为：

- 有 `*_id` 参数（非零/非空）→ 更新已有实体
- 无 `*_id` 参数 → 创建新实体

工具名保持不变（`create_character` 等），docstring 更新说明双模式。

### 受影响工具明细

| 原 create 工具 | 删除的 update 工具 | 合并后新增参数 | update 路径返回 |
|---|---|---|---|
| `create_character` | `update_character` | `character_id: int = 0` | 保留 `changes` diff |
| `create_foreshadowing` | `update_foreshadowing` | `foreshadowing_id: int = 0` + `foreshadowing_ids: str = ""` | 批量模式保留 |
| `create_plot_block` | `update_plot_block` | `plot_block_id: int = 0` | 保留 `updated_fields` |
| `create_subplot` | `update_subplot` | `subplot_id: int = 0` | 保留 `changes` diff |
| `create_plot_question` | `update_plot_question` | `question_id: int = 0` | 保留 `changes` diff |
| `create_style_constraints` | 无独立 update | 无变化（已有 upsert） | 无 |

注：`create_relation`、`create_evolution_plan`、`create_world_setting`、`generate_world_setting_complete` 均无独立 update 工具，不涉及合并。

### 参数默认值规则（第二轮审查修正）

合并后的工具参数默认值必须与原 `update_*` 工具保持一致，使用 `None` 而非 `""`：

| 参数类别 | 默认值 | create 路径过滤 | update 路径过滤 | 说明 |
|---|---|---|---|---|
| 必填字段（name, role, content, title 等） | 无默认值 | — | `if v is not None` | create 路径不传则报错 |
| create/update 共有的可选字符串字段 | `None` | `if val:` (falsy 过滤) | `if v is not None` | `None` = 不填/不修改，`""` = 清空字段 |
| create/update 共有的可选整数字段 | `None` | `if v is not None` | `if v is not None` | `None` = 不填/不修改 |
| 仅 update 路径有的字段 | `None` | 不纳入 create data | `if v is not None` | create 路径忽略这些字段 |
| JSON 字符串参数（must_happen, characters, related_characters 等） | `None` | `or "[]"` 兜底解析 | `if v is not None` | `None`=不修改，`"[]"`=清空，非空 JSON=正常解析 |

**为什么不用 `""` 默认值**：原 `update_character` docstring 明确说 "None 表示不修改，传入具体值则更新。要清空字段需传入空字符串"。如果默认值用 `""`，update 路径的 `if v is not None` 不会过滤 `""`，当 Agent 只传 `character_id=5` 而不传 `name` 时，`name=""` 会被写入 DB，清空角色名——这是 bug。

**create 路径兼容性**：原 create 工具用 `if val:` 过滤 falsy 值（`""` 和 `None` 都是 falsy），所以 `None` 默认值对 create 路径完全兼容。`personality: str | None = None` + `if personality:` 的效果与原 `personality: str = ""` + `if val:` 完全一致。

**`current_status` 特殊处理**：原 `create_subplot` 有 `current_status: str = "developing"`（创建时默认值），合并后改为 `current_status: str | None = None`。create 路径中 `current_status = current_status or "developing"` 保证创建时默认 "developing"；update 路径 `None` 不修改。

### 合并后 create 工具的内部路由逻辑

以 `create_character` 为例：

```python
@tool
async def create_character(
    character_id: int = 0,  # 非零时为更新模式
    name: str = "",         # 必填（create 路径校验）
    role: str = "",         # 必填（create 路径校验）
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
    """创建新角色或更新已有角色。提供 character_id 时为更新模式。

    - character_id=0（默认）：创建新角色（name 和 role 必填）
    - character_id>0：更新指定 ID 的角色。None 表示不修改，空字符串 "" 表示清空字段
    """
    kb = _kb()

    if character_id:
        # --- 更新路径 ---
        before = kb.characters.get_character(character_id)
        if not before:
            return {"error": f"角色 ID {character_id} 不存在"}

        _UPDATABLE_FIELDS = (
            "name", "role", "personality", "catchphrase", "habit_action",
            "deep_fear", "core_motivation", "growth_arc", "appearance",
            "backstory", "signature_item",
        )
        update_data = {
            k: v for k, v in locals().items()
            if k in _UPDATABLE_FIELDS and v is not None
        }
        if not update_data:
            return {"message": "无字段需要更新", "character_id": character_id}

        updated = kb.characters.update_character(character_id, update_data)
        changes = build_changes_diff(before, update_data)
        return {
            "character_id": character_id,
            "name": updated.get("name", before.get("name")),
            "updated_fields": list(changes.keys()),
            "changes": changes,
            "message": f"角色「{updated.get('name')}」已更新 {len(changes)} 个字段",
        }
    else:
        # --- 创建路径 ---
        if not name or not role:
            return {"error": "创建角色时 name 和 role 为必填字段"}

        data = {"name": name, "role": role}
        for key, val in [
            ("personality", personality), ("catchphrase", catchphrase),
            ("habit_action", habit_action), ("deep_fear", deep_fear),
            ("core_motivation", core_motivation), ("growth_arc", growth_arc),
            ("appearance", appearance), ("backstory", backstory),
            ("signature_item", signature_item),
        ]:
            if val:  # falsy 过滤：None 和 "" 都不会写入
                data[key] = val
        char = kb.characters.create_character(data)
        return {
            "action": "created",
            "id": char["id"],
            "name": char["name"],
            "role": char["role"],
            "message": f"角色「{name}」已创建并写入知识库",
        }
```

### 各工具完整参数签名

**create_plot_block**：

```python
@tool
async def create_plot_block(
    plot_block_id: int = 0,       # 非零时更新
    title: str = "",              # 必填（create 路径校验）
    chapter_start: int | None = None,  # 必填（create 路径校验）
    chapter_end: int | None = None,    # 必填（create 路径校验）
    must_happen: str | None = None,
    questions_to_raise: str | None = None,
    questions_to_answer: str | None = None,
    expected_mood: str | None = None,
    completion_summary: str | None = None,  # 仅 update 路径
) -> dict:
```

注：`must_happen`/`questions_to_raise`/`questions_to_answer` 改为 `None` 默认值，与普通字符串字段规则一致。`"[]"` 默认值会导致 update 路径无法区分"Agent 没传"和"Agent 想清空"——当 Agent 只传 `plot_block_id=5` 时，`must_happen="[]"` 非 None 会被误处理为清空操作。create 路径用 `or "[]"` 兜底保证空列表默认值。update 路径用 `if v is not None` 过滤，`None` 不修改，`"[]"` 解析为空列表（清空），非空 JSON 正常解析。

**create_foreshadowing**：

```python
@tool
async def create_foreshadowing(
    foreshadowing_id: int = 0,
    foreshadowing_ids: str = "",  # 批量更新模式
    content: str = "",            # create 路径必填
    level: str | None = None,
    planted_chapter: int | None = None,
    expected_resolve_chapter: int | None = None,
    related_characters: str | None = None,  # create 路径用 or "[]" 兜底
    # 以下仅 update 路径
    status: str | None = None,
    appearance_count: int | None = None,
    resolved_chapter: int | None = None,
) -> dict:
```

**create_subplot**：

```python
@tool
async def create_subplot(
    subplot_id: int = 0,
    name: str = "",               # create 路径必填
    characters: str | None = None,  # create 路径用 or "[]" 兜底
    current_status: str | None = None,  # create 默认 "developing"，update 时 None 不修改
    raised_in_chapter: int | None = None,
    planned_intersection_chapter: int | None = None,
    expected_resolution_chapter: int | None = None,
) -> dict:
```

**create_plot_question**：

```python
@tool
async def create_plot_question(
    question_id: int = 0,
    question_text: str = "",      # create 路径必填
    raised_in_chapter: int | None = None,
    plot_block_id: int | None = None,
    # 以下仅 update 路径
    answered_in_chapter: int | None = None,
    status: str | None = None,
) -> dict:
```

### 必填字段校验规则

| 工具 | create 路径必填字段 | 校验条件 |
|---|---|---|
| `create_character` | `name`, `role` | `if not name or not role` |
| `create_foreshadowing` | `content` | `if not content` |
| `create_plot_block` | `title`, `chapter_start`, `chapter_end` | `if not title or chapter_start is None or chapter_end is None` |
| `create_subplot` | `name` | `if not name` |
| `create_plot_question` | `question_text` | `if not question_text` |

### create_foreshadowing 的三模式路由

`update_foreshadowing` 有批量更新功能，合并后 `create_foreshadowing` 需同时支持三种模式。判断规则（按优先级）：

1. `foreshadowing_id > 0` 且 `foreshadowing_ids` 非空 → 返回错误："不能同时提供 foreshadowing_id 和 foreshadowing_ids"
2. `foreshadowing_id > 0` → 单条更新模式
3. `foreshadowing_ids` 非空 → 批量更新模式
4. 都为空 → 创建新伏笔（`content` 必填）

### 工具代码中硬编码工具名的引用

以下文件在代码/hint 文本中引用了 `update_*` 工具名，需同步更新：

- `delete_plot_block.py`：hint 文本 `"使用 update_plot_question 工具"` → 改为 `"使用 create_plot_question(question_id=...) 工具"`
- 全局扫描 `rg "update_character|update_foreshadowing|update_plot_block|update_subplot|update_plot_question" backend/app/agents/tools/` 确认无遗漏（注意：`api/` 和 `services/` 下的同名函数是 REST API 端点和 Store 方法，不属于 Agent 工具，不受影响）

### registry.py 变化

- 删除 5 个 `update_*` 的 import：`update_character`、`update_foreshadowing`、`update_plot_block`、`update_subplot`、`update_plot_question`
- `_STRUCTURE_EXTRA` 和 `_WRITING_EXTRA` 中移除上述 5 个条目
- `creation/__init__.py` 中移除上述 5 个 import
- `AGENT_TOOLS = WRITING_TOOLS` 无需改动（列表已自动不包含被删的 import）
- `registry_v2.py` 引用 `WRITING_TOOLS` 列表，删除后列表自动更新，无需额外修改

### 下游影响

- **前端 AgentChatPanel.tsx**：工具名→中文标签映射表需更新。移除 `update_character: '更新角色'` 等 5 条，新增逻辑——当 `create_*` 工具返回含 `updated_fields` 或 `changes` 时，前端显示"更新角色"而非"创建角色"
- **REST API 层**（`api/characters.py`、`api/knowledge.py`）：**不受影响**。这些 `update_character`/`update_plot_block` 等是 REST API 端点函数名，与 Agent 工具无关
- **Store 方法层**（`kb.characters.update_character()` 等）：**不受影响**。底层 Store 方法名不变，Agent 工具层只是调用方
- **知识库数据**：底层 Store 方法调用不变
- **SSE 事件流**：不受影响
- **后端测试**：`test_agent_tools.py` 和 `test_change_workflow.py` 需更新 import 路径和工具名引用
- **Agent 行为**：从"选 create 还是 update"变为"填不填 id"，docstring 需清晰说明

### 工具数变化

33 → 28（减少 5 个）

---

## 优化 #2：N+1 查询消除

### 问题

5 个更新路径中有 4 个先用 `list_*()` 获取全量数据再遍历找目标 ID（foreshadowing 已使用 `get()` 无此问题）。当实体数量多时，每次更新都加载全部同类实体，是性能问题也是局部性问题。

此外，`utils.py` 的 `_get_current_value()` 和 `delete_plot_block.py` 也有同类 N+1 问题，一并消除。

### Store 现有方法盘点（第二轮审查修正）

| Store | 已有 `get_by_id` 类方法 | 需补的方法 |
|---|---|---|
| CharacterStore | ✅ 已有 `get_character(id)` | 无需补 |
| PlotStore | ❌ | `get_plot_block_by_id(id)` / `get_subplot_by_id(id)` / `get_plot_question_by_id(id)` |
| ForeshadowingStore | ✅ 已有 `get(id)` | 无需补 |
| StyleStore | ✅ 已有 `get_constraints()`（单例） | 无需补 |

### 新增 Store 方法签名

```python
# PlotStore
def get_plot_block_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个情节块，不存在返回 None"""

def get_subplot_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个支线，不存在返回 None"""

def get_plot_question_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个问题，不存在返回 None"""
```

内部实现：`self.session(readonly=True)` + `db.query(Model).filter(Model.id == id, Model.project_id == self.project_id).first()` + `_to_dict`，与现有 Store 方法模式一致。返回 `dict`，不存在返回 `None`。

### `build_changes_diff` 提取

4 个更新路径都有"对比 before/after 构建变更记录"的逻辑，提取到 `utils.py`：

```python
def build_changes_diff(before: dict, update_data: dict) -> dict:
    """对比 before 和 update_data，返回 {field: {before, after}} 格式的变更记录。

    只包含实际发生变化的字段（before[key] != update_data[key]）。

    前置条件：调用方应确保 update_data 中不含 None 值（由 if v is not None 过滤），
    如果 update_data 残留 None 值，before 中对应的非 None 值将被记录为变更。

    依赖 SQLAlchemy JSON 列的自动反序列化，before 和 update_data 中的
    list/dict 类型可直接用 != 比较（比较元素值而非引用）。
    """
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}
    return changes
```

### N+1 消除范围（第二轮审查扩展）

| 位置 | 旧代码 | 新代码 |
|---|---|---|
| 合并后 create_character 更新路径 | `kb.characters.list_characters()` 遍历 | `kb.characters.get_character(id)` |
| 合并后 create_plot_block 更新路径 | `kb.plots.list_plot_blocks()` 遍历 | `kb.plots.get_plot_block_by_id(id)` |
| 合并后 create_subplot 更新路径 | `kb.plots.list_subplots()` 遍历 | `kb.plots.get_subplot_by_id(id)` |
| 合并后 create_plot_question 更新路径 | `kb.plots.list_plot_questions()` 遍历 | `kb.plots.get_plot_question_by_id(id)` |
| `utils.py` `_get_current_value` character 分支 | `kb.characters.list_characters()` 遍历 | `kb.characters.get_character(id)` |
| `utils.py` `_get_current_value` relation 分支 | `kb.characters.list_relations()` 遍历 | 新增 `CharacterStore.get_relation(id)` 或保留遍历（relation 数量通常少） |
| `delete_plot_block.py` | `kb.plots.list_plot_blocks()` 遍历 | `kb.plots.get_plot_block_by_id(id)` |

注：`_get_current_value` 的 relation 分支暂保留遍历（关系数量通常很少，且 CharacterStore 无 `get_relation(id)` 方法，为最小改动不新增方法）。

---

## 优化 #3：硬编码工具名常量集中

### 问题

感知/写入工具名在 3 处独立硬编码维护：

1. `agent_graph.py` 的 `is_perception` 元组——6 个工具名
2. `agent_graph.py` 的 `invalidate_by_prefix` 列表——6 个前缀
3. `hooks.py` 的 `TOOL_HOOKS`——工具名到 hook 的映射

新增或重命名感知工具时需同步更新 3 处，局部性不足。

### 方案

在 `registry.py` 新增以下常量：

```python
# 感知工具名集合 — 用于缓存/hooks/成本控制的统一判定
PERCEPTION_TOOL_NAMES = frozenset({
    "knowledge_search", "foreshadowing_check",
    "consistency_scan", "style_analysis",
    "rhythm_analysis", "progress_report",
})

# 写入工具名集合 — 执行后使感知缓存失效
WRITING_TOOL_NAMES = frozenset({
    name for name in (t.name for t in WRITING_TOOLS)
    if name not in PERCEPTION_TOOL_NAMES
})
```

### 下游替换

**agent_graph.py**：

```python
# 旧
is_perception = tool_name in (
    "knowledge_search", "foreshadowing_check",
    "consistency_scan", "style_analysis",
    "rhythm_analysis", "progress_report",
)
cache.invalidate_by_prefix([
    "knowledge_search:", "consistency_scan:",
    "style_analysis:", "rhythm_analysis:",
    "progress_report:", "foreshadowing_check:",
])

# 新
from app.agents.tools.registry import PERCEPTION_TOOL_NAMES, WRITING_TOOL_NAMES
is_perception = tool_name in PERCEPTION_TOOL_NAMES
cache.invalidate_by_prefix([f"{name}:" for name in PERCEPTION_TOOL_NAMES])
```

**hooks.py**：`TOOL_HOOKS` 保留不变（它是 hook 注册表，不是分类常量）。但如果未来 hook 注册按分类走，可进一步声明式化。

**不变**：`TOOL_COST_TIER` 字典留在 `registry.py` 原位，语义独立。

---

## 优化 #4：advance_phase session 封装

### 问题

`advance_phase.py` 直接操作 `SessionLocal()`，自行管理 session 的 begin/commit/rollback/`refresh(with_for_update=True)` 行锁。171 行中约 80 行是 DB session 管理和并发控制逻辑。工具层不应感知 DB session 的存在。

### 方案

新建 `WorkflowStore`（与现有 11 个 Store 模式对齐），在 `KnowledgeBaseService` 上新增 `kb.workflows` 属性。

### WorkflowStore 接口

```python
class WorkflowStore(_BaseStore):
    def get_current_phase(self) -> str:
        """获取当前阶段（无锁读取）。

        返回 Phase enum 的 value 字符串，如 "incubation"。
        不存在时创建默认行（Phase.INCUBATION）。
        内部调用 get_or_create_workflow_state 复用现有 upsert 逻辑。
        """

    def advance(
        self,
        direction: str,
        expected_current: str | None = None,
    ) -> dict:
        """推进或回退阶段（带行锁）。

        Args:
            direction: "forward" | "backward"
            expected_current: 乐观锁——如果不为 None 且与实际阶段不同，
                              返回冲突错误而不写入

        Returns:
            {
                "current_phase": str,       # 变更前阶段
                "new_phase": str,           # 变更后阶段（未变更时与 current_phase 相同）
                "advanced": bool,           # 是否实际发生阶段变更
                "conflict": bool,           # 是否检测到并发冲突
            }
        """
```

### WorkflowStore 内部实现要点

- `get_current_phase()` 和 `advance()` 都使用 `self.session()` 管理 DB session，与现有 Store 模式一致
- 内部调用 `from app.utils.workflow import get_or_create_workflow_state` 复用 PostgreSQL/SQLite 兼容的 upsert 逻辑，不重新实现
- `advance()` 中的行锁逻辑：在 `self.session()` 内使用 `db.refresh(ws, with_for_update=True)` 获取行锁后，校验 `expected_current` 与实际阶段是否一致，一致则写入，不一致则返回 `conflict=True`
- `advance()` 中写操作需要持锁写入，不能用 `self.session()` 的自动 commit，需在 `self.session()` 内手动 commit（与 `advance_phase.py` 现有行为一致：获取行锁 → 校验 → 写入 → commit → 释放锁）

### advance_phase 工具简化

```python
@tool
async def advance_phase(direction: str = "forward") -> dict:
    """推进或回退创作阶段。

    direction="forward"：根据知识库完整度判断是否可以进入下一阶段。
    direction="backward"：回退到上一阶段（Writing→Structure，Structure→Incubation）。

    Args:
        direction: 方向 - "forward"(推进) 或 "backward"(回退)
    """
    project_id = get_project_id()
    if project_id is None:
        raise ValueError("project_id not set in tool context")

    kb = _kb()

    # 阶段标签: 使用字符串 key 与 current_phase 类型一致
    phase_labels = {
        "incubation": "创意孵化",
        "structure": "结构设计",
        "writing": "写作中",
        "revision": "修订中",
    }

    # 1. 读取当前阶段
    current_phase = kb.workflows.get_current_phase()

    # 2. 计算目标阶段（逻辑不变，仍在工具层）
    if direction == "backward":
        # 使用字符串 key/value, 与 WorkflowStore.advance() 保持一致
        backward_map = {
            "writing": "structure",
            "structure": "incubation",
        }
        if current_phase not in backward_map:
            return {
                "current_phase": current_phase,
                "suggested_phase": current_phase,
                "advanced": False,
                "direction": direction,
                "reason": f"当前阶段「{phase_labels.get(current_phase, current_phase)}」不可回退",
                "current_phase_label": phase_labels.get(current_phase, current_phase),
                "suggested_phase_label": phase_labels.get(current_phase, current_phase),
            }
        suggested_phase = backward_map[current_phase]
        reason = f"从「{phase_labels.get(current_phase, current_phase)}」回退到「{phase_labels.get(suggested_phase, suggested_phase)}」"
    else:
        suggested_phase, reason = _evaluate_forward(current_phase, kb)

    # 3. 执行带锁写入
    advanced = suggested_phase != current_phase
    if advanced:
        result = kb.workflows.advance(direction, expected_current=current_phase)
        if result.get("conflict"):
            return {
                "current_phase": current_phase,
                "suggested_phase": suggested_phase,
                "advanced": False,
                "direction": direction,
                "reason": "并发更新检测：阶段已被其他请求更新",
                "current_phase_label": phase_labels.get(current_phase, current_phase),
                "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
            }

    return {
        "current_phase": current_phase,
        "suggested_phase": suggested_phase,
        "advanced": advanced,
        "direction": direction,
        "reason": reason,
        "current_phase_label": phase_labels.get(current_phase, current_phase),
        "suggested_phase_label": phase_labels.get(suggested_phase, suggested_phase),
    }
```

预计代码量从 171 行降至 ~80 行。

### KnowledgeBaseService 变化

```python
# knowledge_base.py
from app.agents.services.stores import WorkflowStore

class KnowledgeBaseService:
    def __init__(self, project_id: int):
        ...
        self.workflows = WorkflowStore(project_id)
```

### stores/__init__.py 变化

```python
from app.agents.services.stores.workflow_store import WorkflowStore

__all__ = [
    ...,
    "WorkflowStore",
]
```

### 并发安全

`WorkflowStore.advance()` 内部使用 `with_for_update=True` 行锁 + `expected_current` 乐观锁双重保障，与当前 `advance_phase` 的并发控制逻辑等价。

### 注意：WorkflowStore.advance() 的 session 管理差异

`_BaseStore.session()` 上下文管理器在正常退出时自动 commit，异常时 rollback。但 `advance()` 需要"获取行锁 → 校验 → 写入 → commit"的精确控制。实现时需注意：

- 校验失败时不应 commit，但也不应 raise（而是返回 `conflict=True`）
- 方案：在 `self.session()` 内部手动控制，校验失败时 `db.rollback()` 后返回结果（不 raise），session 上下文管理器在 finally 中 close

---

## 不在本次范围的内容

- P2：consistency_scan 拆分、批量确认拆分、JSON 参数装饰器
- P3：knowledge_search 降级路径重构、auto 模式优化、review/rewrite 返回值文档化、registry_v2 缓存项目章节数
- 前端 REST API 变更
- 数据库模型变更

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 合并后 Agent 不理解"填 id 则更新"的模式 | 更新 docstring，在工具描述首行说明双模式 |
| 合并后 create 路径缺少必填校验，Agent 创建无名角色 | create 路径加必填字段校验，缺则返回 error |
| 参数默认值 `None` 导致 create 路径类型不安全 | create 路径用 `if val:` 过滤（None/"" 都是 falsy），行为与原 create 工具一致 |
| 前端 AgentChatPanel 工具名映射过期 | 同步更新映射表，基于返回值判断显示"创建"还是"更新" |
| 工具代码中硬编码的 update_* 工具名引用（如 delete_plot_block 的 hint） | 全局扫描并更新所有引用 |
| Store 新增 `get_by_id` 方法遗漏 project_id 过滤 | 遵循 _BaseStore 模式，所有查询都带 project_id 条件 |
| WorkflowStore 并发逻辑与现有行为不一致 | 复用 get_or_create_workflow_state，保留行锁 + 乐观锁双保障，迁移后跑 advance_phase 相关测试验证 |
| WorkflowStore.advance() 的 session 管理与 _BaseStore 默认行为不同 | advance() 内部手动控制 commit/rollback，校验失败不 raise 只返回 conflict |
| 删除 update_* 工具后旧测试失败 | 先更新测试，再删除工具文件 |
| REST API 层 update_* 函数名误改 | 明确 API 层（`api/`）和 Store 方法名不在合并范围 |

---

## 验收标准

1. 工具数从 33 降至 28，所有 update_* 工具已删除
2. 合并后的 create 工具 create 路径和 update 路径行为与原工具等价
3. create 路径保留必填字段校验（name/role 等），缺失时返回 error
4. update 路径参数默认 `None`，`None` 不修改，`""` 清空字段（与原 update 工具一致）
5. 所有 N+1 查询位置（含 `_get_current_value` 和 `delete_plot_block`）改为 `get_by_id()` 直接查询
6. 感知/写入工具名只在 `registry.py` 定义一次，`agent_graph.py` 引用常量
7. `advance_phase` 不再直接操作 `SessionLocal()`，通过 `kb.workflows` 调用
8. 前端 `AgentChatPanel.tsx` 工具名映射已更新
9. `delete_plot_block.py` 等 hint 文本中不再引用已删除的 update_* 工具名
10. REST API 层和 Store 方法名不变
11. `docker exec novelagent-backend-1 pytest -v` 全部通过
12. 前端功能不受影响
