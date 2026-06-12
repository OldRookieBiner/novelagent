# Store 接口签名

所有 Store 返回 `dict | list[dict] | None`。序列化在 Store 内部完成，去掉 `created_at`/`updated_at`。

Store 通过 `_BaseStore` 继承 `session()` 上下文管理器。公开方法自动开/关 session；`_*_with_session(db)` 内部方法接受外部传入的 db，仅供 KB facade 编排使用，外部调用方不应直接调用。

---

## OutlineStore

管理：Outline, ChapterOutline

```python
class OutlineStore:
    def __init__(self, project_id: int): ...

    # --- Outline ---
    def get(self) -> dict | None:
        """获取项目大纲"""

    def update(self, data: dict) -> dict:
        """更新大纲（单实例，不需要传 id）"""

    def upsert(self, data: dict) -> dict:
        """创建或更新大纲（单实例 upsert，用于初始化流程）"""

    # --- ChapterOutline ---
    def get_chapter_outline(self, chapter_number: int) -> dict | None:
        """获取指定章节的大纲"""

    def list_chapter_outlines(self) -> list[dict]:
        """列出所有章节大纲"""

    def create_chapter_outline(self, data: dict) -> dict:
        """创建章节大纲"""

    def update_chapter_outline(self, chapter_number: int, data: dict) -> dict:
        """更新章节大纲（按 chapter_number 定位）"""

    # --- 内部方法（共享 session）---
    def _read_with_session(self, db) -> dict | None: ...
    def _read_chapter_outlines_with_session(self, db) -> list[dict]: ...
```

**设计决策**：

- `update(data)` 不需要传 id——每个项目只有一个 Outline 实例，Store 内部按 `project_id` 定位。消除了调用方"先读再取 id"的模式。
- `upsert(data)` 用于初始化流程——存在则更新、不存在则创建。消除了 initialization.py 中直接 `SessionLocal()` 操作 Outline 的代码。
- `get_chapter_outline(chapter_number)` 是新增方法——当前 KB 没有，agent_context.py 直接 `SessionLocal()` 绕过去。迁入后消除那个直接 DB 访问。
- ChapterOutline 归 OutlineStore 管理（而非 ChapterStore），因为 ChapterOutline 的语义是"大纲视角的章节蓝图"。ChapterStore 需要章节大纲数据时，通过 OutlineStore 的内部方法获取。

---

## WorldSettingStore

管理：WorldSetting

```python
class WorldSettingStore:
    def __init__(self, project_id: int): ...

    def get(self) -> dict | None:
        """获取项目世界观"""

    def create(self, data: dict) -> dict:
        """创建世界观"""

    def update(self, data: dict) -> dict:
        """更新世界观（单实例，不需要传 id）"""

    def update_by_id(self, setting_id: int, data: dict) -> dict:
        """按 id 更新（供 API 端点和 impact decision 使用）"""

    # --- 内部方法 ---
    def _read_with_session(self, db) -> dict | None: ...
```

**设计决策**：

- `update(data)` 单实例方法——消除了 `kb.get_world_setting()` → `setting.id` → `kb.update_world_setting(setting.id, data)` 的两步操作。
- `update_by_id(setting_id, data)` 保留——API 端点和 `_apply_change` 场景已有 target_id，直接按 id 更新更精确。

---

## CharacterStore

管理：Character, Relation, EvolutionPlan, EvolutionRecord

