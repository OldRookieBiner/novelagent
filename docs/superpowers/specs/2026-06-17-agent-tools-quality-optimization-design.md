# Agent 工具质量优化设计

> 日期：2026-06-17
> 范围：P0+P1，共 4 项优化
> 目标：减少工具数量、消除 N+1 查询、集中硬编码常量、封装 DB session

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

### 合并后 create 工具的内部路由逻辑

以 `create_character` 为例：

```python
@tool
async def create_character(
    character_id: int = 0,  # 新增：非零时为更新模式
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
    """创建新角色或更新已有角色。提供 character_id 时为更新模式。

    - character_id=0（默认）：创建新角色
    - character_id>0：更新指定 ID 的角色，None 值字段不修改
    """
    kb = _kb()

    if character_id:
        # --- 更新路径 ---
        before = kb.characters.get_by_id(character_id)
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
        # --- 创建路径（与原 create_character 逻辑一致）---
        data = {"name": name, "role": role}
        for key, val in [
            ("personality", personality), ("catchphrase", catchphrase),
            ("habit_action", habit_action), ("deep_fear", deep_fear),
            ("core_motivation", core_motivation), ("growth_arc", growth_arc),
            ("appearance", appearance), ("backstory", backstory),
            ("signature_item", signature_item),
        ]:
            if val:
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

### create_foreshadowing 的批量模式保留

`update_foreshadowing` 有 `foreshadowing_ids` 批量更新功能。合并后 `create_foreshadowing` 需同时支持：

- `foreshadowing_id > 0`：单条更新
- `foreshadowing_ids` 非空：批量更新状态
- 两者都不提供：创建新伏笔

三种模式的互斥逻辑与原 `update_foreshadowing` 一致。

### registry.py 变化

- 删除 5 个 `update_*` 的 import：`update_character`、`update_foreshadowing`、`update_plot_block`、`update_subplot`、`update_plot_question`
- `_STRUCTURE_EXTRA` 和 `_WRITING_EXTRA` 中移除上述 5 个条目
- `AGENT_TOOLS = WRITING_TOOLS` 无需改动（列表已自动不包含被删的 import）

### 下游影响

- **前端**：不受影响（走 REST API）
- **知识库数据**：底层 Store 方法调用不变
- **SSE 事件流**：不受影响
- **后端测试**：`test_agent_tools.py` 等需更新工具名引用
- **Agent 行为**：从"选 create 还是 update"变为"填不填 id"，docstring 需清晰说明

### 工具数变化

33 → 28（减少 5 个）

---

## 优化 #2：N+1 查询消除

### 问题

4 个更新路径（合并进 create 后）先用 `list_*()` 获取全量数据再遍历找目标 ID。当实体数量多时，每次更新都加载全部同类实体，是性能问题也是局部性问题。

### Store 现有方法盘点

| Store | 已有 `get_by_id` 类方法 | 需补的方法 |
|---|---|---|
| CharacterStore | ❌ | `get_by_id(id: int) -> dict | None` |
| PlotStore | ❌ | `get_plot_block_by_id(id)` / `get_subplot_by_id(id)` / `get_plot_question_by_id(id)` |
| ForeshadowingStore | ✅ 已有 `get(id)` | 无需补 |
| StyleStore | ✅ 已有 `get_constraints()`（单例） | 无需补 |

### 新增 Store 方法签名

```python
# CharacterStore
def get_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个角色，不存在返回 None"""

# PlotStore
def get_plot_block_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个情节块，不存在返回 None"""

def get_subplot_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个支线，不存在返回 None"""

def get_plot_question_by_id(self, id: int) -> dict | None:
    """按 ID 获取单个问题，不存在返回 None"""
```

内部实现：`SessionLocal()` + `db.get(Model, id)` + `project_id` 过滤，与现有 Store 方法模式一致。返回 `dict`（通过 `_to_dict` 转换），不存在返回 `None`。

### `build_changes_diff` 提取

4 个更新路径都有"对比 before/after 构建变更记录"的逻辑，提取到 `utils.py`：

```python
def build_changes_diff(before: dict, update_data: dict) -> dict:
    """对比 before 和 update_data，返回 {field: {before, after}} 格式的变更记录。

    只包含实际发生变化的字段（before[key] != update_data[key]）。
    """
    changes = {}
    for key, new_val in update_data.items():
        old_val = before.get(key)
        if old_val != new_val:
            changes[key] = {"before": old_val, "after": new_val}
    return changes
```

### 合并后 create 工具的更新路径替换

```python
# 旧：N+1 查询
chars = kb.characters.list_characters()
for c in chars:
    if c["id"] == character_id:
        before = c

# 新：直接查询
before = kb.characters.get_by_id(character_id)
```

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

    # 阶段标签
    phase_labels = {
        Phase.INCUBATION: "创意孵化",
        Phase.STRUCTURE: "结构设计",
        Phase.WRITING: "写作中",
        Phase.REVISION: "修订中",
    }

    # 1. 读取当前阶段
    current_phase = kb.workflows.get_current_phase()

    # 2. 计算目标阶段（逻辑不变，仍在工具层）
    if direction == "backward":
        backward_map = {
            Phase.WRITING: Phase.STRUCTURE,
            Phase.STRUCTURE: Phase.INCUBATION,
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

### 并发安全

`WorkflowStore.advance()` 内部使用 `with_for_update=True` 行锁 + `expected_current` 乐观锁双重保障，与当前 `advance_phase` 的并发控制逻辑等价。

---

## 不在本次范围的内容

- P2：consistency_scan 拆分、批量确认拆分、JSON 参数装饰器
- P3：knowledge_search 降级路径重构、auto 模式优化、review/rewrite 返回值文档化、registry_v2 缓存项目章节数
- 前端改动
- REST API 变更
- 数据库模型变更

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 合并后 Agent 不理解"填 id 则更新"的模式 | 更新 docstring，在工具描述首行说明双模式 |
| Store 新增 `get_by_id` 方法遗漏 project_id 过滤 | 遵循 _BaseStore 模式，所有查询都带 project_id 条件 |
| WorkflowStore 并发逻辑与现有行为不一致 | 保留行锁 + 乐观锁双保障，迁移后跑 advance_phase 相关测试验证 |
| 删除 update_* 工具后旧测试失败 | 先更新测试，再删除工具文件 |

---

## 验收标准

1. 工具数从 33 降至 28，所有 update_* 工具已删除
2. 合并后的 create 工具 create 路径和 update 路径行为与原工具等价
3. 4 个更新路径不再使用 `list_*()` 遍历，改为 `get_by_id()` 直接查询
4. 感知/写入工具名只在 `registry.py` 定义一次，`agent_graph.py` 和 `hooks.py` 引用常量
5. `advance_phase` 不再直接操作 `SessionLocal()`，通过 `kb.workflows` 调用
6. `docker exec novelagent-backend-1 pytest -v` 全部通过
7. 前端功能不受影响
