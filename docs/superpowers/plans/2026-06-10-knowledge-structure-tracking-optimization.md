# 知识库/结构/追踪三标签页整合与 CRUD 补全 — 实现计划

> 对应 Spec: `docs/superpowers/specs/2026-06-10-knowledge-structure-tracking-optimization-design.md`

## 进度概览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 后端基础设施 | ✅ 已完成 | API 端点、Schema、Service 方法、busy lock |
| 知识库标签页 | ✅ 已完成 | 去重+大纲编辑+风格约束编辑+世界观扩展编辑+角色CRUD+关系编辑 |
| 结构标签页 | ✅ 已完成 | 情节块 CRUD、支线 CRUD、节奏重构 |
| 追踪标签页 | ✅ 已完成 | 伏笔流转、时间线增强、风格偏差、节奏对比 |
| 前端通用 | ✅ 已完成 | 错误处理、类型替换、数据刷新 |

---

## Step 1: 后端基础设施 ✅ 已完成

所有后端变更已在第四轮审查中实现并验证：

- [x] `knowledge.py` 新增 6 个端点（情节块 PUT/DELETE、支线 POST/PUT/DELETE、伏笔 PUT）
- [x] `knowledge.py` 所有写入端点加 `_check_busy` 检查（含批量端点 `create_foreshadowings_batch`、`create_plot_blocks_batch`）
- [x] `characters.py` 11 个写入端点加 `_check_busy` 检查
- [x] `knowledge_base.py` 新增 `delete_plot_block`、`delete_subplot`、`get_foreshadowing`
- [x] `schemas/knowledge.py` 新增 `PlotBlockUpdate`、`SubplotCreate`、`SubplotUpdate`、`ForeshadowingUpdate`
- [x] `plot_structure.py` 修复 ORM cascade 与 `ondelete="SET NULL"` 冲突
- [x] 伏笔状态单向流转校验（active→pending_reclaim→reclaimed）+ level 合法值校验
- [x] 支线 current_status 合法值校验
- [x] `api.ts` knowledgeApi 新增 6 个前端方法
- [x] `types/knowledge.ts` 前端类型定义

---

## Step 2: 知识库标签页 ✅ 已完成

### 2.1 去重 ✅ 已完成

- [x] 移除知识库「伏笔地图」子页面 → 归入追踪
- [x] 移除知识库「时间线」子页面 → 归入追踪
- [x] 清理相关 state、loadKnowledge 调用、import

### 2.2 大纲编辑 ✅ 已完成

- [x] 未确认大纲：显示「编辑」按钮，可编辑 summary + plot_points
- [x] 已确认大纲：显示「已确认」绿色标签，不显示编辑按钮
- [x] plot_points 使用 PlotPoint[] 结构编辑（event/conflict/hook）
- [x] 保存后调用 `incrementKnowledgeVersion()`

### 2.3 风格约束编辑 ✅ 已完成

- [x] 传入 `projectId` + `onUpdate` props
- [x] style_anchor textarea 编辑
- [x] taboo_words / forbidden_patterns / abstract_rules 标签列表可增删
- [x] 保存后调用 `incrementKnowledgeVersion()`

### 2.4 世界观扩展编辑 ✅ 已完成

**文件**: `frontend/src/components/workbench/knowledge/WorldSettingView.tsx`

- [ ] tiered_settings 三层（red/yellow/green）各自维护列表：每条可编辑/删除，底部「+ 添加」
- [ ] key_locations 标签式列表：可增删
- [ ] 编辑态：扩展现有编辑模式，一次保存全部字段
- [ ] 保存后调用 `incrementKnowledgeVersion()`

**注意**: 当前 WorldSettingView 只能编辑 `core_concept`，需要扩展编辑态覆盖 `tiered_settings` 和 `key_locations`。

### 2.5 角色集成 CRUD ✅ 已完成

