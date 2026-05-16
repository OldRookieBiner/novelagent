# 长篇小说支持设计文档

## 概述

为 NovelAgent 新增长篇小说（20万字+，50-300章）支持能力。核心改动：弧/卷结构规划、写后摘要生成、SummaryContentStrategy 上下文策略、章节大纲面板三级折叠树。

篇幅类型由用户在灵感表单内主动选择（短篇/中篇/长篇），不根据字数自动推断。短篇/中篇功能不受影响。

## 一、篇幅类型

三档，灵感表单内选择：

| 类型 | 上下文策略 | 弧/卷 | 写后摘要 |
|------|-----------|-------|---------|
| 短篇 | fulltext | 无 | 无 |
| 中篇 | hybrid | 无 | 无 |
| 长篇 | summary | 有 | 有 |

选择后联动推荐上下文策略和目标字数建议值，用户仍可手动调整。

传到后端 collected_info 新增字段：`novelLength: "short" | "medium" | "long"`

**保存时机**：novelLength 随灵感表单的防抖自动保存一起写入 `outline.collected_info`，而非仅在运行工作流时传入。这样 `build_initial_state` 总能从 `outline.collected_info` 中读到 novelLength，不需要运行工作流时额外传递。

现有 NovelState 的 `novel_length` 字段（当前闲置）将被启用，值来源于 collected_info.novelLength。

## 二、数据模型

### 2.1 新增 volumes 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| project_id | Integer | FK→projects, CASCADE, NOT NULL | |
| volume_number | Integer | NOT NULL | 卷序号 |
| title | String(200) | | 卷名 |
| summary | Text | nullable | 卷概要（LLM 生成，用户可编辑） |
| created_at | DateTime | default=utcnow | |
| updated_at | DateTime | default=utcnow, onupdate=utcnow | |

约束：`UniqueConstraint(project_id, volume_number)`

删除策略：project CASCADE → volumes → arcs。volume CASCADE → arcs。

Relationship：
- `project = relationship("Project", back_populates="volumes")`
- `arcs = relationship("Arc", back_populates="volume", cascade="all, delete-orphan")`

projects 模型需新增 `volumes = relationship("Volume", back_populates="project", cascade="all, delete-orphan")`。

### 2.2 新增 arcs 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | Integer | PK | |
| volume_id | Integer | FK→volumes, CASCADE, NOT NULL | 所属卷 |
| arc_number | Integer | NOT NULL | 弧序号（卷内递增） |
| title | String(200) | | 弧名 |
| summary | Text | nullable | 弧概要（LLM 生成，用户可编辑） |
| chapter_count | Integer | NOT NULL | 该弧的章节数（规划时确定） |
| created_at | DateTime | default=utcnow | |
| updated_at | DateTime | default=utcnow, onupdate=utcnow | |

约束：`UniqueConstraint(volume_id, arc_number)`

删除策略：arc 删除 → chapter_outlines.arc_id SET NULL（章节保留，弧归属清空）。

Relationship：
- `volume = relationship("Volume", back_populates="arcs")`
- `chapter_outlines = relationship("ChapterOutline", back_populates="arc")`

弧的章节范围不在 arcs 表中存储 start_chapter/end_chapter，通过 chapter_outlines.arc_id 反查聚合。避免双源数据不一致。

### 2.3 修改 chapter_outlines 表

新增字段：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| arc_id | Integer | FK→arcs, nullable, SET NULL | 所属弧。短/中篇为 NULL |

Relationship：
- `arc = relationship("Arc", back_populates="chapter_outlines")`

### 2.4 修改 chapters 表

新增字段：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| summary | Text | nullable | 写后摘要（仅长篇填充） |

## 三、NovelState 变更

### 3.1 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| volumes | list[dict] | [{id, volume_number, title, summary}]。短/中篇为空列表 |
| arcs | list[dict] | [{id, volume_id, volume_number, arc_number, title, summary, chapter_count}]。短/中篇为空列表。volume_number 用于全局排序（arc_number 是卷内递增，不能单独排序） |
| chapter_summaries | Annotated[list[dict], merge_chapter_summaries] | [{chapter_number, summary}]。独立于 written_chapters，语义清晰 |

