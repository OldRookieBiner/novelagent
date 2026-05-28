# 智能体模型选择 & 聊天窗口合并设计

日期：2026-05-28

## 背景

两个用户体验问题：
1. AgentChatPanel 无法选择模型，始终使用用户默认配置
2. 写作页面存在两个聊天窗口（右侧 AgentChatPanel + 孵化阶段中栏 InspirationChat），功能重叠，用户困惑

## 设计决策

### 1. 标签页重排

当前顺序：写作 → 知识库 → 结构 → 追踪
新顺序：知识库 → 结构 → 写作 → 追踪

理由：创作流程为「孵化(知识库) → 结构 → 写作 → 修订(追踪)」，标签顺序应对齐流程。

变更：
- `TabNavigation.tsx` TABS 数组顺序调整
- 默认激活标签改为 `knowledge`
- 各阶段默认标签映射：孵化→knowledge，结构→structure，写作→writing，修订→tracking

### 2. 写作标签阶段引导

WritingTab 在孵化/结构阶段时，顶部显示引导卡片：
- 孵化阶段：「当前处于创意孵化阶段，请先在右侧智能体中完善知识库，完成后切换到结构设计阶段」
- 结构阶段：「请完成结构设计后再开始写作，你可以在右侧智能体中讨论情节安排」

引导卡片可关闭（useState 控制，当次会话有效）。

WritingTab 移除孵化阶段对 InspirationChat 的分支，所有阶段统一渲染 WritingPanel。

### 3. 合并聊天窗口

删除 InspirationChat：
- 删除 `frontend/src/components/workbench/creation/InspirationChat.tsx`
- WritingTab.tsx 移除 InspirationChat 引用，统一渲染 WritingPanel

AgentChatPanel 增强：
- 孵化阶段使用 INCUBATION_TOOLS（后端已支持，无需修改）
- Header 区域增加阶段标签
- 空状态文案按阶段区分：孵化阶段为"描述你的小说创意，智能体将帮你完善世界观、角色和风格"

后端无需修改。`/agent/chat` 已按 phase 分配工具集。

### 4. AgentChatPanel 模型选择器

UI 位置：AgentChatPanel header 区域，标题和折叠按钮之间。

交互：
- 紧凑的 Select 下拉，默认显示"默认模型"
- 列表来自 `/api/model_configs`（仅 is_enabled 的配置）
- 选择后后续消息携带 model_config_id
- 折叠状态下不显示选择器

数据流：
- 组件挂载时请求模型列表，存组件 state
- selectedModelConfigId 存组件 state，写入 fetch body
- 发送消息走 agentApi.ts 的 sendAgentMessage（替代当前直接 fetch）

### 5. AgentChatPanel 重构为使用 agentApi

当前 AgentChatPanel 直接 fetch + 手动解析 SSE。重构为使用 `sendAgentMessage`：
- 统一 SSE 事件处理
- 天然支持 modelConfigId、history 等参数
- 减少 AgentChatPanel 内部代码量

## 涉及文件

| 文件 | 变更 |
|------|------|
| `frontend/src/components/workbench/TabNavigation.tsx` | 标签顺序调整 |
| `frontend/src/components/workbench/creation/WritingTab.tsx` | 移除 InspirationChat 分支，加引导卡片 |
| `frontend/src/components/workbench/creation/InspirationChat.tsx` | 删除 |
| `frontend/src/components/workbench/AgentChatPanel.tsx` | 模型选择器、阶段标签、重构为 agentApi、空状态文案 |
| `frontend/src/stores/workbenchStore.ts` | 默认 activeTab 改为 knowledge |
| 后端 | 无变更 |

## 不涉及

- 后端 API 端点无修改
- 其他标签页内容不变
- 工作流（LangGraph）不变