**涉及文件**: 
- `frontend/src/components/character/CharacterFormDialog.tsx`
- `frontend/src/components/workbench/knowledge/CharactersListView.tsx`
- `frontend/src/components/workbench/knowledge/KnowledgeTab.tsx`

- [ ] CharacterFormDialog 改造编辑模式：新增 `character?: Character` prop，传入时填充初始值，标题"编辑角色"，onSubmit 调用 `characterApi.update`
- [ ] CharactersListView 增加 `projectId: number` + `onUpdate: () => void` props
- [ ] CharactersListView 顶部加「+ 新增角色」按钮
- [ ] 角色卡片加「编辑」按钮 → 弹出 CharacterFormDialog（编辑模式）
- [ ] 角色卡片加「删除」按钮 → confirm 提示"该角色的所有关联关系将一并删除"（级联类型：CASCADE，关系和演变规划自动删除）
- [ ] KnowledgeTab 的 CharactersSection 传递 projectId + onUpdate

### 2.6 关系编辑按钮 ✅ 已完成

**涉及文件**:
- `frontend/src/components/character/RelationFormDialog.tsx`
- `frontend/src/components/workbench/knowledge/RelationsView.tsx`

- [ ] RelationFormDialog 改造编辑模式：新增 `relation?: RelationWithCharacters` prop
- [ ] RelationCard 加「编辑」按钮 → 弹出 RelationFormDialog（编辑模式）
- [ ] 编辑保存后调用 `incrementKnowledgeVersion()`

---

## Step 3: 结构标签页 ✅ 已完成

### 3.1 情节块 inline 编辑+删除 ✅ 已完成

**文件**: `frontend/src/components/workbench/structure/StructureTab.tsx`

- [ ] PlotBlocksView 增加 `projectId: number` + `onUpdate: () => void` props
- [ ] 点击情节块卡片进入 inline 编辑态：title / expected_mood / questions_to_answer / questions_to_raise / must_happen
- [ ] questions 列表用可增删标签式编辑器（提取 KnowledgeTab.tsx:483 的 TagEditor 为共享组件 `components/common/TagEditor.tsx`，供知识库风格约束和结构情节块复用）
- [ ] 新增删除按钮 → confirm 提示"关联的问题链条目将失去情节块关联"（级联类型：SET NULL，PlotQuestion.plot_block_id 被设为 NULL）
- [ ] 保存/删除后调用 `incrementKnowledgeVersion()`

### 3.2 支线 CRUD ✅ 已完成

**文件**: `frontend/src/components/workbench/structure/StructureTab.tsx`

- [ ] SubplotsView 增加 `projectId: number` + `onUpdate: () => void` props
- [ ] 顶部「+ 新增支线」按钮，弹出表单：name / characters / current_status（下拉）/ raised_in_chapter / planned_intersection_chapter / expected_resolution_chapter
- [ ] 卡片加「编辑」按钮（inline 编辑态）
- [ ] 卡片加「删除」按钮（confirm）
- [ ] 保存/删除后调用 `incrementKnowledgeVersion()`

### 3.3 预期节奏重构 ✅ 已完成

**文件**: `frontend/src/components/workbench/structure/StructureTab.tsx`

- [ ] 删除 RhythmChart 组件（实际节奏柱状图）
- [ ] 保留预期节奏横条展示
- [ ] 新增轻量实际张力折线预览（SVG 折线，无柱状图/数据点标注）
- [ ] 底部加「查看详细对比 →」链接，点击切换到追踪标签页的节奏对比子页面
- [ ] 「查看详细对比 →」链接点击时调用 `useWorkbenchStore.getState().setActiveTab('tracking')` 切换到追踪标签页

**注意**: 无需 prop drilling，RhythmView 内部直接调用 `useWorkbenchStore.getState().setActiveTab('tracking')` 即可。`workbenchStore` 已有 `activeTab` + `setActiveTab`（workbenchStore.ts:48-49,105-106），TabNavigation 已通过此状态切换标签页。

