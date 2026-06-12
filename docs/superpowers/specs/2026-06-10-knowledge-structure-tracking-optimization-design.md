# 知识库/结构/追踪三标签页整合与 CRUD 补全设计

## 背景

当前三个标签页共 15 个子页面，存在三类问题：

1. **数据重复**：伏笔（知识库+追踪）、时间线（知识库+追踪）、节奏（结构+追踪）各出现两次
2. **CRUD 缺失**：大纲/风格约束/角色/伏笔/情节块/支线等子页面为纯只读，无法人工修正 AI 生成结果
3. **后端 API 缺口**：情节块缺 PUT/DELETE、支线缺 POST/PUT/DELETE、伏笔缺 PUT

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 优化策略 | 去重+整合优先，再补 CRUD | 信息架构决定功能该建在哪里，先归位再补功能不返工 |
| 角色 CRUD | 复用 CharacterFormDialog | 组件已验证，角色字段多不适合内联编辑 |
| 伏笔状态流转 | 操作按钮（单向） | 防止跳步，活跃→标记待回收→确认已回收 |
| 节奏对比展示 | 叠加曲线 | 一眼看到偏差，不需要上下对照 |
| 结构预期节奏 | 保留横条+轻量折线预览 | 保留整体感知，折线不喧宾夺主，详细对比跳转追踪 |
| 已确认大纲 | 不允许编辑 | 大纲确认后进入结构阶段，修改会导致情节块/章节规划不一致 |

## 整合方案

### 标签页职责

- **知识库** = 写作前设定参考（静态知识）
- **结构** = 叙事架构规划（规划产出）
- **追踪** = 写作过程监控（运行时数据）

### 数据归位

| 数据 | 原位置 | 目标位置 | 动作 |
|------|--------|----------|------|
| 伏笔 | 知识库+追踪 | 追踪（唯一） | 删除知识库「伏笔地图」子页面，追踪伏笔追踪合并规划+状态展示 |
| 时间线 | 知识库+追踪 | 追踪（唯一） | 删除知识库「时间线」子页面，追踪时间线增强展示（因果链+ScoreBar） |
| 节奏 | 结构（预期+实际）+追踪（实际） | 结构（预期+轻量折线）+追踪（叠加对比） | 结构删实际柱状图，改为轻量折线预览+跳转链接；追踪升级为叠加曲线图 |

### 最终布局

**知识库（6 子页面）：** 故事种子 / 大纲 / 世界观 / 风格约束 / 角色 / 关系

**结构（4 子页面）：** 情节块 / 问题链 / 支线网络 / 预期节奏

**追踪（4 子页面）：** 伏笔追踪 / 时间线 / 风格偏差 / 节奏对比

---

## 知识库标签页 CRUD 详情

### 故事种子

无变动。已有读取 + 编辑保存。

### 大纲

- 新增编辑功能：summary（textarea）、plot_points（列表编辑器，可增删改条目）
- 编辑态：右上角「编辑」按钮进入，保存/取消退出
- **已确认大纲不可编辑**：如果大纲已 confirmed（显示"已确认"绿色标签），不显示编辑按钮。理由：大纲确认后进入结构阶段，情节块/章节规划均基于此大纲，随意修改会导致下游数据不一致
- 后端：复用已有 `PUT /api/projects/{id}/outline`（outline.py），该 API 已有 confirmed 检查返回 400
- **不新增 knowledge.py 的 outline PUT 端点**，避免两个入口修改同一数据
- 编辑保存后调用 `incrementKnowledgeVersion()` 刷新视图

### 世界观

- 扩展编辑：core_concept（已有）、tiered_settings 各层条目可增删、key_locations 可增删
- tiered_settings 编辑：三层（red/yellow/green）各自维护列表，每条可编辑/删除，底部「+ 添加」
- key_locations 编辑：标签式列表，可增删
- 后端：已有 `PUT /api/projects/{id}/world-setting`，WorldSettingUpdate schema 已包含 tiered_settings / key_locations 字段，无需新增