`merge_chapter_summaries` reducer 逻辑：同 chapter_number 的摘要替换，否则追加。与 written_chapters 的 reducer 模式一致但独立。

### 3.2 修改字段

**written_chapters** 结构不变：`{chapter_number, content, word_count, title}`

**novel_length** 从闲置变为驱动逻辑：`short`/`medium` → 不生成弧/卷，`long` → 触发弧/卷规划节点

**confirmation_type** 新增 `"volume_arc"` 值

### 3.3 修改 reducer

`replace_or_append_chapters` 保持原有整条替换逻辑不变。摘要写入走独立的 `chapter_summaries` 字段和 `merge_chapter_summaries` reducer，不再通过 written_chapters 的合并副作用。

```python
def merge_chapter_summaries(existing: list[dict], new_items: list[dict]) -> list[dict]:
    """摘要 reducer：替换同章节号的摘要或追加新摘要"""
    result = list(existing)
    for new_item in new_items:
        chapter_num = new_item.get("chapter_number")
        existing_idx = None
        for i, s in enumerate(result):
            if s.get("chapter_number") == chapter_num:
                existing_idx = i
                break
        if existing_idx is not None:
            result[existing_idx] = new_item
        else:
            result.append(new_item)
    return result
```

## 四、LangGraph 工作流变更

### 4.1 新增节点

#### volume_arc_planning_node

- **触发条件**：`novel_length == "long"`
- **输入**：大纲数据（title、summary、plot_points、world_setting、outline_emotional_curve）+ 目标总章节数（`state.chapter_count`）
- **输出**：volumes 和 arcs 列表（含每弧 chapter_count），自动计算总 chapter_count
- **行为**：
  1. LLM 根据大纲生成卷/弧划分，每弧指定章节数。**目标总章节数作为硬约束传入 prompt**，LLM 输出的各弧章节数之和不得偏离目标值 ±20%
  2. 总章节数 = 各弧章节数之和，覆盖 `state.chapter_count`
  3. 将 volumes、arcs 写入 state
- **之后**：暂停等待用户确认（`confirmation_type = "volume_arc"`）
- **LLM 调用方式**：流式 `llm.chat_stream()`，长篇弧/卷规划输出量大（5卷×5弧=25个弧），需要 10-20 秒。SSE 发送 chunk 事件让前端知道 LLM 在工作

#### chapter_summary_node

- **触发条件**：`novel_length == "long"` 且审核通过后
- **输入**：当前章节的 content（从 written_chapters 获取）
- **输出**：`chapter_summaries: [{chapter_number, summary}]`（~200字），写入独立的 `chapter_summaries` 字段，不经过 written_chapters
- **行为**：
  1. LLM 流式调用 `llm.chat_stream()` 生成摘要，SSE 发送 chunk 事件让前端显示进度
  2. 将 `{chapter_number, summary}` 写入 state.chapter_summaries（通过 merge_chapter_summaries reducer）
  3. 摘要完成后发送 node_done 事件
- **之后**：进入下一章节生成或结束

### 4.2 工作流图路由

**短/中篇流程不变**：
```
大纲 → 角色 → 关系 → 章节大纲 → 正文 → 审核 → ...
```

**长篇流程**：
```
大纲 → 角色 → 关系 → [弧/卷规划] → 确认 → 章节大纲 → 正文 → 审核 → [摘要] → 下一章
```

路由变更：

| 路由函数 | 变更 |
|----------|------|
| `route_after_relations` | 新增判断：`novel_length == "long"` 且 relations 确认后 → `volume_arc_planning_node`；否则 → `chapter_outlines_node` |
| `route_after_volume_arc` | **新增路由**：确认后 → `chapter_outlines_node` |
| `route_after_review` | 新增判断：审核通过且 `novel_length == "long"` → `chapter_summary_node`；否则 → next_chapter/end |
| `route_after_summary` | **新增路由**：summary 完成后判断，有下一章 → `generate_chapter_content_node`；无 → end |