```python
class CharacterStore:
    def __init__(self, project_id: int): ...

    # --- Character ---
    def list_characters(self) -> list[dict]:
        """列出所有角色"""

    def get_character(self, character_id: int) -> dict | None:
        """获取单个角色"""

    def create_character(self, data: dict) -> dict:
        """创建角色"""

    def update_character(self, character_id: int, data: dict) -> dict:
        """更新角色（直接字段更新，用于 impact decision 的 apply）"""

    # --- Relation ---
    def list_relations(self) -> list[dict]:
        """列出所有关系"""

    def create_relation(self, data: dict) -> dict:
        """创建关系"""

    def update_relation(self, relation_id: int, data: dict) -> dict:
        """更新关系"""

    def get_relations_by_character_names(self, names: list[str]) -> list[dict]:
        """获取涉及指定角色名的关系"""

    # --- EvolutionPlan ---
    def list_evolution_plans_triggering_at(self, chapter_number: int) -> list[dict]:
        """获取在指定章节触发的关系演变规划"""

    def list_relations_with_plans(self) -> list[dict]:
        """获取所有关系及其演变规划（嵌套 dict）"""

    def create_evolution_plan(self, data: dict) -> dict:
        """创建演变规划"""

    def mark_evolution_plan_triggered(self, relation_id: int, chapter_number: int) -> list[dict]:
        """标记指定章节的演变规划为已触发"""

    def update_relation_trust_level(self, relation_id: int, new_trust_level: int) -> None:
        """更新关系信任度"""

    # --- EvolutionRecord ---
    def create_evolution_record(self, data: dict) -> dict:
        """创建演变记录（幂等：同章节同关系只创建一条）"""

    # --- 内部方法 ---
    def _read_all_characters_with_session(self, db) -> list[dict]: ...
    def _read_all_relations_with_session(self, db) -> list[dict]: ...
```

**设计决策**：

- `list_relations_with_plans` 当前返回 `{"relation": orm, "plans": [orm]}`。拆分后在 Store 内部解析为纯 dict，嵌套关系扁平化：

```python
# 返回值示例
{
    "id": 1,
    "character_a_id": 3,
    "character_b_id": 5,
    "relation_type": "信任",
    "current_status": "战友",
    "trust_level": 80,
    "plans": [
        {"id": 10, "trigger_chapter": 8, "event_description": "...", "status_after": "决裂", ...}
    ]
}
```

这消除了 agent_context.py 中 `plan.relation.character_a.name` 的 lazy-loaded 访问风险。Store 内部在同一 session 内完成关系名解析，返回扁平 dict。

---

## PlotStore

管理：PlotBlock, PlotQuestion, Subplot

```python
class PlotStore:
    def __init__(self, project_id: int): ...

    # --- PlotBlock ---
    def list_plot_blocks(self) -> list[dict]: ...
    def get_current_plot_block(self, chapter_number: int) -> dict | None: ...
    def create_plot_block(self, data: dict) -> dict: ...
    def update_plot_block(self, block_id: int, data: dict) -> dict: ...
    def delete_plot_block(self, block_id: int) -> None: ...

    # --- PlotQuestion ---
    def list_plot_questions(self, status: str | None = None) -> list[dict]: ...
    def get_questions_for_chapter(self, chapter_number: int) -> list[dict]: ...
    def create_plot_question(self, data: dict) -> dict: ...
    def update_plot_question(self, question_id: int, data: dict) -> dict: ...

    # --- Subplot ---
    def list_subplots(self) -> list[dict]: ...
    def create_subplot(self, data: dict) -> dict: ...
    def update_subplot(self, subplot_id: int, data: dict) -> dict: ...
    def delete_subplot(self, subplot_id: int) -> None: ...

    # --- 内部方法 ---
    def _read_all_with_session(self, db) -> dict: ...
```

`_read_all_with_session` 返回 `{"plot_blocks": [...], "plot_questions": [...], "subplots": [...]}`，供 `batch_read_for_index` 一次读取。

---

## ForeshadowingStore

管理：Foreshadowing

```python
class ForeshadowingStore:
    def __init__(self, project_id: int): ...

    def get(self, foreshadowing_id: int) -> dict | None: ...
    def list_foreshadowings(self, status: str | None = None) -> list[dict]: ...
    def list_pending(self) -> list[dict]:
        """status='pending_reclaim'"""
    def list_overdue(self, current_chapter: int) -> list[dict]:
        """active/pending_reclaim 且 expected_resolve_chapter < current"""
    def create(self, data: dict) -> dict: ...
    def update(self, foreshadowing_id: int, data: dict) -> dict: ...

    # --- 内部方法 ---
    def _read_all_with_session(self, db) -> list[dict]: ...
    def _create_with_session(self, db, data: dict) -> dict: ...
```

`_create_with_session` 供 `write_chapter_with_tracking` 编排方法使用。

