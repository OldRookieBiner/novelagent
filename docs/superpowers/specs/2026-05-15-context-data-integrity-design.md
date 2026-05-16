# 上下文传递数据完整性与策略优化设计

## 背景

当前上下文传递机制存在数据完整性和功能缺口，根源是 **DB schema 缺列** 导致数据写入后丢失，以及 **`build_initial_state` 只加载部分字段** 导致节点拿不到完整数据。

### 根源问题分析

| 问题 | 根源 | 表现 |
|------|------|------|
| `turning_point`/`hook`/`transition` 丢失 | `chapter_outlines` 表缺三列 | `parse_single_chapter_outline` 解析出的字段无法持久化，DB 读回为 None |
| `evolution_plans`/`evolution_records` 为空 | `build_initial_state` 不加载，且模型无 `project_id` 需 join 查询 | 节点拿不到角色演变数据，`format_evolution_info` 永远返回空 |
| `characters` 字段映射错位 | DB 有 `backstory`/`signature_item`/`catchphrase`/`habit_action`/`deep_fear`，`build_initial_state` 和 `format_characters_info` 用了不存在的 `age`/`skills`/`goals`/`background` | DB 有数据但 LLM 看不到 |
| SSE 端点自定义 prompt 不生效 | `_prompts` 只在 `run_workflow` 注入，SSE 端点不经过 `run_workflow` | 用户自定义 prompt 对审核/重写/生成端点无效 |
| HybridContentStrategy 未实现 | 用户选 hybrid 策略时抛 `NotImplementedError` | 长篇小说无法使用混合策略 |
| review/rewrite 硬编码策略 | 直接 `FulltextContentStrategy()`，不读用户选择 | 用户选 hybrid 策略对审核/重写不生效 |

## 优化项

### 1. DB Schema 补全：`chapter_outlines` 表加列

**文件：** 新增 Alembic 迁移

`parse_single_chapter_outline` 解析出 `turning_point`、`hook`、`transition` 三个字段，但 `chapter_outlines` 表没有这三列，数据写入后丢失。这是所有下游数据缺失的根源。

**迁移：** `backend/alembic/versions/YYYYMMDD_add_chapter_outline_fields.py`

```python
def upgrade():
    op.add_column('chapter_outlines', sa.Column('turning_point', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('hook', sa.Text(), nullable=True))
    op.add_column('chapter_outlines', sa.Column('transition', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('chapter_outlines', 'transition')
    op.drop_column('chapter_outlines', 'hook')
    op.drop_column('chapter_outlines', 'turning_point')
```

**ORM 补全：** `backend/app/models/outline.py` ChapterOutline 类

```python
turning_point = Column(Text, nullable=True)
hook = Column(Text, nullable=True)
transition = Column(Text, nullable=True)
```

**持久化补全：** 修改 `workflow_persistence.py:persist_chapter_outlines` 和 `chapters.py` 的章节大纲创建，写入新字段：

```python
chapter_outline = ChapterOutline(
    ...,
    turning_point=co_data.get("turning_point"),
    hook=co_data.get("hook"),
    transition=co_data.get("transition"),
)
```

### 2. `build_initial_state` 数据完整性修复

**文件：** `backend/app/api/workflow.py`

**2a. 补全 chapter_outlines 字段**

迁移完成后，`build_initial_state` 的 chapter_outlines 构建中加入新列：

```python
chapter_outlines = [
    {
        "chapter_number": co.chapter_number,
        "title": co.title,
        "scene": co.scene,
        "characters": co.characters,
        "plot": co.plot,
        "conflict": co.conflict,
        "turning_point": co.turning_point,  # 新增
        "hook": co.hook,                      # 新增
        "transition": co.transition,          # 新增
        "ending": co.ending,
        "target_words": co.target_words,
    }
    for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
]
```

**2b. 修正 characters 字段映射**

DB Character 模型有 `appearance`、`personality`、`backstory`、`catchphrase`、`habit_action`、`deep_fear`、`core_motivation`、`growth_arc`、`signature_item`。没有 `age`/`skills`/`goals`/`background`。