`route_after_summary` 逻辑与 `route_after_review` 中审核通过的分支一致：

```python
def route_after_summary(state: NovelState) -> Literal["next_chapter", "end"]:
    if state.get("current_chapter", 0) < state.get("chapter_count", 0):
        return "next_chapter"
    return "end"
```

图的边变更：

```python
# 审核 → 摘要或下一章/结束
graph.add_conditional_edges(
    "review_node",
    route_after_review,
    {
        "rewrite": "rewrite_node",
        "next_chapter": "generate_chapter_content_node",
        "chapter_summary": "chapter_summary_node",  # 新增
        "wait_confirm": END,
        "end": END,
    },
)

# 摘要 → 下一章或结束
graph.add_conditional_edges(
    "chapter_summary_node",
    route_after_summary,
    {"next_chapter": "generate_chapter_content_node", "end": END},
)
```

`route_after_review` 的返回值新增 `"chapter_summary"`，当审核通过且 `novel_length == "long"` 时返回此值路由到 `chapter_summary_node`。

### 4.3 chapter_outlines_node 变更

生成章节大纲时，若 `novel_length == "long"` 且 arcs 非空，根据 arcs 的 chapter_count 顺序分配弧标识：

```python
# 弧规划示例：弧1(15章), 弧2(20章), 弧3(18章)
# 生成第1-15章大纲 → volume_number=1, arc_number=1
# 生成第16-35章大纲 → volume_number=1, arc_number=2
# 生成第36-53章大纲 → volume_number=2, arc_number=1
```

注意：volume_arc_planning_node 输出到 state 时 arcs 尚无 DB id（persist 还未执行）。chapter_outlines_node 在 chapter_outlines 数据中写入 `volume_number` 和 `arc_number` 标识弧归属，而非直接写 arc_id。

**persist_chapter_outlines 在持久化时查询 DB 获取 arc_id**：根据 `co_data.get("volume_number")` 和 `co_data.get("arc_number")` 从 DB 查询 Arc 记录，获取真实的 arc_id 写入 ChapterOutline。

短/中篇无 volume_number/arc_number，行为不变。

章节大纲生成的 prompt 中需包含弧/卷信息：`generate_single_chapter_outline` 函数新增 `arc_info` 参数，格式为"当前弧：第N弧《弧名》，本章是本弧第M章"。prompt 模板新增 `{arc_info}` 占位符，长篇填充具体信息，短/中篇填充空字符串。

### 4.4 build_initial_state 变更

新增加载 volumes 和 arcs、novel_length、arc_id、summary：

```python
# 加载弧/卷
volumes = db.query(Volume).filter_by(project_id=project_id).order_by(Volume.volume_number).all()
volume_ids = [v.id for v in volumes]
volume_id_to_num = {v.id: v.volume_number for v in volumes}  # volume_id → volume_number 映射
arcs = db.query(Arc).filter_by(volume_id__in=volume_ids).order_by(Arc.volume_id, Arc.arc_number).all()

state["volumes"] = [{"id": v.id, "volume_number": v.volume_number, "title": v.title, "summary": v.summary} for v in volumes]
state["arcs"] = [
    {
        "id": a.id,
        "volume_id": a.volume_id,
        "volume_number": volume_id_to_num.get(a.volume_id, 1),  # P2-12: 包含 volume_number，供全局排序
        "arc_number": a.arc_number,
        "title": a.title,
        "summary": a.summary,
        "chapter_count": a.chapter_count,
    }
    for a in arcs
]

# P0-4: novel_length 从 collected_info 中读取
collected_info = outline.collected_info or {}
state["novel_length"] = collected_info.get("novelLength", "short")
```

chapter_outlines 加载时新增 arc_id（P2-10）：

```python
chapter_outlines = [
    {
        "chapter_number": co.chapter_number,
        "arc_id": co.arc_id,  # 新增
        # ... 其余字段不变
    }
    for co in sorted(project.chapter_outlines, key=lambda x: x.chapter_number)
]
```