### 风格约束

- 接线已有 PUT API：style_anchor（textarea 编辑）、taboo_words（标签列表可增删）、forbidden_patterns（列表可增删）、abstract_rules（列表可增删）
- 编辑态：右上角「编辑」按钮进入，保存/取消退出
- 后端：已有 `PUT /api/projects/{id}/style-constraints`，无需新增
- **前端 StyleConstraintsView 需新增 onUpdate + projectId props**，当前未传入

### 角色

- 集成 CharacterFormDialog：卡片上加「编辑」按钮，点击弹出 CharacterFormDialog；顶部加「+ 新增角色」按钮；卡片加「删除」按钮（confirm 后调用 `characterApi.delete`）
- **CharacterFormDialog 需改造支持编辑模式**：新增可选 `character?: Character` prop，传入时表单 useState 初始值从 character 填充、标题"编辑角色"、按钮"保存"、onSubmit 调用 `characterApi.update`；不传时保持创建模式
- CharactersListView 组件需扩展 props：增加 `projectId`、`onUpdate` 回调
- 后端：已有完整 CRUD API，无需新增
- **角色删除级联**：Relation 表的 `character_a_id` / `character_b_id` 是 `ForeignKey("characters.id", ondelete="CASCADE")`，Character 的 `relations_a/b` relationship 也有 `cascade="all, delete-orphan"`。删除角色时，关联关系和演变规划/记录会自动级联删除，无需手动处理。前端只需在删除确认提示中说明"该角色的所有关联关系将一并删除"

### 关系

- 已有新增（RelationFormDialog）和删除，补「编辑」按钮
- **RelationFormDialog 需改造支持编辑模式**：新增可选 `relation?: RelationWithCharacters` prop，传入时表单 useState 初始值从 relation 填充、标题"编辑关系"、按钮"保存"、onSubmit 调用 `relationApi.update`；不传时保持创建模式
- RelationCard 组件加「编辑」按钮
- 后端：已有 `PUT /api/projects/{id}/relations/{rid}`，无需新增

---

## 结构标签页 CRUD 详情

### 情节块

- 新增编辑：点击情节块卡片进入 inline 编辑态，字段包括 title / expected_mood / questions_to_answer / questions_to_raise / must_happen
- questions 列表用可增删标签式编辑器
- 新增删除按钮（confirm 后调用 API）
- **删除情节块的级联影响**：PlotQuestion 表的 `plot_block_id` 有 `ForeignKey("plot_blocks.id", ondelete="SET NULL")`，删除情节块后关联问题的 `plot_block_id` 会被设为 NULL。前端删除确认提示中说明"关联的问题链条目将失去情节块关联"
- 后端：需补 `PUT /api/projects/{id}/plot-blocks/{bid}` 和 `DELETE /api/projects/{id}/plot-blocks/{bid}`
- KnowledgeBaseService 需补 `delete_plot_block` 方法

### 问题链

无变动。从情节块数据派生，只读展示。

### 支线网络

- 新增 CRUD：顶部「+ 新增支线」按钮，弹出表单填写 name / characters / current_status / raised_in_chapter / planned_intersection_chapter / expected_resolution_chapter
- current_status 下拉选项：暗示(hint) / 发展中(developing) / 待交汇(pending_intersection) / 已解决(resolved)
- 卡片上加「编辑」按钮（inline 编辑态）和「删除」按钮（confirm）
- 后端：需补 `POST /api/projects/{id}/subplots`、`PUT /api/projects/{id}/subplots/{sid}`、`DELETE /api/projects/{id}/subplots/{sid}`
- KnowledgeBaseService 已有 `create_subplot` / `update_subplot`，需补 `delete_subplot` 方法

### 预期节奏