---

## Step 4: 追踪标签页 ✅ 已完成

### 4.1 伏笔追踪状态流转+编辑+新增 ✅ 已完成

**文件**: `frontend/src/components/workbench/tracking/TrackingTab.tsx`

- [ ] 按状态分组显示：待回收（顶部）→ 活跃 → 已回收（底部）
- [ ] 状态流转按钮：
  - 活跃 → 显示「⏱ 标记待回收」
  - 待回收 → 显示「✓ 确认已回收」+ 逾期预警（预计回收章 < currentChapterNum 时标红 ⚠ 已逾期）
  - 已回收 → 无流转按钮，内容划线淡化
- [ ] 所有状态都有「编辑」按钮（弹出表单：content / level / planted_chapter / expected_resolve_chapter / related_characters，**不含 status 字段**）
- [ ] 确认回收时自动填入 resolved_chapter（从 `useProjectStore.getState().currentChapterNum` 获取，projectStore.ts:8 已有此状态）
- [ ] 顶部「+ 新增伏笔」按钮，弹出表单（level 下拉：hint/strengthened/revealed，status 默认 active）
- [ ] 流转/编辑/新增后调用 `incrementKnowledgeVersion()`
- [ ] **不提供伏笔删除功能**：伏笔是写作过程追踪数据，应通过状态流转到"已回收"终结，而非删除。后端无 DELETE 端点（符合 Spec 约束）

### 4.2 时间线增强 ✅ 已完成

**文件**: `frontend/src/components/workbench/tracking/TrackingTab.tsx`

- [ ] 加入 ScoreBar（节奏/张力/情绪评分条，从知识库版迁移）
- [ ] 保留因果链展示
- [ ] 加章节范围筛选（chapterStart/chapterEnd 两个 number input）
- [ ] 只读，无需编辑

### 4.3 风格偏差升级 ✅ 已完成

**文件**: `frontend/src/components/workbench/tracking/TrackingTab.tsx`

- [ ] 保留表格（段落数/平均段长/对话占比/平均句长）+ 对话占比折线
- [ ] 新增偏差预警列：单元格背景标红 + hover 显示偏差值
- [ ] 预警逻辑：优先从 style_constraints 解析阈值，无阈值时用均值 ± 1σ
- [ ] 前端计算（数据量小），不增加后端负担

### 4.4 节奏对比升级 ✅ 已完成

**文件**: `frontend/src/components/workbench/tracking/TrackingTab.tsx`

- [ ] 叠加曲线图：预期曲线（虚线，从情节块 expected_mood 插值）+ 实际曲线（实线，从时间线张力数据）
- [ ] 偏差区域用半透明填充标注
- [ ] 偏差超出阈值的数据点用橙色高亮
- [ ] 偏差预警卡片：列出偏差最大的章节
- [ ] 情绪标签分布：按章显示 emotion_tag
- [ ] 预期曲线插值逻辑：mood 映射数值表 + 线性插值 + 间隙延伸

**需要的数据**: 追踪标签页需同时加载 plotBlocks 和 timeline。当前 `loadTracking` 只加载 foreshadowings/timeline/styleSnapshots（TrackingTab.tsx:29-37），需扩展为同时调用 `knowledgeApi.getPlotBlocks(projectId)` 获取情节块数据用于预期曲线插值。新增 `plotBlocks` state，在 loadTracking 的 Promise.allSettled 中加入该请求。

---

## Step 5: 前端通用 ✅ 已完成

### 5.0 TagEditor 提取为共享组件 ✅ 已完成

**当前状态**: `TagEditor` 是 `KnowledgeTab.tsx:483` 的局部 const，无法被 StructureTab 复用。