written_chapters 加载时不含 summary（摘要走独立字段 chapter_summaries）。

chapter_summaries 加载（从 chapters 表的 summary 字段聚合）：

```python
chapter_summaries = []
for co in project.chapter_outlines:
    if co.chapter and co.chapter.summary:
        chapter_summaries.append({
            "chapter_number": co.chapter_number,
            "summary": co.chapter.summary,
        })
state["chapter_summaries"] = chapter_summaries
```

### 4.6 弧/卷规划确认

新增节点必须注册到 `NODE_PERSIST_MAP`（workflow_persistence.py），确保节点输出写入 DB。

**persist_volumes_arcs**

`volume_arc_planning_node` 的持久化函数：

```python
def persist_volumes_arcs(output: dict, project_id: int, db: Session):
    volumes_data = output.get("volumes", [])
    arcs_data = output.get("arcs", [])

    # 清除旧数据（CASCADE 自动删 arcs，SET NULL 自动清 chapter_outlines.arc_id）
    db.query(Volume).filter(Volume.project_id == project_id).delete()

    volume_id_map = {}  # 临时 volume_number → DB id 映射
    for v_data in volumes_data:
        volume = Volume(
            project_id=project_id,
            volume_number=v_data.get("volume_number", 1),
            title=v_data.get("title", ""),
            summary=v_data.get("summary"),
        )
        db.add(volume)
        db.flush()
        volume_id_map[v_data.get("volume_number", 1)] = volume.id

    for a_data in arcs_data:
        vol_num = a_data.get("volume_number", 1)  # arcs state 中包含 volume_number
        arc = Arc(
            volume_id=volume_id_map.get(vol_num),
            arc_number=a_data.get("arc_number", 1),
            title=a_data.get("title", ""),
            summary=a_data.get("summary"),
            chapter_count=a_data.get("chapter_count", 10),
        )
        db.add(arc)
```

**persist_chapter_summary**

`chapter_summary_node` 的持久化函数，从 `chapter_summaries` 字段读取：

```python
def persist_chapter_summary(output: dict, project_id: int, db: Session):
    chapter_summaries = output.get("chapter_summaries", [])
    for summary_data in chapter_summaries:
        summary = summary_data.get("summary")
        if not summary:
            continue
        chapter_num = summary_data.get("chapter_number")
        if not chapter_num:
            continue
        chapter_outline = db.query(ChapterOutline).filter(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_num,
        ).first()
        if chapter_outline and chapter_outline.chapter:
            chapter_outline.chapter.summary = summary
```

**persist_chapter_outlines 变更**

现有 `persist_chapter_outlines` 需在创建 ChapterOutline 时写入 `arc_id`。长篇时 arc_id 通过 volume_number + arc_number 从 DB 查询获得：

```python
for co_data in chapter_outlines:
    arc_id = None
    vol_num = co_data.get("volume_number")
    arc_num = co_data.get("arc_number")
    if vol_num and arc_num:
        # 从 DB 查询已持久化的 Arc 记录获取 arc_id
        arc_record = db.query(Arc).join(Volume).filter(
            Volume.project_id == project_id,
            Volume.volume_number == vol_num,
            Arc.arc_number == arc_num,
        ).first()
        if arc_record:
            arc_id = arc_record.id

    chapter_outline = ChapterOutline(
        project_id=project_id,
        chapter_number=co_data.get("chapter_number", 1),
        arc_id=arc_id,  # 从 DB 查询获得，短/中篇为 None
        # ... 其余字段不变
    )
```

**persist_chapter_content 无变更**

摘要写入走独立的 `chapter_summaries` 字段和 `persist_chapter_summary` 函数，`persist_chapter_content` 无需处理 summary，保持原有逻辑。

**NODE_PERSIST_MAP 注册**

```python
NODE_PERSIST_MAP = {
    # ... 现有映射
    "volume_arc_planning_node": persist_volumes_arcs,
    "chapter_summary_node": persist_chapter_summary,
}
```