- 保留预期节奏横条展示（情节块的 expected_mood）
- 删除实际节奏柱状图（RhythmChart 组件）
- 新增轻量实际张力折线预览（SVG 折线，无柱状图/数据点标注）
- 底部加「查看详细对比 →」链接，点击切换到追踪标签页的节奏对比子页面
- expected_mood 编辑通过情节块编辑间接实现

---

## 追踪标签页详情

### 伏笔追踪

- 从知识库迁入，合并规划+状态展示
- 按状态分组：待回收（顶部）→ 活跃 → 已回收（底部）
- 状态流转按钮：
  - 活跃 → 显示「⏱ 标记待回收」
  - 待回收 → 显示「✓ 确认已回收」+ 逾期预警（预计回收章 < 当前已写章数时标红 ⚠ 已逾期）
  - 已回收 → 无流转按钮，内容划线淡化
- 所有状态都有「编辑」按钮（修改伏笔内容/预计回收章节等）
- **编辑表单不包含 status 字段**——状态只能通过流转按钮修改，防止绕过单向校验
- **确认回收时自动填入 resolved_chapter**：从 `projectStore.currentChapterNum` 获取当前章节号，作为 `resolved_chapter` 传给后端
- 顶部「+ 新增伏笔」按钮，弹出表单（content / level / planted_chapter / expected_resolve_chapter / related_characters，status 默认 active）
- **新增伏笔的 level 合法值**：hint（暗示）/ strengthened（强化）/ revealed（揭示），前端用下拉选择
- 后端：需补 `PUT /api/projects/{id}/foreshadowings/{fid}`
- KnowledgeBaseService 已有 `update_foreshadowing`，API 层只需新增路由
- **伏笔状态校验**：PUT 端点需校验状态转换合法性（active→pending_reclaim→reclaimed 单向），拒绝跳步和非法值。定义常量：

```python
FORESHADOWING_STATUS_TRANSITIONS = {
    "active": {"pending_reclaim"},
    "pending_reclaim": {"reclaimed"},
    "reclaimed": set(),  # 终态，不可流转
}
FORESHADOWING_VALID_STATUSES = {"active", "pending_reclaim", "reclaimed"}
```

- **不提供伏笔删除 API**：伏笔是写作过程追踪数据，应通过状态流转到"已回收"终结，而非删除

### 时间线

- 从知识库迁入，增强展示
- 保留因果链展示 + 加入 ScoreBar（节奏/张力/情绪评分条，从知识库版本迁移）
- 只读（自动生成数据），加章节范围筛选（chapterStart/chapterEnd 两个 number input）
- 后端：已有 `GET /api/projects/{id}/timeline?chapter_start=&chapter_end=`，无需新增

### 风格偏差

- 原「风格统计」升级
- 保留表格（段落数/平均段长/对话占比/平均句长）+ 对话占比折线
- 新增偏差预警列：当某章统计值偏离正常范围时高亮
- 预警逻辑：
  - 优先从 style_constraints 的 abstract_rules / forbidden_patterns 解析阈值（如"对话占比不超过 40%"→ 0.4）
  - 无明确阈值时，用全部章节均值 ± 1σ 作为正常范围
  - 偏差超出范围时，单元格背景标红，hover 显示偏差值
- 只读（计算值），无需编辑
- **性能考量**：偏差计算在前端执行（数据量小，每章一行），不增加后端负担

### 节奏对比

- 合并结构实际节奏 + 追踪节奏分析
- 叠加曲线图：预期曲线（虚线，从情节块 expected_mood 插值）+ 实际曲线（实线，从时间线张力数据）
- 偏差区域用半透明填充标注
- 偏差超出阈值的章节数据点用橙色高亮
- 偏差预警卡片：列出偏差最大的章节，显示预期值 vs 实际值 + 偏差百分比 + 建议
- 情绪标签分布：按章显示 emotion_tag，颜色按 emotion_score 梯度
- 只读（计算值），无需编辑
- **预期曲线插值**：情节块定义章节范围（chapter_start~chapter_end）和 expected_mood，将 mood 映射为数值（日常=1, 舒缓=1.5, 悬念=2.5, 转折=3.5, 紧张=4, 高潮=5, 悲伤=3），在块内线性插值到每章。**未覆盖的章节**（情节块之间可能有间隙或最前/最后）用最近块的值延伸

