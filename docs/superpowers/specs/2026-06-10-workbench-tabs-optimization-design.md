# 工作台知识库/结构/追踪标签页优化设计

> 日期：2026-06-10
> 范围：知识库、结构、追踪三个主标签页的整合去重 + CRUD 补全

## 1. 问题分析

### 1.1 数据重复

三个标签页存在 3 处数据重复展示：

| 数据 | 出现位置 A | 出现位置 B |
|------|-----------|-----------|
| 伏笔 | 知识库「伏笔地图」 | 追踪「伏笔追踪」 |
| 时间线 | 知识库「时间线」 | 追踪「时间线」 |
| 节奏 | 结构「节奏曲线」(含实际) | 追踪「节奏分析」 |

### 1.2 CRUD 缺失

15 个子页面中，仅「故事种子」具备完整 CRUD。其余子页面大多为只读展示，用户无法人工修正 AI 生成结果。

### 1.3 后端 API 缺口

| 资源 | 缺失 API |
|------|----------|
| 情节块 | `PUT /projects/{id}/plot-blocks/{bid}`, `DELETE /projects/{id}/plot-blocks/{bid}` |
| 支线 | `POST /projects/{id}/subplots`, `PUT /projects/{id}/subplots/{sid}`, `DELETE /projects/{id}/subplots/{sid}` |
| 伏笔 | `PUT /projects/{id}/foreshadowings/{fid}` |
| 大纲 | `PUT /projects/{id}/outline-summary` |

---

## 2. 标签页职责定义

| 标签页 | 职责 | 数据性质 |
|--------|------|---------|
| 知识库 | 写作前设定的参考资料 | 静态设定，孵化/结构阶段产出 |
| 结构 | 叙事架构规划 | 规划数据，结构阶段产出 |
| 追踪 | 写作过程监控 | 运行时数据，写作阶段自动更新 |

---

## 3. 整合方案

### 3.1 伏笔：知识库 → 追踪

- **删除** 知识库 `KnowledgeTab` 中的 `foreshadowing` 子页面（`SECTIONS` 数组移除该条目，`ForeshadowingView` 组件及 `renderContent` 对应 case 删除）
- **升级** 追踪 `ForeshadowingTrackView`：
  - 合并展示规划信息（伏笔内容、埋设章节、预计回收章节）+ 运行状态（活跃/待回收/已回收分组）
  - 新增状态流转按钮（单向：活跃 → 标记待回收 → 确认已回收）
  - 新增「编辑」按钮（修改伏笔内容/预计回收章节等）
  - 新增「+ 新增伏笔」按钮
  - 逾期预警：当 `expected_resolve_chapter` < 当前写作章节且状态非 `reclaimed` 时，显示 ⚠ 已逾期标签

### 3.2 时间线：知识库 → 追踪

- **删除** 知识库 `KnowledgeTab` 中的 `timeline` 子页面（`SECTIONS` 移除，`TimelineView`/`ScoreBar` 组件及 `renderContent` 对应 case 删除）
- **升级** 追踪 `TimelineTrackView`：
  - 吸收知识库版本的 ScoreBar 组件（节奏/张力/情绪评分条），在每个时间线条目中展示
  - 保留因果链展示
  - 新增章节范围筛选：`chapterStart` 和 `chapterEnd` 输入框，调用 `knowledgeApi.getTimeline(projectId)` 后前端过滤（后端 API 已支持 chapter_start/chapter_end 参数）

### 3.3 节奏：结构保留预期，追踪升级为对比

**结构「节奏曲线」→「预期节奏」：**

- 重命名 `StructureTab` 中 `rhythm` 子页面 label 为「预期节奏」
- 保留预期节奏横条（情节块 expected_mood）
- **删除** 实际节奏的 `RhythmChart` 柱状图组件
- **新增** 轻量实际张力折线预览：一条 SVG `<polyline>`，使用时间线 `tension_score` 数据，半透明样式，无数据点标注
- **新增** 「查看详细对比 →」链接，点击切换到追踪标签页的节奏对比子页面（通过 `useWorkbenchStore.setActiveTab('tracking')` 实现）

**追踪「节奏分析」→「节奏对比」：**

- 重命名 `TrackingTab` 中 `rhythm` 子页面 label 为「节奏对比」
- **替换** `RhythmTrackView` 为 `RhythmCompareView`：
  - 叠加曲线图：预期曲线（蓝色虚线，从情节块 expected_mood 插值生成）+ 实际曲线（红色实线，从时间线 tension_score 生成）
  - 偏差区域：预期与实际差值超过阈值（默认 1.0）的章节区间，用半透明橙色填充
  - 偏差预警卡片：列出偏差超过阈值的章节，标注偏差百分比和建议
  - 情绪标签分布：从时间线 emotion_tag 渲染彩色标签
  - 图例：预期（虚线）、实际（实线）、偏差区（填充色）

---

## 4. CRUD 补全方案