### 4.8 弧/卷确认的 confirm 端点处理

`confirm_workflow` 端点新增 `volume_arc` confirmation_type 处理：

**WorkflowConfirmRequest 新增字段：**

```python
class WorkflowConfirmRequest(BaseModel):
    # ... 现有字段
    volumes: Optional[list] = None   # 用户修改后的卷数据
    arcs: Optional[list] = None      # 用户修改后的弧数据
```

**confirm 逻辑：**

```python
if confirmation_type == "volume_arc":
    volumes_data = request.volumes if request and request.volumes else checkpoint_state.get("volumes", [])
    arcs_data = request.arcs if request and request.arcs else checkpoint_state.get("arcs", [])

    # 更新 checkpoint_state 中的弧/卷数据（用户可能编辑了名称/概要）
    checkpoint_state["volumes"] = volumes_data
    checkpoint_state["arcs"] = arcs_data

    # 持久化到 DB
    persist_volumes_arcs({"volumes": volumes_data, "arcs": arcs_data}, project_id, db)

    # 确认通过，同步更新 chapter_count
    total_chapters = sum(a.get("chapter_count", 0) for a in arcs_data)
    checkpoint_state["chapter_count"] = total_chapters
    outline = db.query(Outline).filter(Outline.project_id == project_id).first()
    if outline:
        outline.chapter_count_suggested = total_chapters

    # 关键：从 DB 重新查询带 id 的 volumes/arcs 写回 checkpoint_state
    # persist_volumes_arcs 执行后 DB 已有真实 id，但 checkpoint_state 中仍是 LLM 输出的原始数据（无 id）
    # 后续节点（chapter_outlines_node）需要用 DB id 分配 arc_id
    db_volumes = db.query(Volume).filter_by(project_id=project_id).order_by(Volume.volume_number).all()
    volume_id_to_num = {v.id: v.volume_number for v in db_volumes}
    db_arcs = db.query(Arc).filter_by(volume_id__in=[v.id for v in db_volumes]).order_by(Arc.volume_id, Arc.arc_number).all()
    checkpoint_state["volumes"] = [
        {"id": v.id, "volume_number": v.volume_number, "title": v.title, "summary": v.summary}
        for v in db_volumes
    ]
    checkpoint_state["arcs"] = [
        {
            "id": a.id,
            "volume_id": a.volume_id,
            "volume_number": volume_id_to_num.get(a.volume_id, 1),
            "arc_number": a.arc_number,
            "title": a.title,
            "summary": a.summary,
            "chapter_count": a.chapter_count,
        }
        for a in db_arcs
    ]
```

### 4.9 replan 清理

大纲重新规划时清除弧/卷数据：

1. 删除 DB 中项目的 volumes（CASCADE 自动删 arcs，SET NULL 自动清 chapter_outlines.arc_id）
2. 清除 state 中的 volumes、arcs 字段为空列表
3. 重置 chapter_count（弧规划重新计算）

## 五、上下文策略

### 5.1 SummaryContentStrategy 实现

长篇专用。上下文构建逻辑：

```
前面弧的弧概要 + 当前弧内已写章节的摘要 + 近3章全文
```

具体实现：