---

## 后端 API 变更汇总

| 端点 | 方法 | 说明 | KnowledgeBaseService |
|------|------|------|---------------------|
| `/api/projects/{id}/plot-blocks/{bid}` | PUT | 编辑情节块 | 已有 `update_plot_block` |
| `/api/projects/{id}/plot-blocks/{bid}` | DELETE | 删除情节块 | **需补** `delete_plot_block` |
| `/api/projects/{id}/subplots` | POST | 新增支线 | 已有 `create_subplot` |
| `/api/projects/{id}/subplots/{sid}` | PUT | 编辑支线 | 已有 `update_subplot` |
| `/api/projects/{id}/subplots/{sid}` | DELETE | 删除支线 | **需补** `delete_subplot` |
| `/api/projects/{id}/foreshadowings/{fid}` | PUT | 编辑伏笔（内容+状态流转） | 已有 `update_foreshadowing` |

大纲编辑复用已有 `PUT /api/projects/{id}/outline`（outline.py），不新增端点。

已有无需变更的 API：
- `PUT /api/projects/{id}/world-setting`（世界观）
- `PUT /api/projects/{id}/style-constraints`（风格约束）
- 角色/关系 CRUD（characters.py 已有完整 API）
- `GET /api/projects/{id}/timeline?chapter_start=&chapter_end=`（时间线筛选）

---

## 并发安全

knowledge.py 的所有写入端点（PUT/DELETE）需检查项目 busy 状态，防止用户在 Agent/工作流运行时修改数据导致数据竞争。

```python
# 在每个写入端点中：
project = get_project_for_user(project_id, current_user.id, db)
if project.is_busy:
    holder = project.busy_by or "未知"
    raise HTTPException(status_code=409, detail=f"项目正在被{holder}使用，请稍后再试")
```

**注意**：只检查 `is_busy` 状态，不调用 `_acquire_busy_lock`。busy lock 的 acquire/release 由 Agent/工作流负责，知识库编辑只需拒绝并发写入。

已有 GET 端点不加 busy 检查（只读安全）。

> **已知遗留**：chapters.py 和 outline.py 的写入端点也没有 busy 检查，这是既有技术债。本次变更不为旧端点补 busy 检查（范围外），但新增端点必须加。

---

## Pydantic Schema 变更

`backend/app/schemas/knowledge.py` 需新增：

```python
class PlotBlockUpdate(BaseModel):
    title: Optional[str] = None
    questions_to_answer: Optional[list] = None
    questions_to_raise: Optional[list] = None
    must_happen: Optional[list] = None
    expected_mood: Optional[str] = None
    chapter_start: Optional[int] = None
    chapter_end: Optional[int] = None
    completion_summary: Optional[str] = None

class SubplotCreate(BaseModel):
    name: str
    characters: list = []
    current_status: Optional[str] = "hint"
    raised_in_chapter: Optional[int] = None
    planned_intersection_chapter: Optional[int] = None
    expected_resolution_chapter: Optional[int] = None

class SubplotUpdate(BaseModel):
    name: Optional[str] = None
    characters: Optional[list] = None
    current_status: Optional[str] = None
    raised_in_chapter: Optional[int] = None
    planned_intersection_chapter: Optional[int] = None
    expected_resolution_chapter: Optional[int] = None

class ForeshadowingUpdate(BaseModel):
    content: Optional[str] = None
    level: Optional[str] = None
    status: Optional[str] = None  # 状态流转：仅允许 active→pending_reclaim→reclaimed
    planted_chapter: Optional[int] = None
    expected_resolve_chapter: Optional[int] = None
    resolved_chapter: Optional[int] = None
    related_characters: Optional[list] = None
```

