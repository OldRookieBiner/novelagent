# 新工作台替换旧界面设计

> 版本：v0.7.0
> 日期：2026-04-29

## 目标

将项目主入口 `/project/:id` 指向新的工作台页面，删除旧页面路由，全面启用新工作台。

## 设计

### 路由变更

| 旧路由 | 变更 | 说明 |
|--------|------|------|
| `/project/:id` | 重定向到 `/project/:id/workbench` | 原 ProjectDetail 页面停用 |
| `/project/:id/write` | 删除 | 写作功能由工作台 WritingPanel 替代 |
| `/project/:id/read/:chapterNum` | 删除 | 审核功能由工作台 AIAssistantPanel 替代 |
| `/project/:id/characters` | 删除 | 人物/关系功能由工作台 CharacterPanel/RelationPanel 替代 |
| `/project/:id/workbench` | 不变 | 新工作台主页面 |

### 入口点变更

- 项目列表页（Home）项目卡片链接从 `/project/:id` 改为 `/project/:id/workbench`

### 不变的部分

- `/project/:id/workbench` 路由和 ProjectWorkbench 组件
- Layout、Home、Login、Settings 页面
- 所有 store、hooks、API 客户端

### 旧组件处理

采用渐进清理策略：先改路由，旧组件文件暂不删除，后续确认无引用后再清理。

旧组件列表（本次不动）：
- `pages/ProjectDetail.tsx`
- `pages/CharacterSetting.tsx`
- `pages/Writing.tsx`
- `pages/Reading.tsx`
- `components/project/OutlineWorkflow.tsx`
- `components/project/InspirationForm.tsx`
- `components/project/InspirationEditor.tsx`
- `components/project/ChapterList.tsx`
- `components/project/ChapterOutlineDetail.tsx`
- `components/project/StepNavigation.tsx`
- `components/project/HistoryContent.tsx`
- `components/project/ResumeDialog.tsx`

### 影响范围

- `frontend/src/App.tsx` — 路由配置修改
- `frontend/src/pages/Home.tsx` — 项目卡片链接更新

### 风险评估

- **低风险** — 仅路由重定向和链接修改，不影响已有工作台功能
- 旧页面无用户可见入口，但代码保留可随时恢复