```python
class SummaryContentStrategy(ContextStrategy):
    """摘要策略：前面弧概要 + 当前弧章节摘要 + 近N章全文"""

    def __init__(self, recent_count: int = 3):
        self.recent_count = max(1, min(recent_count, 10))

    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        if not written_chapters:
            return "（这是第一章，没有前文）"

        parts = []

        # 1. 前面弧：只取弧概要（非章节摘要）
        if arcs:
            current_arc = self._find_arc_for_chapter(arcs, current_chapter)
            if current_arc:
                # 全局排序键：(volume_number, arc_number)
                current_key = (current_arc.get("volume_number", 1), current_arc.get("arc_number", 0))
                sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
                previous_arcs = [a for a in sorted_arcs if (a.get("volume_number", 1), a.get("arc_number", 0)) < current_key]
                if previous_arcs:
                    arc_parts = []
                    for a in previous_arcs:
                        summary = f"《{a.get('title', '')}》"
                        if a.get("summary"):
                            summary += f"\n{a['summary']}"
                        arc_parts.append(summary)
                    parts.append("【前弧概要】\n" + "\n\n".join(arc_parts))

        # 2. 当前弧内已写章节：从 chapter_summaries 取摘要
        if arcs:
            current_arc = self._find_arc_for_chapter(arcs, current_chapter)
            if current_arc:
                current_arc_chapters = [
                    ch for ch in written_chapters
                    if ch.get("chapter_number", 0) < current_chapter
                    and self._is_in_arc(ch, current_arc, arcs, chapter_outlines)
                    and current_chapter - ch.get("chapter_number", 0) > self.recent_count
                ]
                if current_arc_chapters:
                    # 构建 chapter_number → summary 映射
                    summary_map = {}
                    if chapter_summaries:
                        summary_map = {s.get("chapter_number"): s.get("summary") for s in chapter_summaries if s.get("summary")}

                    summary_parts = []
                    for ch in sorted(current_arc_chapters, key=lambda x: x.get("chapter_number", 0)):
                        ch_num = ch.get("chapter_number", 0)
                        text = f"第{ch_num}章"
                        ch_summary = summary_map.get(ch_num)
                        if ch_summary:
                            text += f"\n{ch_summary}"
                        else:
                            # 回退：summary 未生成时从 chapter_outlines 取 plot
                            outline = self._find_outline(ch, chapter_outlines)
                            if outline and outline.get("plot"):
                                text += f"\n（大纲）{outline['plot'][:200]}"
                        summary_parts.append(text)
                    parts.append("【当前弧摘要】\n" + "\n\n".join(summary_parts))

        # 3. 近N章：取 content 全文
        recent = [
            ch for ch in written_chapters
            if ch.get("chapter_number", 0) < current_chapter
            and current_chapter - ch.get("chapter_number", 0) <= self.recent_count
        ]
        if recent:
            recent_parts = []
            for ch in sorted(recent, key=lambda x: x.get("chapter_number", 0)):
                title = ch.get("title", "")
                content = ch.get("content", "")
                recent_parts.append(f"第{ch.get('chapter_number', 0)}章《{title}》\n{content}")
            parts.append("【近期全文】\n" + "\n\n---\n\n".join(recent_parts))

        return "\n\n---\n\n".join(parts) if parts else "（这是第一章，没有前文）"

    def _find_arc_for_chapter(self, arcs: list[dict], chapter_number: int) -> dict | None:
        """根据章节号找到所属弧（通过累积 chapter_count 推算）

        arcs 按 (volume_number, arc_number) 全局排序，确保跨卷顺序正确。
        arc_number 是卷内递增，不能单独用于全局排序。
        """
        sorted_arcs = sorted(arcs, key=lambda a: (a.get("volume_number", 1), a.get("arc_number", 0)))
        cumulative = 0
        for arc in sorted_arcs:
            cumulative += arc.get("chapter_count", 0)
            if chapter_number <= cumulative:
                return arc
        return sorted_arcs[-1] if sorted_arcs else None

    def _is_in_arc(self, chapter: dict, arc: dict, arcs: list[dict], chapter_outlines: list[dict] | None = None) -> bool:
        """判断章节是否属于指定弧

        优先通过 chapter_outlines.arc_id 精确匹配。
        回退时用 _find_arc_for_chapter 找到章节实际所属的弧，比较是否等于目标弧。
        """
        # 精确匹配
        if chapter_outlines:
            for co in chapter_outlines:
                if co.get("chapter_number") == chapter.get("chapter_number") and co.get("arc_id") == arc.get("id"):
                    return True
        # 回退：找到章节实际所属的弧，比较是否为目标弧
        actual_arc = self._find_arc_for_chapter(arcs, chapter.get("chapter_number", 0))
        return actual_arc is not None and actual_arc.get("id") == arc.get("id")

    def _find_outline(self, chapter: dict, chapter_outlines: list[dict] | None) -> dict | None:
        if not chapter_outlines:
            return None
        for co in chapter_outlines:
            if co.get("chapter_number") == chapter.get("chapter_number"):
                return co
        return None
```