**SubplotCreate/SubplotUpdate 的 current_status 校验**：合法值为 `hint` / `developing` / `pending_intersection` / `resolved`，API 层需校验。

**ForeshadowingUpdate 的 level 校验**：合法值为 `hint` / `strengthened` / `revealed`，API 层需校验。

**ForeshadowingUpdate 的 status 校验**：除了流转校验外，`appearance_count` 字段不在 Update schema 中——它由系统自动管理，不允许手动修改。

---

## KnowledgeBaseService 新增方法

遵循同文件现有 CRUD 模式（`_get_db` / `_close_db_write`），不引入新模式以避免混入不相关重构：

```python
def delete_plot_block(self, block_id: int) -> None:
    """删除情节块

    注意：关联的 PlotQuestion.plot_block_id 会被 SET NULL（数据库 ondelete）
    """
    db = self._get_db()
    committed = False
    try:
        block = db.query(PlotBlock).filter(
            PlotBlock.id == block_id,
            PlotBlock.project_id == self.project_id,
        ).first()
        if not block:
            raise ValueError(f"PlotBlock {block_id} not found")
        db.delete(block)
        db.commit()
        committed = True
    finally:
        self._close_db_write(db, committed)

def delete_subplot(self, subplot_id: int) -> None:
    """删除支线"""
    db = self._get_db()
    committed = False
    try:
        s = db.query(Subplot).filter(
            Subplot.id == subplot_id,
            Subplot.project_id == self.project_id,
        ).first()
        if not s:
            raise ValueError(f"Subplot {subplot_id} not found")
        db.delete(s)
        db.commit()
        committed = True
    finally:
        self._close_db_write(db, committed)
```

---

## 前端组件改造

### CharacterFormDialog 编辑模式

当前只有创建模式（`onSubmit: (data: CharacterCreate) => void`）。

改造：
- 新增可选 `character?: Character` prop
- 传入时：表单 useState 初始值从 character 填充，标题"编辑角色"，按钮"保存"，onSubmit 调用 `characterApi.update`
- 不传时：保持创建模式不变
- **类型处理**：`onSubmit` 签名改为联合类型 `onSubmit: (data: CharacterCreate | CharacterUpdate) => void`，由调用方决定传哪种数据

### RelationFormDialog 编辑模式

当前只有创建模式（`onSubmit: (data: RelationCreate) => void`）。

改造：
- 新增可选 `relation?: RelationWithCharacters` prop
- 传入时：表单 useState 初始值从 relation 填充，标题"编辑关系"，按钮"保存"，onSubmit 调用 `relationApi.update`
- 不传时：保持创建模式不变
- 同上类型处理

---

## 前端错误处理

新增 CRUD 操作的错误处理统一使用 `sonner` toast（项目已有依赖）：

- 保存成功：`toast.success('保存成功')`
- 保存失败：`toast.error('保存失败：' + err.message)`
- 删除成功：`toast.success('已删除')`
- 删除失败：`toast.error('删除失败：' + err.message)`
- 并发冲突（409）：`toast.error('项目正在被 Agent 使用，请稍后再试')`
- 大纲已确认（400）：`toast.error('大纲已确认，无法编辑')`

---

## 前端数据刷新

所有写入操作完成后，调用 `useWorkbenchStore.getState().incrementKnowledgeVersion()` 触发知识库和结构标签页的数据重新加载。

**TrackingTab 需新增 knowledgeVersion 订阅**：当前未订阅，导致在追踪标签页操作伏笔后切到其他标签页时数据不刷新。在 TrackingTab 的 useEffect 依赖中加入 knowledgeVersion。

---

## 前端类型安全

当前三个标签页组件中存在 14 处 `any` 类型。新增代码应使用具体类型，不继续积累 `any` 技术债。

新增 `frontend/src/types/knowledge.ts`：

