# ProjectCard 重设计

## 背景

项目首页卡片存在多个 BUG 和信息展示问题，需要修复并优化卡片信息架构。

## 发现的 BUG

### BUG #1：后端 ProjectListResponse schema 类型不匹配

`ProjectListResponse.projects` 声明为 `List[ProjectResponse]`，但 `list_projects` 实际返回 `ProjectDetailResponse` 对象。Pydantic 不报错但 schema 声明与实际不一致，影响 OpenAPI 文档和类型推断。

**修复**：将 `ProjectListResponse.projects` 类型改为 `List[ProjectDetailResponse]`。

### BUG #2：项目创建后首页列表不刷新

`CreateProjectDialog` 创建成功后直接 `navigate` 跳转到工作台。当用户通过浏览器后退回到首页时，项目列表仍为旧数据。

**根因**：`Home.tsx` 的 `fetchProjects` 仅在 `isAuthenticated` 变化时触发，页面重新获得焦点时不会刷新。

**修复**：在 `Home.tsx` 中添加 `visibilitychange` 事件监听，页面从隐藏恢复时刷新列表。这比改 `CreateProjectDialog` 的 props 更根本——无论从哪个页面返回首页都能拿到最新数据。

### BUG #3：0/0 章节显示问题

新创建项目 `chapter_count=0` 时显示 "0/0 章"，看起来像数据缺失。

**修复**：本次重设计中移除了章节进度条和比例显示，此 BUG 自然消除。

## 设计决策

### 卡片信息架构（从旧到新）

**旧卡片**：
- 项目名 + 内部阶段标签（创意孵化/结构设计/写作中/修订中）
- completed_chapters/chapter_count 章 + total_words 字 + updated_at（仅日期）
- 进度条（章节完成百分比）
- 继续按钮 + 删除按钮

**新卡片**：
- 项目名 + 状态标签（连载中 / 已完结）
- 已写字数（大号加粗，视觉焦点）
- 当前章节（来自 workflow_state.current_chapter，新项目显示 "—"）
- 更新时间（带时分）
- 继续按钮 + 删除按钮（保留）

**移除的内容**：
- 内部 Phase 四阶段标签 → 改为面向创作者的高层状态（连载中/已完结）
- 章节进度条 → 小说创作没有明确进度概念
- 章节比例（completed_chapters/chapter_count）→ 同上
- 目标字数 → 改为已写字数
- AI 处理中状态 → 在首页无实际作用，工作台内感知即可

### 状态判断逻辑

后端新增 `is_completed` 字段，在 `ProjectDetailResponse` 中返回：

```python
# backend/app/schemas/project.py
class ProjectDetailResponse(ProjectResponse):
    chapter_count: int = 0
    completed_chapters: int = 0
    progress_percentage: float = 0.0
    is_completed: bool = False  # 新增
```

```python
# backend/app/api/projects.py - get_project_detail 函数
is_completed = chapter_count > 0 and completed_chapters == chapter_count
```

判断逻辑：`chapter_count > 0`（已有章节）且 `completed_chapters == chapter_count`（所有章节审核通过）。`chapter_count=0` 的新项目不会误判为已完结。

前端根据 `is_completed` 显示：
- `is_completed=true` → "已完结"（绿色标签）
- `is_completed=false` → "连载中"（蓝色标签）

内部 Phase（incubation/structure/writing/revision）仍保留在工作台内部使用，不在卡片上暴露。

### 后端改动

1. **ProjectListResponse.projects 类型**：`List[ProjectResponse]` → `List[ProjectDetailResponse]`
2. **ProjectDetailResponse 新增字段**：`is_completed: bool`，由 `get_project_detail` 计算
3. **ProjectDetailResponse 新增字段**：`is_busy: bool`，来自 `Project.is_busy`，供工作台 busy lock 使用

### 前端改动

1. **ProjectCard 组件重写**：
   - 移除 `STAGE_CONFIG` 四阶段配置
   - 新增状态判断：根据 `project.is_completed` 显示连载中/已完结
   - 信息行：已写字数（大号）、当前章节、更新时间（带时分）
   - 当前章节来源：`project.workflow_state?.current_chapter`
   - 新项目（`workflow_state` 为 null 或 `current_chapter=1` 且 `chapter_count=0`）显示 "—"
   - 保留继续按钮 + 删除按钮

2. **ProjectCardSkeleton 更新**：
   - 骨架屏结构匹配新卡片布局：标题行（项目名+状态标签）→ 大号字数 → 章节行 → 时间行 → 按钮行

3. **Home.tsx**：
   - 添加 `visibilitychange` 事件监听，页面从隐藏恢复时调用 `fetchProjects()`
   - 组件卸载时移除事件监听

4. **类型定义**：
   - `ProjectDetail` 新增 `is_completed: boolean`、`is_busy: boolean`

## 不在范围内

- 工作台内部的 Phase 展示（保持现状）
- 新建项目占位卡片的样式调整
- 删除确认对话框的改动