### 5.2 上下文 token 估算

长篇写第50章（弧3第5章，每弧15-20章）时：

| 部分 | 内容 | 估算 token |
|------|------|------------|
| 弧1概要 | ~500字 | ~700 |
| 弧2概要 | ~500字 | ~700 |
| 弧3已写摘要 | 4章×200字 | ~1.1k |
| 近3章全文 | 3章×3000字 | ~12k |
| **合计** | | **~14.5k** |

300章小说最后一章也在 ~15k token 内可控，不随章节增长膨胀。

### 5.3 回退机制

- summary 为空时（摘要未生成），从 chapter_outlines 取 plot[:200] 作为降级概要
- arcs 为空时（数据异常），回退到 hybrid 策略行为

### 5.4 get_context_strategy 变更

SummaryContentStrategy 已在 `_STRATEGY_MAP` 中注册。用户选择 `summary` 策略或 `novel_length == "long"` 时使用。

`build_previous_context` 调用处需传入 arcs 和 chapter_summaries 参数。基类签名显式加这两个参数，所有子类统一签名：

```python
# 基类
class ContextStrategy(ABC):
    @abstractmethod
    def build_previous_context(
        self,
        written_chapters: list[dict],
        current_chapter: int,
        chapter_outlines: list[dict] | None = None,
        arcs: list[dict] | None = None,
        chapter_summaries: list[dict] | None = None,
    ) -> str:
        pass

# 调用处（chapter_generation.py）
previous_context = strategy.build_previous_context(
    written_chapters, chapter_number,
    chapter_outlines=state.get("chapter_outlines", []),
    arcs=state.get("arcs", []),
    chapter_summaries=state.get("chapter_summaries", []),
)
```

FulltextContentStrategy 和 HybridContentStrategy 的 `build_previous_context` 签名同步加 `arcs` 和 `chapter_summaries` 参数但忽略（`_arcs`、`_chapter_summaries` 命名表示不使用），保持接口一致。

## 六、前端变更

### 6.1 灵感表单（InspirationPanel）

在目标字数附近新增"篇幅类型"下拉框：

| 选项 | 联动行为 |
|------|---------|
| 短篇 | 上下文策略→fulltext，目标字数建议<5万 |
| 中篇 | 上下文策略→hybrid，目标字数建议5-20万 |
| 长篇 | 上下文策略→summary，目标字数建议>20万 |

选择后联动更新上下文策略推荐和目标字数建议值，用户仍可手动调整。

传到后端 collected_info 新增 `novelLength: "short" | "medium" | "long"`。

### 6.2 章节大纲面板（ChapterOutlinePanel）

**短/中篇**：不变，平铺列表。

**长篇**：三级折叠树：

```
▼ 卷一：风云初起
  ▼ 弧1：初入江湖（15章）
    第1章 山村少年  📝
    第2章 拜师学艺  ✅
    ...
  ▶ 弧2：门派试炼（20章）
▶ 卷二：江湖恩怨
```

- 卷/弧行：显示名称+概要（点击可编辑，复用 inline edit 模式）
- 章节行：复用现有卡片，新增"摘要"字段
- 弧/卷确认步骤：工作流等待确认时，面板展示弧/卷结构供用户审阅和编辑

### 6.3 写后摘要交互

- 章节写完后，面板中该章的"摘要"字段自动填充
- 用户可点击编辑
- 编辑后自动保存到 DB（防抖，复用现有自动保存模式）

### 6.4 类型定义新增

```typescript
// types/index.ts
interface Volume {
  id: number
  volumeNumber: number
  title: string
  summary: string | null
}

interface Arc {
  id: number
  volumeId: number
  volumeNumber: number  // 用于前端全局排序
  arcNumber: number
  title: string
  summary: string | null
  chapterCount: number
}
```

## 七、API 变更

