# 标签页重构设计

**日期**: 2026-04-30
**版本**: v0.6.5

---

## 1. 背景

当前工作台有 2 个顶层 Tab：
- **规划 Tab**：灵感 → 人物 → 关系
- **创作 Tab**：小说大纲 → 章节大纲 → 写作

小说大纲本质属于规划阶段（定义整体故事脉络），放在创作 Tab 不符合自然工作流程。章节大纲和章节正文都是独立的重要阶段，不应挤在一个 Tab 中。

## 2. 目标

1. 将小说大纲从「创作」Tab 移到「规划」Tab，放在灵感下方
2. 废除「创作」Tab
3. 将章节大纲和章节正文各自提升为独立的顶层 Tab（原"写作"Tab 改名为"章节正文"）
4. 章节大纲和章节正文 Tab 无侧边栏（全屏面板）

## 3. 设计

### 3.1 变更概览

**变更前**：
```
[规划] [创作]
├──────┐
│ 灵感  │ └─ 小说大纲 / 章节大纲 / 写作（侧边栏菜单）
│ 人物  │
│ 关系  │
└──────┘
```

**变更后**：
```
[规划] [章节大纲] [章节正文]
├──────┐
│ 灵感  │     无侧边栏      无侧边栏
│ 小说大纲│   全屏章节大纲   全屏章节正文
│ 人物  │
│ 关系  │
└──────┘
```

### 3.2 类型定义改动

**文件**: `frontend/src/types/workbench.ts`

改动：
- `WorkbenchTab`: `'planning' | 'creation'` → `'planning' | 'chapter_outlines' | 'writing'`
- `PlanningMenuItem`: 新增 `'outline'`
- **删除** `CreationMenuItem` 类型
- `MenuItem` 仅从 `PlanningMenuItem` 推导
- `PLANNING_MENUS` 顺序变为：
  1. 灵感 (Lightbulb)
  2. 小说大纲 (FileText)
  3. 人物 (Users)
  4. 关系 (Link)
- **删除** `CREATION_MENUS`

### 3.3 Store 改动

**文件**: `frontend/src/stores/workbenchStore.ts`

改动：
- `initialState.activeMenuItem` 保持 `'inspiration'`（不变）
- `setActiveTab` 逻辑：
  - 切换到 `'planning'` → `activeMenuItem` = `'inspiration'`
  - 切换到 `'chapter_outlines'` / `'writing'` → 不改变 `activeMenuItem`（渲染逻辑改为基于 `activeTab` 而非 `activeMenuItem`）
  - 注意：`writing` 作为 Tab key 保持不变（内部标识），仅显示标签改为"章节正文"

### 3.4 TabNavigation 改动

**文件**: `frontend/src/components/workbench/TabNavigation.tsx`

改动：
- TABS 数组改为 3 项：
  1. `{ key: 'planning', label: '规划', icon: Lightbulb }`
  2. `{ key: 'chapter_outlines', label: '章节大纲', icon: BookOpen }`
  3. `{ key: 'writing', label: '章节正文', icon: PenTool }`

### 3.5 WorkbenchSidebar 改动

**文件**: `frontend/src/components/workbench/WorkbenchSidebar.tsx`

改动：
- 删除 `CREATION_MENUS` 引用
- `menus` 逻辑改为：当 `activeTab === 'planning'` 时返回 `PLANNING_MENUS`，否则返回 `[]`
- `ICON_MAP` 移除不再需要的图标（可选清理）

### 3.6 ProjectWorkbench 渲染改动

**文件**: `frontend/src/pages/ProjectWorkbench.tsx`

改动：
- `renderContent` 不再仅依赖 `activeMenuItem`，改为同时依赖 `activeTab`：
  - `chapter_outlines` Tab → 直接渲染 `ChapterOutlinePanel`
  - `writing` Tab → 直接渲染 `WritingPanel`
  - `planning` Tab → 按 `activeMenuItem` 渲染对应面板
- 新增 `case 'outline'` 在 planning 分支中（因为它现在是 planning 的子菜单）
- `writing` Tab key 不变，但 TabNavigation 中显示标签改为"章节正文"

### 3.7 面板文件移动（可选）

- `OutlinePanel.tsx` 从 `components/workbench/creation/` 移动到 `components/workbench/planning/`
- `ChapterOutlinePanel.tsx` 和 `WritingPanel.tsx` 保持在 `creation/` 或移动到独立目录（不强制）

### 3.8 向后兼容

- 后端 API：无变化
- 面板组件内部逻辑：无变化
- LangGraph 工作流：无变化
- 路由：无变化

## 4. 实现步骤

1. 修改 `types/workbench.ts` → 更新类型和菜单配置
2. 修改 `stores/workbenchStore.ts` → 更新 `setActiveTab` 逻辑
3. 修改 `TabNavigation.tsx` → 3 个 Tab 按钮
4. 修改 `WorkbenchSidebar.tsx` → 仅在 planning Tab 显示侧边栏
5. 修改 `ProjectWorkbench.tsx` → 更新渲染逻辑，`chapter_outlines`/`writing` Tab 直接渲染面板
6. 移动 `OutlinePanel.tsx` 到 `planning/` 目录（可选）
7. 前端测试验证
8. Docker 构建验证