- [ ] 将 `TagEditor` 提取为 `frontend/src/components/common/TagEditor.tsx`，导出为独立组件
- [ ] 接口：`{ items: string[]; setItems: (v: string[]) => void; placeholder: string }`
- [ ] KnowledgeTab.tsx 中删除局部定义，改为 import 共享组件
- [ ] StructureTab.tsx 中情节块/支线的列表编辑器使用共享 TagEditor

### 5.1 错误处理统一 ✅ 已完成

- [ ] 所有新增 CRUD 操作使用 `sonner` toast
- [ ] 成功：`toast.success('保存成功')` / `toast.success('已删除')`
- [ ] 失败：`toast.error('保存失败：' + err.message)`
- [ ] 并发冲突（409）：`toast.error('项目正在被 Agent 使用，请稍后再试')`
- [ ] 大纲已确认（400）：`toast.error('大纲已确认，无法编辑')`

### 5.2 数据刷新 ✅ 已完成

- [ ] 所有写入操作后调用 `incrementKnowledgeVersion()`
- [ ] TrackingTab 已加 knowledgeVersion 订阅 ✅
- [ ] KnowledgeTab 已有 knowledgeVersion 订阅 ✅
- [ ] StructureTab 已有 knowledgeVersion 订阅 ✅

**outlineApi 导入模式**: OutlineView 编辑模式使用动态 `import('@/lib/api')` 获取 `outlineApi`（避免循环依赖）。此模式已验证可行，新增代码如遇类似循环依赖可沿用。

### 5.3 类型替换 ✅ 已完成

- [ ] 三个标签页组件中的 `any` 类型逐步替换为 `types/knowledge.ts` 中的具体类型
- [ ] 优先级：新代码必须用具体类型，存量 `any` 在触碰相关组件时顺带替换

---

## 实现顺序建议

```
Step 5.0 TagEditor 提取       （简单，提取共享组件，优先于 3.1）
Step 2.4 世界观扩展编辑       （简单，扩展现有组件）
Step 2.5 角色集成 CRUD        （中等，CharacterFormDialog 改造）
Step 2.6 关系编辑按钮          （简单，RelationFormDialog 改造）
Step 5.1 错误处理统一          （简单，可穿插在每步中）
Step 3.1 情节块编辑+删除       （中等，inline 编辑态）
Step 3.2 支线 CRUD            （中等，新增+编辑+删除）
Step 3.3 预期节奏重构          （中等，SVG 折线+跳转）
Step 4.1 伏笔状态流转+编辑     （复杂，状态机+表单+逾期检测）
Step 4.2 时间线增强            （简单，ScoreBar+筛选）
Step 4.3 风格偏差升级          （中等，预警逻辑）
Step 4.4 节奏对比升级          （复杂，叠加曲线+插值+偏差计算）
Step 5.3 类型替换              （渐进式，贯穿始终）
```

---

## 范围外事项

以下变更不在本次实现范围内（详见 Spec）：

- 写作标签页变更、Agent 侧边栏变更
- 引入第三方图表库（节奏对比/风格偏差继续使用 SVG）
- 伏笔批量创建 API 变更（已有 batch 端点）
- Alembic 迁移（无新表/新列，变更在已有 JSON 列内）
- 旧端点补 busy 检查（chapters.py、outline.py 等）
- KnowledgeBaseService 统一迁移到 session() 上下文管理器
- 已确认大纲的取消确认功能

---

## 关键风险

| 风险 | 缓解 |
|------|------|
| 跳转追踪标签页需要跨组件通信 | ✅ 已解决：workbenchStore 已有 setActiveTab，直接调用即可 |
| 节奏对比的 mood 数值映射表需要覆盖所有已知值 | 映射表定义为常量，未知 mood 值默认为 3 |
| 伏笔确认回收时 currentChapterNum 可能不准确 | 前端从 projectStore 获取，该值在写作过程中持续更新 |
| 风格偏差预警的阈值解析可能不稳定 | 优先用 style_constraints 的明确阈值，回退到统计范围 |