`format_characters_info` 使用 `appearance`/`personality`/`background`/`skills`/`goals`，其中 `background` 应映射到 DB 的 `backstory`，`skills`/`goals` 在 DB 中不存在。

修正方案：`build_initial_state` 加载 DB 实际存在的字段，`format_characters_info` 按实际字段名读取：

```python
state["characters"] = [
    {
        "id": c.id,
        "name": c.name,
        "role": c.role,
        "appearance": c.appearance or "",
        "personality": c.personality or "",
        "backstory": c.backstory or "",
        "catchphrase": c.catchphrase or "",
        "habit_action": c.habit_action or "",
        "deep_fear": c.deep_fear or "",
        "core_motivation": c.core_motivation or "",
        "growth_arc": c.growth_arc or "",
        "signature_item": c.signature_item or "",
    }
    for c in db_characters
]
```

同步修正 `format_characters_info`（`utils.py`），将 `background` 改为 `backstory`，删除不存在的 `skills`/`goals`，补全 DB 实际存在的字段：

```python
def format_characters_info(state: dict) -> str:
    detailed_characters = state.get("characters", [])
    characters = state.get("outline_characters", [])
    info = state.get("collected_info", {})

    if detailed_characters:
        chars_str = "【详细人物设定】\n"
        for c in detailed_characters:
            chars_str += f"- {c.get('name', '')}（{c.get('role', '配角')}）：\n"
            if c.get("appearance"):
                chars_str += f"  外貌：{c.get('appearance')}\n"
            if c.get("personality"):
                chars_str += f"  性格：{c.get('personality')}\n"
            if c.get("backstory"):
                chars_str += f"  背景：{c.get('backstory')}\n"
            if c.get("catchphrase"):
                chars_str += f"  口头禅：{c.get('catchphrase')}\n"
            if c.get("habit_action"):
                chars_str += f"  习惯动作：{c.get('habit_action')}\n"
            if c.get("deep_fear"):
                chars_str += f"  深层恐惧：{c.get('deep_fear')}\n"
            if c.get("core_motivation"):
                chars_str += f"  核心动机：{c.get('core_motivation')}\n"
            if c.get("growth_arc"):
                chars_str += f"  成长弧线：{c.get('growth_arc')}\n"
            if c.get("signature_item"):
                chars_str += f"  标志性物品：{c.get('signature_item')}\n"
        return chars_str
    elif characters:
        return "\n".join([
            f"- {c.get('name', '')}：{c.get('personality', '')}，动机：{c.get('motivation', '')}"
            for c in characters
        ])
    else:
        return info.get("customProtagonist") or info.get("protagonist", "未指定")
```

**2c. 加载 evolution_plans 和 evolution_records**

EvolutionPlan/Record 没有 `project_id`，需通过 Relation join 查询：

```python
from app.models.character import EvolutionPlan, EvolutionRecord, Relation

# 查询项目所有关系 ID
relation_ids = [r.id for r in db.query(Relation).filter(
    Relation.project_id == project.id
).all()]

# 通过 relation_id 批量查询演变数据
db_plans = db.query(EvolutionPlan).filter(
    EvolutionPlan.relation_id.in_(relation_ids)
).order_by(EvolutionPlan.trigger_chapter).all() if relation_ids else []

db_records = db.query(EvolutionRecord).filter(
    EvolutionRecord.relation_id.in_(relation_ids)
).order_by(EvolutionRecord.chapter_number).all() if relation_ids else []

# 构建 state 数据（字段名与 NovelState 定义对齐）
state["evolution_plans"] = [
    {
        "chapter_number": p.trigger_chapter,
        "character_name": _get_character_name_for_plan(p, db),
        "changes": f"{p.status_before or ''} → {p.status_after}"
    }
    for p in db_plans
]

state["evolution_records"] = [
    {
        "chapter_number": r.chapter_number,
        "character_name": _get_character_name_for_record(r, db),
        "actual_changes": r.content,
    }
    for r in db_records
]
```

其中 `_get_character_name_for_plan/record` 通过 relation_id 找到 Relation，再通过 character_a_id/character_b_id 找到 Character name。避免 N+1 查询，应先批量预加载 Character 和 Relation 的映射：