```typescript
export interface PlotBlock {
  id: number
  project_id: number
  title: string
  questions_to_answer: string[]
  questions_to_raise: string[]
  must_happen: string[]
  expected_mood: string | null
  chapter_start: number | null
  chapter_end: number | null
  completion_summary: string | null
}

export interface Subplot {
  id: number
  project_id: number
  name: string
  characters: string[]
  current_status: string
  raised_in_chapter: number | null
  planned_intersection_chapter: number | null
  expected_resolution_chapter: number | null
}

export interface Foreshadowing {
  id: number
  project_id: number
  content: string
  level: string
  appearance_count: number
  status: string
  planted_chapter: number | null
  expected_resolve_chapter: number | null
  resolved_chapter: number | null
  related_characters: string[]
}

export interface TimelineEntry {
  id: number
  project_id: number
  chapter_number: number
  summary: string | null
  causal_chain: string | null
  rhythm_score: number
  tension_score: number
  emotion_score: number
  emotion_tag: string | null
}

export interface StyleSnapshot {
  id: number
  project_id: number
  chapter_number: number
  paragraph_count: number
  avg_paragraph_length: number
  dialogue_ratio: number
  avg_sentence_length: number
}
```

---

## 前端文件变更预估

### 新增文件

| 文件 | 说明 |
|------|------|
| `frontend/src/types/knowledge.ts` | 知识库相关类型定义 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `knowledge/KnowledgeTab.tsx` | 删除伏笔地图/时间线子页面及 SECTIONS 条目；大纲加编辑（未确认时显示编辑按钮）；风格约束加编辑（传 onUpdate+projectId）；角色集成 CharacterFormDialog；用具体类型替代 any |
| `knowledge/WorldSettingView.tsx` | 扩展编辑 tiered_settings + key_locations |
| `knowledge/CharactersListView.tsx` | 增加 projectId/onUpdate props，集成新增/编辑/删除 |
| `knowledge/RelationsView.tsx` | 补编辑按钮，复用 RelationFormDialog 编辑模式 |
| `character/CharacterFormDialog.tsx` | 新增 character? prop 支持编辑模式 |
| `character/RelationFormDialog.tsx` | 新增 relation? prop 支持编辑模式 |
| `structure/StructureTab.tsx` | 情节块加 inline 编辑+删除（提示级联影响）；支线加 CRUD；预期节奏改用轻量折线+跳转链接；用具体类型替代 any |
| `tracking/TrackingTab.tsx` | 伏笔追踪加状态流转+编辑+新增；时间线增强+筛选；风格统计升级为偏差预警；节奏升级为叠加对比；新增 knowledgeVersion 订阅；用具体类型替代 any |
| `lib/api.ts` | 新增 plot-blocks PUT/DELETE、subplots POST/PUT/DELETE、foreshadowings PUT 的前端方法 |
| `lib/characterApi.ts` | 无变更（已有 update/delete） |

### 后端修改文件

| 文件 | 变更 |
|------|------|
| `api/knowledge.py` | 新增情节块 PUT/DELETE、支线 POST/PUT/DELETE、伏笔 PUT 端点；所有写入端点加 busy 检查；伏笔 PUT 加状态流转校验+level 合法值校验；支线 POST/PUT 加 current_status 合法值校验 |
| `agents/services/knowledge_base.py` | 新增 delete_plot_block、delete_subplot 方法 |
| `schemas/knowledge.py` | 新增 PlotBlockUpdate、SubplotCreate、SubplotUpdate、ForeshadowingUpdate schema |

---

## 不在范围内

- 写作标签页的变更
- Agent 侧边栏的变更
- 图表库引入（节奏对比/风格偏差继续使用 SVG，不引入第三方图表库）
- 伏笔的批量创建 API 变更（已有 batch 端点，不动）
- 演变规划/记录的变更（已有完整 CRUD）
- Alembic 迁移（无新表/新列，所有变更在已有 JSON 列内）
- 旧端点补 busy 检查（chapters.py、outline.py 等已有端点，范围外）
- KnowledgeBaseService 统一迁移到 session() 上下文管理器（范围外，不混入重构）
- 已确认大纲的取消确认功能（范围外，需单独设计）