---

## StyleStore

管理：StyleConstraints, StyleSnapshot

```python
class StyleStore:
    def __init__(self, project_id: int): ...

    def get_constraints(self) -> dict | None: ...
    def create_constraints(self, data: dict) -> dict: ...
    def update_constraints(self, data: dict) -> dict:
        """更新风格约束（单实例，不需要传 id）"""
    def update_constraints_by_id(self, constraints_id: int, data: dict) -> dict:
        """按 id 更新（供 API 端点和 impact decision 使用）"""

    def list_snapshots(self, last_n: int | None = None) -> list[dict]: ...
    def create_snapshot(self, data: dict) -> dict: ...

    # --- 内部方法 ---
    def _read_constraints_with_session(self, db) -> dict | None: ...
    def _create_snapshot_with_session(self, db, data: dict) -> dict: ...
```

**设计决策**：

- `update_constraints(data)` 单实例方法——和 WorldSettingStore 同理，消除先读再取 id。
- `update_constraints_by_id(constraints_id, data)` 保留——供 API 端点和 impact decision 使用。

---

## TimelineStore

管理：TimelineEntry, SceneEntry

```python
class TimelineStore:
    def __init__(self, project_id: int): ...

    def list_timeline(self, chapter_range: tuple[int, int] | None = None) -> list[dict]: ...
    def create_timeline_entry(self, data: dict) -> dict: ...

    def list_scene_entries(self, chapter_number: int | None = None) -> list[dict]: ...
    def create_scene_entry(self, data: dict) -> dict: ...

    # --- 内部方法 ---
    def _read_all_with_session(self, db) -> dict: ...
    def _create_with_session(self, db, data: dict) -> dict: ...
```

---

## VolumeStore

管理：Volume, CrossVolumeForeshadowing, CrossVolumeSubplot, CharacterChangeLog

```python
class VolumeStore:
    def __init__(self, project_id: int): ...

    # --- Volume ---
    def list_volumes(self) -> list[dict]: ...
    def get_volume(self, volume_number: int) -> dict | None: ...
    def get_current_volume(self) -> dict | None: ...
    def create_volume(self, data: dict) -> dict: ...
    def update_volume(self, volume_id: int, data: dict) -> dict: ...

    # --- CrossVolume ---
    def list_cross_volume_foreshadowings(self, status: str | None = None) -> list[dict]: ...
    def create_cross_volume_foreshadowing(self, data: dict) -> dict: ...
    def update_cross_volume_foreshadowing(self, cvf_id: int, data: dict) -> dict: ...

    def list_cross_volume_subplots(self, status: str | None = None) -> list[dict]: ...
    def create_cross_volume_subplot(self, data: dict) -> dict: ...
    def update_cross_volume_subplot(self, cvs_id: int, data: dict) -> dict: ...

    # --- CharacterChangeLog ---
    def list_character_change_logs(self, volume_number: int | None = None) -> list[dict]: ...
    def create_character_change_log(self, data: dict) -> dict: ...

    # --- 内部方法 ---
    def _read_volume_for_index_with_session(self, db, volume_number: int) -> dict: ...
```

---

## ChapterStore

管理：Chapter

```python
class ChapterStore:
    def __init__(self, project_id: int): ...

    def get_by_number(self, chapter_number: int) -> dict | None:
        """获取章节正文（含 content）"""

    def save_content(self, chapter_number: int, content: str, word_count: int = 0) -> dict:
        """保存章节正文"""

    def search_references(self, keywords: list[str], max_chapters: int = 50) -> list[dict]:
        """搜索包含关键词的章节段落（跨 ChapterOutline + Chapter 联合查询）"""

    # --- 内部方法 ---
    def _read_with_session(self, db, chapter_number: int) -> dict | None: ...
    def _create_with_session(self, db, data: dict) -> dict: ...
```

**设计决策**：

