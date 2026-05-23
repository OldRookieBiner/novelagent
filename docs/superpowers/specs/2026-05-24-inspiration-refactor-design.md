# 灵感页面重构设计文档

## 概述

将灵感采集页面从「表单/对话双模式切换」重构为「Agent 驱动表单」统一体验。

**核心变化：**
- 删除 `InspirationChatPanel` + `InspirationPreview`（对话由右栏 AI 搭档承载）
- 删除表单/对话模式切换
- 左栏：精简参数面板（卡片式分组，三种 Agent 状态）
- 右栏：AICompanionSidebar 通过 tool call 联动表单
- 1400 行巨型组件拆分为 4 个聚焦文件

## 目标

1. **Agent 增强可控性**：通过 Agent 引导用户完善灵感参数，提升小说生成质量
2. **消除重复**：灵感页面的独立聊天窗口与右栏 Agent 功能重叠，删除冗余
3. **代码可维护**：拆分巨型组件，提取自定义 hook
4. **UX 优化**：表单信息层级清晰，必填/选填/Agent 状态一目了然

## 架构设计

### 组件拆分

```
InspirationPanel.tsx (~80行 编排组件)
├── InspirationForm.tsx (~250行 参数面板)
│   ├── InspirationFieldGroup.tsx (~40行 字段组容器，含状态标签)
│   └── InspirationTemplatePreview.tsx (~60行 Prompt预览)
├── useInspirationForm.ts (~350行 hook: 状态+校验+持久化+Agent联动)
├── AICompanionSidebar (现有，增强灵感 tool context)
└── OutlineProgressDialog (现有，不变)
```

**删除文件：**
- `InspirationChatPanel.tsx`
- `InspirationPreview.tsx`
- `InspirationPanel.tsx` 中表单模式切换逻辑 + 内联 JSX ~600 行

**拆分 `inspiration.ts`：**
- `inspiration/types.ts` — 类型定义
- `inspiration/config.ts` — 选项常量
- `inspiration/templates.ts` — 快捷模板 + Prompt 生成
- `inspiration/utils.ts` — 工具函数 + localStorage 持久化

### 文件结构

```
frontend/src/components/workbench/planning/
├── InspirationPanel.tsx        # 编排组件
├── InspirationForm.tsx          # 参数面板
├── InspirationFieldGroup.tsx    # 字段组容器
├── InspirationTemplatePreview.tsx
├── OutlineProgressDialog.tsx    # 现有

frontend/src/lib/inspiration/
├── types.ts
├── config.ts
├── templates.ts
├── utils.ts
```

## 数据流

### Agent ↔ 表单双向桥接

```
用户右栏说话 → Agent 分析 → tool call → SSE → workbenchStore
                                                    ↓
                  表单字段更新 ← useInspirationForm ← inspirationFields
                                                    ↓
                  字段状态标签 → 'Agent 已提取' 高亮 0.5s
```

```
用户直接点表单 → setState → workbenchStore.inspirationFields
                                 ↓
                  Agent 读取 → 识别已填字段 → 追问下一缺失项
```

### State 位置

灵感表单状态放在 `workbenchStore` 中，与 Agent 共享上下文：

```typescript
inspirationFields: InspirationData
inspirationFieldStatus: Record<string, FieldStatus>
```

localStorage 草稿作为离线缓存（useInspirationForm 内部管理）。

### 字段状态枚举

```typescript
type FieldStatus =
  | 'agent_populated'  // Agent 填充，紫色标签 + 蓝色边框
  | 'agent_asking'     // Agent 询问中，黄色标签 + 虚线边框
  | 'empty'            // 待填写，无标签
  | 'user_filled'      // 用户手动填写，无标签
```

## Agent Tool 定义

后端新增 9 个灵感工具：

| Tool | 参数 | 说明 |
|------|------|------|
| `set_novel_type` | `value: string` | 题材 |
| `set_target_reader` | `value: "male" \| "female"` | 目标读者 |
| `set_era` | `value: string` | 年代 |
| `set_novel_length` | `value: "short" \| "medium" \| "long"` | 篇幅 |
| `set_core_theme` | `value: string` | 核心主题 |
| `set_protagonist` | `lead_type, custom_value?` | 人设 |
| `set_world_setting` | `value, custom_value?` | 世界观 |
| `set_style_preference` | `value: string` | 风格偏好 |
| `recommend_inspiration` | — | 根据已填字段推荐剩余选项 |

每个 tool 执行时校验值有效性，更新 workbenchStore，返回确认消息 + 下一个缺失字段提示。

## 视觉设计

### 布局（三栏）

```
[左导航] [参数面板 flex:1] [AI 搭档 w:240px]
          ├ 快捷模板按钮
          ├ 基础设定卡片 (Agent 已提取)
          ├ 主角设定卡片 (Agent 询问中)
          ├ 高级设定卡片 (可折叠)
          ├ Prompt 预览卡片
          └ [模型选择] [进度条] [开始规划]
```

### 字段组卡片状态

| 状态 | 边框 | 标签 | 背景 |
|------|------|------|------|
| Agent 已提取 | `border-indigo-200` | 紫色 "Agent 已提取" | `bg-indigo-50` |
| Agent 询问中 | `border-amber-300` | 黄色 "Agent 询问中" | `bg-amber-50` |
| 待填写 | `border-gray-200` | 无 | `bg-white` |

### Prompt 预览

- 位置：表单底部，确认按钮上方
- 默认折叠显示前 3 行
- 点击展开完整编辑
- 手动编辑后不再自动更新（与现有逻辑一致）
- 复制按钮

## 实现边界

**本次不做：**
- 后端 Agent 灵感 tool 的具体 LLM prompt 优化
- AICompanionSidebar 的 UI 变更（仅增强 context）
- 灵感之外的其他 Tab 变更

**本次做：**
- 前端组件拆分、hook 抽取
- inspiration.ts 文件拆分
- workbenchStore 新增 inspirationFields 状态
- 表单三种状态的视觉实现
- 快捷模板下拉菜单
- 删除 InspirationChatPanel、InspirationPreview
- 删除表单/对话模式切换逻辑

## 风险

- 三栏布局在小屏设备体验较差 → 考虑后续添加左导航折叠
- Agent tool call 的可靠性依赖后端 prompt 质量 → 先实现基本 tool，后续迭代优化