```python
# 批量预加载：relation_id → (character_a_name, character_b_name)
relation_map = {}
for r in db.query(Relation).filter(Relation.project_id == project.id).all():
    a = next((c for c in db_characters if c.id == r.character_a_id), None)
    b = next((c for c in db_characters if c.id == r.character_b_id), None)
    relation_map[r.id] = (a.name if a else "未知", b.name if b else "未知")
```

### 3. 章节大纲生成补充人物关系和演变上下文

**文件：** `backend/app/agents/nodes/chapter_generation.py`

在 `generate_single_chapter_outline` 函数中，`chars_str = format_characters_info(state)` 之后补充：

```python
# 格式化人物关系
relations_str = format_relations_info(state, chapter_number)

# 格式化演变计划
evolution_str, _ = format_evolution_info(state, chapter_number)

# 合并
combined_chars = chars_str + relations_str + evolution_str
```

然后在 prompt 构建时用 `combined_chars` 替代 `chars_str`。`{characters}` 占位符名不变，内容更丰富。

需在 import 中补充 `format_relations_info` 和 `format_evolution_info`。

### 4. `_prompts` 注入统一化

**文件：** `backend/app/api/workflow.py`

**问题根源：** `_prompts` 当前在 `run_workflow` 等 3 处端点函数中单独注入，SSE 端点不经过这些函数所以缺失。这不是 SSE 端点的问题，而是 `_prompts` 注入位置不对。

**方案：** 将 `_prompts` 注入移入 `build_initial_state`（统一入口），删除 3 处重复注入。

> 注：`_prompts` 通过 `_build_prompts_dict(db)` 构建，依赖 db 参数。`build_initial_state` 已有 `db` 参数。这是过渡方案——LangGraph 规范应通过 `config` 传递运行时配置，但当前 `_prompts` 作为 state 字段的模式已广泛使用，暂不重构。

```python
# build_initial_state 末尾
if db is not None:
    state["_prompts"] = _build_prompts_dict(db)
```

删除以下 3 处单独注入：
- `stream_workflow_events` 中（约 L436）
- 另一处 workflow 端点（约 L831）
- 第三处 workflow 端点（约 L932）

`chapters.py` 的 SSE 端点无需修改——它们已调用 `build_initial_state(db=db)`，`_prompts` 自动包含。

### 5. 混合上下文策略实现

**文件：** `backend/app/agents/context_strategy.py`

实现 `HybridContentStrategy`，策略为"近 N 章全文 + 远章大纲概要"。远章概要从 `chapter_outlines`（而非 `written_chapters`）提取，避免两个数据源的字段混入同一字典。

**接口变更：** `ContextStrategy.build_previous_context` 新增 `chapter_outlines` 参数：

```python
class ContextStrategy(ABC):
    @abstractmethod
    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
    ) -> str:
        """构建前文上下文文本

        Args:
            written_chapters: 已写章节列表（含 content）
            current_chapter: 当前章节号
            chapter_outlines: 章节大纲列表（远章概要的数据源，可选）
        """
        pass
```

`FulltextContentStrategy` 忽略 `chapter_outlines` 参数（全文策略不需要）。

`HybridContentStrategy` 实现：

