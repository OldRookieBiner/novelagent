---
name: settings-sidebar-layout
description: 设置页面重构 - 添加左侧导航栏布局
type: project
---

# 设置页面左侧导航栏重构设计

## 背景

当前设置页面采用单页面卡片堆叠布局，将"模型配置"和"审核设置"两个功能区块垂直排列。为提升用户体验和未来扩展性，需重构为左侧导航栏 + 右侧内容区的布局。

## 目标

- 添加左侧导航栏，区分不同设置分类
- 保持现有功能不变（模型配置 + 审核设置）
- 使用项目现有 shadcn/ui 灰色中性主题风格
- 采用组件内状态切换，不修改路由配置

## 设计方案

### 布局结构

```
┌─────────────────────────────────────────────┐
│ Header                                       │
├────────────┬────────────────────────────────┤
│ 导航栏     │ 内容区                          │
│ (220px)    │ (flex-1)                        │
│            │                                 │
│ ┌────────┐ │ ┌─────────────────────────────┐│
│ │设置    │ │ │ 模型配置                     ││
│ ├────────┤ │ │                             ││
│ │模型配置│ │ │ - 模型提供商                 ││
│ │(选中)  │ │ │ - API Key                   ││
│ ├────────┤ │ │ - 删除 API Key 按钮          ││
│ │审核设置│ │ │ - 保存按钮                   ││
│ └────────┘ │ └─────────────────────────────┘│
└────────────┴────────────────────────────────┘
```

### 导航项

| 分类 | 说明 |
|------|------|
| 模型配置 | 模型提供商选择、API Key 管理 |
| 审核设置 | 启用审核开关、审核严格度选择 |

### 交互方式

- **状态切换**：使用 `useState` 管理 `activeTab` 状态
- **点击导航项**：切换右侧内容区显示对应设置
- **无 URL 路由**：单 URL `/settings`，无浏览器历史记录

### 样式规范

使用项目 shadcn/ui 主题变量：

| 元素 | 样式 |
|------|------|
| 导航栏容器 | `w-[220px] border-r bg-background` |
| 选中项 | `bg-secondary text-foreground font-medium rounded-md` |
| 未选中项 | `bg-transparent text-muted-foreground hover:bg-secondary/50 rounded-md` |
| 内容区 | `flex-1 p-6` |
| 保存按钮 | `Button` 组件（bg-primary 深灰背景） |

### 组件结构

```tsx
// Settings.tsx
const [activeTab, setActiveTab] = useState<'model' | 'review'>('model')

// 导航项配置
const tabs = [
  { id: 'model', label: '模型配置' },
  { id: 'review', label: '审核设置' },
]

// 渲染
<div className="flex">
  {/* 左侧导航 */}
  <nav className="w-[220px] ...">
    {tabs.map(tab => (
      <button
        className={activeTab === tab.id ? 'bg-secondary ...' : 'bg-transparent ...'}
        onClick={() => setActiveTab(tab.id)}
      >
        {tab.label}
      </button>
    ))}
  </nav>

  {/* 右侧内容 */}
  <div className="flex-1 ...">
    {activeTab === 'model' && <ModelSettings />}
    {activeTab === 'review' && <ReviewSettings />}
  </div>
</div>
```

## 实现要点

1. **重构 Settings.tsx**：将现有单页面拆分为导航 + 内容区
2. **提取子组件**：可考虑将模型配置和审核设置提取为独立组件（可选）
3. **保持 API Key 管理逻辑**：删除 API Key 功能不变
4. **保持表单状态**：每个设置区的表单状态独立管理

## 不在范围内

- 深色模式适配（已有 CSS 变量支持，自动适配）
- URL 路由切换（未来可扩展）
- 新增设置分类（未来可扩展）

## Why

用户反馈当前设置页面布局不够直观，希望通过左侧导航栏区分不同设置分类。采用此设计可提升用户体验，并为未来添加更多设置分类预留扩展空间。

## How to apply

实现时遵循项目现有的 shadcn/ui + Tailwind 样式规范，不引入新的颜色或样式变量，保持视觉一致性。