- 不设 `get_by_number_without_content`——当前所有调用方都需要 content（consistency_check 提取角色名、style_analysis 做风格分析、agent_context 取上一章结尾）。YAGNI。
- `search_references` 涉及 ChapterOutline + Chapter 两张表的联合查询。ChapterOutline 的数据通过 OutlineStore 的内部方法获取，Chapter 本身在 ChapterStore 内部查询。整体作为 KB facade 的编排方法暴露，但实现可以放在 ChapterStore 内部（因为它发起查询、OutlineStore 只是提供数据）。

---

## ChangeStore

管理：SettingChange

```python
class ChangeStore:
    def __init__(self, project_id: int): ...

    def get(self, change_id: int) -> dict | None: ...
    def list_changes(self, status: str | None = None) -> list[dict]: ...
    def create(self, data: dict) -> dict: ...
    def update(self, change_id: int, data: dict) -> dict: ...
```

---

## KnowledgeBaseService (facade)

```python
class KnowledgeBaseService:
    """知识库读写服务 — thin facade

    委托给各 Store，提供跨 Store 编排方法。
    """

    def __init__(self, project_id: int):
        self.project_id = project_id
        self.outlines = OutlineStore(project_id)
        self.world_setting = WorldSettingStore(project_id)
        self.characters = CharacterStore(project_id)
        self.plots = PlotStore(project_id)
        self.foreshadowings = ForeshadowingStore(project_id)
        self.styles = StyleStore(project_id)
        self.timelines = TimelineStore(project_id)
        self.volumes = VolumeStore(project_id)
        self.chapters = ChapterStore(project_id)
        self.changes = ChangeStore(project_id)

    # --- Session 管理 ---
    @contextmanager
    def session(self, readonly=False):
        """上下文管理器：创建独立 DB session"""

    # --- 故事种子（项目元数据，不属于任何 Store）---
    def get_story_seed(self) -> str | None: ...
    def update_story_seed(self, story_seed: str) -> None: ...

    # --- 跨 Store 编排方法 ---

    def write_chapter_with_tracking(
        self,
        chapter_data: dict,
        timeline_data: dict | None = None,
        foreshadowing_data: list[dict] | None = None,
        snapshot_data: dict | None = None,
    ) -> dict:
        """原子写入章节 + 追踪数据"""

    def batch_read_for_index(self) -> dict:
        """单次 session 批量读取所有知识库数据"""

    def batch_read_volume_for_index(self, volume_number: int) -> dict:
        """单次 session 批量读取指定卷数据"""

    def validate_prerequisites(self, current_chapter: int | None = None) -> dict:
        """校验写作前置条件（从 agent_context.py 迁入）"""

    def search_chapters_for_references(self, keywords: list[str], max_chapters: int = 50) -> list[dict]:
        """搜索包含关键词的章节段落（跨 ChapterOutline + Chapter 联合查询）"""
```

**设计决策**：

- 属性式访问（`kb.characters.list_characters()`）而非方法式（`kb.list_characters()`）。方法式意味着 KB 上要有 60+ 个转发方法，和现在没区别。属性式让 KB facade 保持薄——只有编排方法和故事种子。
- `search_chapters_for_references` 保留在 KB facade——它涉及 ChapterOutline + Chapter 两张表的联合查询，是跨 Store 的编排方法。
- 故事种子直接在 KB facade 上操作 Project 表——它是项目元数据，不属于任何知识库实体。
- **不保留便捷方法**（如 `kb.get_outline()` → `kb.outlines.get()`）。迁移时直接改为 Store 属性式访问，不留中间态。

---

## _with_session 内部方法的可见性约定

Python 没有真正的访问控制。`_with_session` 方法以 `_` 前缀标记为内部使用，仅在 KB facade 的编排方法中调用。外部调用方不应直接调用。

代码审查时将 `_with_session` 的使用范围作为检查项。在 `_BaseStore` 的文档字符串中明确标注。

---

## 字段裁剪和内容截断

Store 返回全量 dict。调用方按需裁剪和截断：

- agent_context.py 的 `_load_writing_context` 只需要伏笔的前 60 字 → 在 agent_context 层面做 `f["content"][:60]`
- agent_context 只需要 character 的部分字段 → 在 agent_context 层面挑选 dict key

这不属于 Store 的职责。Store 不知道调用方的 token 预算约束。