### 4.1 知识库

#### 大纲 `OutlineView`

- 新增编辑态：点击「编辑」按钮，summary 变为 textarea，plot_points 变为列表编辑器（每项一个 input + 删除按钮，底部新增按钮）
- 保存调用 `knowledgeApi.updateOutlineSummary(projectId, data)` → 后端需补 `PUT /projects/{id}/outline-summary`

#### 世界观 `WorldSettingView`

- 扩展编辑范围：除 core_concept 外，tiered_settings 的 red/yellow/green 三个层级各变为可增删列表，key_locations 变为可增删标签列表
- 保存调用已有的 `knowledgeApi.updateWorldSetting(projectId, data)`

#### 风格约束 `StyleConstraintsView`

- 接线已有 PUT API：新增 `onUpdate` prop 和「编辑」按钮
- 编辑态：style_anchor 变为 textarea，taboo_words / forbidden_patterns / abstract_rules 各变为可增删列表
- 保存调用已有的 `knowledgeApi.updateStyleConstraints(projectId, data)`

#### 角色 `CharactersListView`

- 集成已有 `CharacterFormDialog`：
  - 每个角色卡片加「编辑」按钮，点击弹出 `CharacterFormDialog`（传入角色数据）
  - 顶部加「+ 新增角色」按钮，弹出空白 `CharacterFormDialog`
  - 每个角色卡片加「删除」按钮，确认后调用 `characterApi.delete()`
- 新增 `projectId` 和 `onUpdate` props

#### 关系 `RelationsView`

- 已有新增/删除，补「编辑」按钮：点击弹出 `RelationFormDialog`，预填当前关系数据
- 后端已有 PUT API（`characters.py` 中 `update_relation`），前端 `relationApi` 需补 `update()` 方法

### 4.2 结构

#### 情节块 `PlotBlocksView`

- inline 编辑：点击情节块卡片，展开为编辑表单
  - 可编辑字段：title (input), expected_mood (select/input), questions_to_answer (列表), questions_to_raise (列表), must_happen (列表)
  - 底部「保存」「取消」按钮
- 删除：卡片右上角「删除」按钮，确认后调用后端 API
- 后端需补 `PUT /projects/{id}/plot-blocks/{bid}` 和 `DELETE /projects/{id}/plot-blocks/{bid}`
- 前端 `knowledgeApi` 需补 `updatePlotBlock()` 和 `deletePlotBlock()` 方法

#### 支线网络 `SubplotsView`

- 新增：「+ 新增支线」按钮，弹出表单：name (input), characters (标签输入), current_status (select: hint/developing/pending_intersection/resolved), raised_in_chapter / planned_intersection_chapter / expected_resolution_chapter (number input)
- 编辑：点击支线卡片展开编辑表单
- 删除：卡片右上角「删除」按钮
- 后端需补 `POST /projects/{id}/subplots`, `PUT /projects/{id}/subplots/{sid}`, `DELETE /projects/{id}/subplots/{sid}`
- 前端 `knowledgeApi` 需补 `createSubplot()`, `updateSubplot()`, `deleteSubplot()` 方法

### 4.3 追踪

#### 伏笔追踪 `ForeshadowingTrackView`

- 状态流转按钮：
  - `active` 状态 → 显示「⏱ 标记待回收」按钮，点击调用 `knowledgeApi.updateForeshadowing(id, {status: 'pending_reclaim'})`
  - `pending_reclaim` 状态 → 显示「✓ 确认已回收」按钮，点击调用 `knowledgeApi.updateForeshadowing(id, {status: 'reclaimed', resolved_chapter: currentChapter})`
  - `reclaimed` 状态 → 无流转按钮
- 编辑：所有状态都有「编辑」按钮，弹出表单修改 content / expected_resolve_chapter / related_characters
- 新增：顶部「+ 新增伏笔」按钮
- 后端需补 `PUT /projects/{id}/foreshadowings/{fid}`
- 前端 `knowledgeApi` 需补 `updateForeshadowing()` 和 `createForeshadowing()` 方法

#### 时间线 `TimelineTrackView`

- 只读（自动生成），不加 CRUD
- 新增章节范围筛选：两个 number input（起始章/结束章），调用 `knowledgeApi.getTimeline(projectId, start, end)`
- 增强：每个条目加入 ScoreBar（节奏/张力/情绪评分条，从知识库 `TimelineView` 迁移）

#### 风格偏差 `StyleTrackView`

- 只读（计算值），不加 CRUD
- 重命名子页面 label 为「风格偏差」
- 新增偏差预警列：对比 style_constraints 与 style_snapshots
  - 预警规则：无明确阈值时，用全部章节均值 ± 1σ 作为正常范围，超出则预警
  - 预警展示：表格中偏差超标的单元格高亮（橙色背景），hover 显示偏差值

#### 节奏对比 `RhythmCompareView`（新组件）