### 7.1 新增端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/volumes` | 获取卷列表（含弧） |
| PUT | `/api/projects/{id}/volumes/{vid}` | 编辑卷名/概要 |
| PUT | `/api/projects/{id}/arcs/{aid}` | 编辑弧名/概要 |
| PUT | `/api/projects/{id}/chapters/{cid}/summary` | 编辑章节摘要 |

### 7.2 修改端点

| 端点 | 变更 |
|------|------|
| `POST /api/projects/{id}/workflow/run` | collected_info 新增 novelLength 字段，写入 state.novel_length |
| `POST /api/projects/{id}/workflow/confirm` | confirmation_type 新增 "volume_arc"，确认时更新弧/卷编辑数据 |
| `GET /api/projects/{id}/chapters` | 返回数据新增 summary、arc_id 字段 |
| `GET /api/projects/{id}/chapters/outlines` | 返回数据新增 arc_id 字段 |

## 八、SSE 事件

弧/卷规划节点和摘要节点复用现有 node_start/node_done 事件，无需新事件类型。

弧/卷确认步骤复用现有 `waiting` 事件，confirmation_type = "volume_arc"。

## 九、Prompt 模板

### 9.1 弧/卷规划 Prompt

新增 `volume_arc_generation` prompt 模板，输入大纲数据，输出结构化的卷/弧划分：

```
输入：大纲标题、概述、情节节点、世界观、目标字数、总章节数
输出：
  卷一《xxx》
    弧1《xxx》：N章，概要...
    弧2《xxx》：N章，概要...
  卷二《xxx》
    弧3《xxx》：N章，概要...
```

### 9.2 写后摘要 Prompt

新增 `chapter_summary_generation` prompt 模板，输入章节内容，输出200字摘要：

```
输入：章节正文（全文）
输出：200字以内的章节内容摘要，包含关键情节、角色变化、伏笔线索
```

## 十、影响范围

| 模块 | 文件 | 改动类型 |
|------|------|---------|
| DB 迁移 | 新增 `20260516_add_volumes_arcs.py` | 新增 |
| 模型 | 新增 `volume.py`、`arc.py`，改 `outline.py`、`chapter.py` | 新增+修改 |
| Schema | 新增 `volume.py`、`arc.py`，改 `chapter.py` | 新增+修改 |
| State | `state.py` | 修改（字段+reducer） |
| 工作流图 | `graph.py` | 修改（2新节点+路由） |
| 节点 | 新增 `volume_arc_planning.py`、`chapter_summary.py` | 新增 |
| 上下文策略 | `context_strategy.py` | 修改（SummaryContentStrategy） |
| API | 新增 `volumes.py`、`arcs.py`，改 `chapters.py`、`workflow.py` | 新增+修改 |
| 工具 | `workflow_persistence.py`、`workflow.py`（build_initial_state） | 修改 |
| Prompt | `prompts.py` | 修改（2新模板） |
| 前端 | `InspirationPanel.tsx` | 修改（篇幅类型选项） |
| 前端 | `ChapterOutlinePanel.tsx` | 修改（三级折叠树+摘要字段） |
| 前端 | `api.ts` | 修改（新增 volumes/arcs API） |
| 前端 | `types/index.ts` | 修改（Volume/Arc 类型） |
| 测试 | 新增 `test_volume_arc.py`、`test_chapter_summary.py`，改 `test_context_strategy.py` | 新增+修改 |

## 十一、兼容性保证

1. **短/中篇零影响**：所有新逻辑通过 `novel_length == "long"` 门控，短/中篇不触发新节点、不加载弧/卷、不生成摘要
2. **数据向后兼容**：volumes/arcs 表为新增，chapter_outlines.arc_id 和 chapters.summary 为 nullable，旧数据不受影响
3. **工作流图兼容**：路由函数增加条件判断，短/中篇走原路径
4. **前端兼容**：ChapterOutlinePanel 根据是否有弧数据决定展示方式（有弧→树形，无弧→平铺）
5. **reducer 向后兼容**：合并逻辑对现有数据格式完全兼容，新字段 summary 不存在时 old 行为不变