---

## 第四轮审查修复记录（2026-06-10）

| 修复 | 文件 | 说明 |
|------|------|------|
| PlotBlock cascade 冲突 | `backend/app/models/plot_structure.py` | 移除 `cascade="all, delete-orphan"`，让数据库 `ondelete="SET NULL"` 生效。之前 ORM cascade 会抢先删除 PlotQuestion，与 SET NULL 语义矛盾 |
| N+1 查询性能 | `backend/app/api/knowledge.py` | `update_foreshadowing` 改用 `get_foreshadowing(id)` 单条查询替代 `get_foreshadowings()` 全量加载 |
| KnowledgeBaseService 补方法 | `backend/app/agents/services/knowledge_base.py` | 新增 `delete_plot_block`、`delete_subplot`、`get_foreshadowing` |
| Pydantic Schema 补类型 | `backend/app/schemas/knowledge.py` | 新增 `PlotBlockUpdate`、`SubplotCreate`、`SubplotUpdate`、`ForeshadowingUpdate` |
| knowledge.py busy 检查 | `backend/app/api/knowledge.py` | 所有写入端点（含已有的故事种子/世界观/风格约束/批量端点）加 `_check_busy` 检查 |
| characters.py busy 检查 | `backend/app/api/characters.py` | 角色/关系/演变规划的所有写入端点加 `_check_busy` 检查（共 11 个） |
| 伏笔状态流转校验 | `backend/app/api/knowledge.py` | PUT 端点校验 active→pending_reclaim→reclaimed 单向转换 + level 合法值 |
| 支线 status 校验 | `backend/app/api/knowledge.py` | POST/PUT 端点校验 current_status 合法值 |
| 前端 API CRUD 方法 | `frontend/src/lib/api.ts` | knowledgeApi 新增 `updatePlotBlock`、`deletePlotBlock`、`createSubplot`、`updateSubplot`、`deleteSubplot`、`updateForeshadowing` |
| 前端类型定义 | `frontend/src/types/knowledge.ts` | 新增 PlotBlock/Subplot/Foreshadowing/TimelineEntry/StyleSnapshot 等类型 |
| KnowledgeTab 去重 | `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx` | 移除伏笔地图/时间线子页面（归入追踪标签页） |
| OutlineView 编辑 | `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx` | 未确认大纲可编辑 summary + plot_points（PlotPoint[] 结构），已确认大纲不显示编辑按钮 |
| StyleConstraintsView 编辑 | `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx` | 补编辑模式：style_anchor/禁忌词/禁用句式/风格规则，标签列表可增删 |
| TrackingTab knowledgeVersion | `frontend/src/components/workbench/tracking/TrackingTab.tsx` | 新增 `knowledgeVersion` 订阅，修复切标签页后数据不刷新问题 |

### 仍需实现阶段完成的工作

- CharacterFormDialog 编辑模式（需加 `character?` prop）
- RelationFormDialog 编辑模式（需加 `relation?` prop）
- CharactersListView 增加 `projectId`/`onUpdate` + 新增/编辑/删除按钮
- RelationCard 增加编辑按钮
- StructureTab 情节块 inline 编辑+删除
- StructureTab 支线 CRUD（新增/编辑/删除）
- StructureTab 预期节奏改为轻量折线+跳转追踪
- TrackingTab 伏笔追踪状态流转按钮+编辑+新增
- TrackingTab 时间线增强（章节范围筛选+ScoreBar）
- TrackingTab 风格偏差升级（偏差预警）
- TrackingTab 节奏对比升级（叠加曲线图）
- 前端错误处理统一用 `sonner` toast
- 前端写入操作后调用 `incrementKnowledgeVersion()`
