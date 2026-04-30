# 项目列表页与工作台协调优化

## 概述

优化项目列表页（Home），使其与新工作台界面的视觉风格和布局协调一致。

## 目标

1. Home 页添加全局 Header，建立品牌连续性
2. ProjectCard 重新设计，与 Workbench 组件风格统一
3. 网格布局优化，支持自适应列数
4. 新建项目入口改为占位卡片 + Dialog 模式

---

## 设计详情

### 一、Home 页全局 Header

**当前状态：** Home 页无全局 Header，只有一个独立的页面级 Header（"我的项目" + 新建按钮）。

**改造后：** 添加顶层全局 Header，显示 Logo 和用户操作。

```
┌─────────────────────────────────────────────┐
│ 📖 NovelAgent              admin  ⚙  🚪    │  ← 全局 Header (h-14)
├─────────────────────────────────────────────┤
│ 我的项目                                     │  ← 内容区标题
├─────────────────────────────────────────────┤
│ [卡片网格]                                   │  ← auto-fill 自适应
└─────────────────────────────────────────────┘
```

**Header 规范：**
- 高度: `h-14` (56px)，与 Workbench Header 一致
- 背景: `bg-white border-b`
- 内边距: `px-6`
- 左侧: NovelAgent Logo（BookOpen 图标 + 文字，复用现有 Header 组件中的样式）
- 右侧: 用户名 + 设置图标 + 登出图标（复用现有 Header 组件）

**实现方式：** 提取现有 `components/layout/Header.tsx` 组件，在 Home 页引入。Settings 页已使用该组件，无需修改。

### 二、内容区布局

```
┌─────────────────────────────────────────────┐
│ 我的项目                                     │  ← text-lg font-semibold
├─────────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │+新建 │ │项目1 │ │项目2 │ │项目3 │  ...  │  ← auto-fill 网格
│ │      │ │      │ │      │ │      │       │
│ └──────┘ └──────┘ └──────┘ └──────┘       │
└─────────────────────────────────────────────┘
```

**网格规范：**
- `grid-template-columns: repeat(auto-fill, minmax(260px, 1fr))`
- 间距: `gap-4`
- 内容区 padding: `p-6`
- 最小卡片宽度 260px，保证卡片内容不会过度压缩

**空状态（项目数为0）：**
- 隐藏网格布局，改为居中显示
- 一个占位"创建新项目"卡片（固定宽度 `max-w-xs`，水平居中）
- 下方提示文字: "创建你的第一个项目，开始写作之旅"

### 三、ProjectCard 重新设计

采用 Workbench 灵感选择器风格，`border-2 rounded-lg`。

```
┌─────────────────────────────────┐
│ 项目名称           [灵感采集]   │  ← 标题 + 柔和标签
│                                 │
│ 📄 第 0/0 章  📏 0 字  🕐 今天 │  ← 元数据行（inline 排列）
│                                 │
│ ▓░░░░░░░░░░░░░░  5%             │  ← 进度条 + 百分比
│ 进行中                          │  ← 状态文字
│                                 │
│ [继续]  [删除]                  │  ← 操作按钮
└─────────────────────────────────┘
```

**卡片样式规范：**

| 属性 | 值 |
|------|-----|
| 边框 | `border-2 border-border rounded-lg` |
| 背景 | `bg-card` |
| 内边距 | `p-4` |
| 阴影 | 无（移除 hover:shadow-lg） |
| hover | `hover:border-primary/30`（边框微妙高亮） |

**阶段标签：**
- 从彩色背景 + 白色文字改为柔和背景 + 深色文字（pill 形状）
- `rounded-full`

| 阶段 | 背景色 | 文字色 |
|------|--------|--------|
| 灵感采集 | `bg-yellow-50` | `text-yellow-700` |
| 大纲生成 | `bg-blue-50` | `text-blue-700` |
| 章节纲 | `bg-purple-50` | `text-purple-700` |
| 写作中 | `bg-green-50` | `text-green-700` |
| 审核中 | `bg-orange-50` | `text-orange-700` |
| 已完成 | `bg-emerald-50` | `text-emerald-700` |
| 暂停 | `bg-gray-100` | `text-gray-600` |

**元数据：**
- 从垂直排列改为水平 inline 排列
- 字体: `text-xs text-muted-foreground`
- 分隔符: 空格 + `·`

**进度条：**
- 使用 shadcn/ui Progress 组件
- 高度: `h-1.5`
- 完成态（100%）进度条颜色改为绿色

**按钮：**
- 主要按钮: `<Button size="sm">` — 继续/查看
- 次要按钮: `<Button variant="outline" size="sm">` — 删除

### 四、新建项目入口

**占位卡片：**
```
┌─────────────────────────────────┐
│                                 │
│           ┌───┐                │
│           │ + │                │  ← 圆形图标
│           └───┘                │
│        新建项目                 │
│                                 │
└─────────────────────────────────┘
```

- 位置: 网格第一项
- 边框: `border-2 border-dashed border-border`
- hover: `hover:border-primary/50 hover:bg-primary/5`
- 点击弹出 Dialog

**Dialog：**
- 标题: "新建项目"
- 输入框: 项目名称（maxLength: 100）
- 按钮: 取消 / 创建
- 复用现有 shadcn/ui Dialog 组件

### 五、Workbench Header 优化

为保持一致性，Workbench 的全局 Header 也需要同步添加。

当前 WorkbenchLayout Header：
```
[← 返回]  项目名称  [进度条]  [百分比]
```

改造后：
```
[📖 NovelAgent]  admin ⚙ 🚪    ← 全局 Header
[← 返回]  项目名称  [进度条]    ← 项目 Header
```

- 全局 Header 和项目 Header 都是 `h-14`
- 项目 Header 移除百分比文字（进度条本身已足够）
- 全局 Header 与 Home 页完全一致

---

## 涉及文件

### 需要修改

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/Home.tsx` | 添加全局 Header；重构内容区布局；网格改为 auto-fill；移除旧内联新建表单 |
| `frontend/src/components/common/ProjectCard.tsx` | 重写为 border-2 风格；标签改为柔和色 pill；元数据横向排列 |
| `frontend/src/components/workbench/WorkbenchLayout.tsx` | 添加全局 Header；优化项目 Header |

### 可能需要新增

| 文件 | 说明 |
|------|------|
| `frontend/src/components/project/CreateProjectDialog.tsx` | 新建项目 Dialog 组件（从 Home 中抽取） |

### 无需修改

| 文件 | 原因 |
|------|------|
| `frontend/src/components/layout/Header.tsx` | 已存在且满足需求，直接复用 |
| `frontend/src/App.tsx` | 路由无需改动 |

---

## 验收标准

1. Home 页显示全局 Header（Logo + 用户名/设置/登出）
2. ProjectCard 采用 `border-2 rounded-lg` 无阴影风格
3. 阶段标签为柔和色 pill (`rounded-full`)
4. 网格使用 `auto-fill(minmax(260px, 1fr))` 自适应
5. 新建项目为占位虚线卡片，点击弹 Dialog
6. Workbench 页也显示全局 Header
7. 两个页面的 Header 高度、配色、字体一致
8. 空项目列表时显示占位卡片 + 引导文字
9. 加载骨架屏风格与新卡片一致
10. 删除确认 Dialog 样式不变