- 只读（计算值），不加 CRUD
- 替换原 `RhythmTrackView`
- 叠加曲线图（SVG）：
  - 预期曲线：蓝色虚线，从情节块 expected_mood 数值插值
  - 实际曲线：红色实线，从时间线 tension_score 绘制
  - 偏差区域：差值 > 阈值的章节区间，半透明橙色填充
- 偏差预警卡片
- 情绪标签分布

---

## 5. 交互模式统一

| 模式 | 适用子页面 | 说明 |
|------|-----------|------|
| 编辑按钮 → 编辑态 | 大纲、世界观、风格约束 | 右上角「编辑」，点击进入编辑态，保存/取消退出 |
| 弹窗表单 | 角色、关系、支线、伏笔 | 点击弹出 Dialog，保存后刷新列表 |
| inline 编辑 | 情节块 | 点击卡片展开为编辑表单 |
| 状态流转按钮 | 伏笔 | 只显示合法的下一步操作 |
| 只读 + 筛选 | 时间线、风格偏差、节奏对比 | 无编辑，时间线加章节筛选 |

列表编辑器（可增删条目）统一组件：`EditableList` — 每项一个 input + 删除图标，底部「+ 添加」按钮。

---

## 6. 后端 API 补全清单

| API | 方法 | 说明 |
|-----|------|------|
| `/projects/{id}/outline-summary` | PUT | 编辑大纲 summary / plot_points |
| `/projects/{id}/plot-blocks/{bid}` | PUT | 编辑情节块 |
| `/projects/{id}/plot-blocks/{bid}` | DELETE | 删除情节块 |
| `/projects/{id}/subplots` | POST | 创建支线 |
| `/projects/{id}/subplots/{sid}` | PUT | 编辑支线 |
| `/projects/{id}/subplots/{sid}` | DELETE | 删除支线 |
| `/projects/{id}/foreshadowings/{fid}` | PUT | 更新伏笔（状态流转/编辑内容） |

---

## 7. 前端 API 客户端补全清单

| 方法 | 说明 |
|------|------|
| `knowledgeApi.updateOutlineSummary()` | PUT 大纲 |
| `knowledgeApi.updatePlotBlock()` | PUT 情节块 |
| `knowledgeApi.deletePlotBlock()` | DELETE 情节块 |
| `knowledgeApi.createSubplot()` | POST 支线 |
| `knowledgeApi.updateSubplot()` | PUT 支线 |
| `knowledgeApi.deleteSubplot()` | DELETE 支线 |
| `knowledgeApi.updateForeshadowing()` | PUT 伏笔 |
| `knowledgeApi.createForeshadowing()` | POST 单条伏笔 |
| `relationApi.update()` | PUT 关系 |

---

## 8. 组件变更清单

### 新增组件

| 组件 | 位置 | 说明 |
|------|------|------|
| `EditableList` | `components/common/` | 可增删条目的列表编辑器 |
| `ForeshadowingFormDialog` | `components/workbench/tracking/` | 伏笔新增/编辑弹窗 |
| `SubplotFormDialog` | `components/workbench/structure/` | 支线新增/编辑弹窗 |
| `RhythmCompareView` | `components/workbench/tracking/` | 节奏叠加对比视图 |

### 修改组件

| 组件 | 变更 |
|------|------|
| `KnowledgeTab` | 删除 foreshadowing/timeline 子页面，SECTIONS 从 7→5 |
| `StructureTab` | 重命名 rhythm→预期节奏，RhythmView 删除 RhythmChart，加轻量折线+跳转链接 |
| `TrackingTab` | 重命名 style→风格偏差、rhythm→节奏对比，替换 RhythmTrackView→RhythmCompareView |
| `ForeshadowingTrackView` | 加状态流转按钮/编辑/新增 |
| `TimelineTrackView` | 加 ScoreBar + 章节筛选 |
| `StyleTrackView` | 加偏差预警列 |
| `OutlineView` | 加编辑态 |
| `WorldSettingView` | 扩展编辑范围 |
| `StyleConstraintsView` | 接线 PUT API + 编辑态 |
| `CharactersListView` | 集成 CharacterFormDialog + 删除 |
| `RelationsView` | 补编辑按钮 |
| `PlotBlocksView` | inline 编辑 + 删除 |
| `SubplotsView` | 新增/编辑/删除 |

### 删除组件

| 组件 | 说明 |
|------|------|
| `ForeshadowingView`（KnowledgeTab 内） | 知识库伏笔地图视图，功能迁入追踪 |
| `TimelineView`（KnowledgeTab 内） | 知识库时间线视图，功能迁入追踪 |
| `RhythmChart`（StructureTab 内） | 实际节奏柱状图，替换为轻量折线 |

---

## 9. 不在范围内

- 写作标签页的改动
- Agent 侧边栏的改动
- 后端 LangGraph 工作流节点的改动
- SSE 事件体系的改动
- 数据库 schema 变更（所有表已存在）