```python
class HybridContentStrategy(ContextStrategy):
    """混合策略：近 N 章全文 + 远章大纲概要

    近章提供完整的语言风格和衔接参考，
    远章提供情节线索和伏笔追踪（从 chapter_outlines 提取，无需 LLM 调用）。
    """

    def __init__(self, recent_count: int = 3):
        self.recent_count = recent_count

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
    ) -> str:
        if not written_chapters:
            return "（这是第一章，没有前文）"

        # 分离近章和远章
        recent = []
        distant_nums = []
        for ch in written_chapters:
            ch_num = ch.get("chapter_number", 0)
            if ch_num < current_chapter:
                if current_chapter - ch_num <= self.recent_count:
                    recent.append(ch)
                else:
                    distant_nums.append(ch_num)

        parts = []

        # 远章：从 chapter_outlines 提取概要
        if distant_nums and chapter_outlines:
            outline_map = {co.get("chapter_number"): co for co in chapter_outlines}
            distant_parts = []
            for ch_num in sorted(distant_nums):
                co = outline_map.get(ch_num, {})
                title = co.get("title", "")
                plot = co.get("plot", "")
                conflict = co.get("conflict", "")
                hook = co.get("hook", "")
                summary = f"第{ch_num}章《{title}》"
                if plot:
                    summary += f"\n情节：{plot[:200]}"
                if conflict:
                    summary += f"\n冲突：{conflict}"
                if hook:
                    summary += f"\n钩子：{hook}"
                distant_parts.append(summary)
            if distant_parts:
                parts.append("【前文概要】\n" + "\n\n".join(distant_parts))

        # 近章：全文
        if recent:
            recent_parts = []
            for ch in sorted(recent, key=lambda x: x.get("chapter_number", 0)):
                title = ch.get("title", "")
                content = ch.get("content", "")
                recent_parts.append(f"第{ch.get('chapter_number', 0)}章《{title}》\n{content}")
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"
```

**调用方适配：** 所有 `strategy.build_previous_context` 调用点传入 `chapter_outlines`：

- `chapter_generation.py:_build_chapter_content_messages` — `strategy.build_previous_context(written_chapters, chapter_number, state.get("chapter_outlines", []))`
- `review.py:_build_review_messages` — 同上
- `rewrite.py:_build_rewrite_messages` — 同上

`FulltextContentStrategy` 忽略第三个参数，无需改动。

**策略选择逻辑：** `get_context_strategy` 不改动。用户选 hybrid 时 `_STRATEGY_MAP["hybrid"]` 返回新实现。

### 6. 审核/重写节点策略一致性

**文件：** `backend/app/agents/nodes/review.py`、`backend/app/agents/nodes/rewrite.py`

当前硬编码 `FulltextContentStrategy()`，改为通过 `get_context_strategy` 获取策略，与章节生成节点保持一致：

```python
from app.agents.context_strategy import get_context_strategy

# 替换 strategy = FulltextContentStrategy()
info = state.get("collected_info", {})
target_words = info.get("targetWords", 100000)
strategy_name = info.get("contextStrategy")
strategy = get_context_strategy(target_words, strategy_name)
chapter_outlines = state.get("chapter_outlines", [])
previous_context = strategy.build_previous_context(written_chapters, chapter_number, chapter_outlines)
```

## 涉及文件

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `backend/alembic/versions/YYYYMMDD_add_chapter_outline_fields.py` | 新增 | `chapter_outlines` 表加 `turning_point`/`hook`/`transition` 列 |
| `backend/app/models/outline.py` | 修改 | ChapterOutline ORM 补全三列 |
| `backend/app/utils/workflow_persistence.py` | 修改 | `persist_chapter_outlines` 写入新字段 |
| `backend/app/api/chapters.py` | 修改 | 章节大纲创建写入新字段 |
| `backend/app/api/workflow.py` | 修改 | `build_initial_state` 加载完整数据 + `_prompts` 注入 + 删除重复注入 |
| `backend/app/agents/nodes/utils.py` | 修改 | `format_characters_info` 字段映射修正 |
| `backend/app/agents/nodes/chapter_generation.py` | 修改 | 补充 relations + evolution 上下文 + 传入 chapter_outlines |
| `backend/app/agents/context_strategy.py` | 修改 | 接口加 `chapter_outlines` 参数 + 实现 `HybridContentStrategy` |
| `backend/app/agents/nodes/review.py` | 修改 | 改用 `get_context_strategy` + 传入 chapter_outlines |
| `backend/app/agents/nodes/rewrite.py` | 修改 | 改用 `get_context_strategy` + 传入 chapter_outlines |

## 不涉及

- 前端代码不改动（章节大纲字段已有前端类型定义）
- API 接口不改动
- `SummaryContentStrategy`（LLM 摘要）不实现
- `get_context_strategy` 的自动选择逻辑不改动
- NovelState 的 `evolution_plans`/`evolution_records` 字段结构不改动（与 NovelState TypedDict 定义一致）
