# AI 搭档模式 + 工作台重构设计

> 日期：2026-05-22
> 状态：草案
> 范围：前端布局重构 + Agent 模式新增

---

## 1. 背景与目标

### 当前问题

1. **灵感面板层级不合理** — 灵感是创意发散阶段，却塞在「规划」标签的子菜单里，视觉空间受限
2. **大纲页面布局低效** — `max-w-3xl` 限制浪费宽屏空间，AI 分析面板是假数据
3. **AI 介入方式被动** — 现有 AI 功能是「点按钮触发」，用户无法用自然语言引导 AI 修改
4. **工作流模式线性** — LangGraph 线性节点流程，用户必须按步骤操作，无法跨模块联动

### 目标

1. 调整标签结构：灵感独立，规划更名设定
2. 大纲页面采用双栏自适应布局
3. 新增 AI 搭档模式：常驻右侧聊天栏，全流程覆盖
4. 工作流模式与 Agent 模式并存，逐步融合

---

## 2. 标签结构调整

### 变更

| 变更项 | 之前 | 之后 |
|--------|------|------|
| 灵感 | 规划标签内子菜单（`PlanningMenuItem`） | 独立标签页（`WorkbenchTab`） |
| 规划 | 标签名「规划」 | 更名「设定」，侧边栏：大纲/人物/关系 |
| 标签数 | 3（规划/章节大纲/章节正文） | 4（灵感/设定/章节大纲/章节正文） |

### 类型变更

```typescript
// 之前
type WorkbenchTab = 'planning' | 'chapter_outlines' | 'writing'
type PlanningMenuItem = 'inspiration' | 'outline' | 'characters' | 'relations'

// 之后
type WorkbenchTab = 'inspiration' | 'settings' | 'chapter_outlines' | 'writing'
type SettingsMenuItem = 'outline' | 'characters' | 'relations'
```

### 侧边栏行为

- 灵感标签页：无侧边栏，全宽展示 InspirationPanel
- 设定标签页：显示设定侧边栏（大纲/人物/关系），保持现有折叠功能
- 章节大纲/章节正文：无侧边栏，与现有行为一致

### 完整布局（设定标签页为例）

设定标签页下左右三栏并存：

```
┌──────────────────────────────────────────────────────────────┐
│ 💡灵感 │ ⚙️设定 │ 📖章节大纲 │ ✏️章节正文                     │
├────┬─────────────────────────────────┬───────────────────────┤
│设定│                                 │                       │
│侧边│     主内容区                     │   🤖 AI 搭档          │
│栏  │  （大纲/人物/关系面板）           │   （常驻聊天侧栏）      │
│120 │                                 │   340px               │
└────┴─────────────────────────────────┴───────────────────────┘
```

其他标签页时，设定侧边栏消失，主内容区自动扩展。AI 侧栏始终在。

---

## 3. 整体布局架构

### 核心布局：左工作区 + 右 AI 侧栏

```
┌─────────────────────────────────────────────────────┐
│ Header（全局）                                       │
├─────────────────────────────────────────────────────┤
│ 项目 Header（标题 + 进度条）                          │
├─────────────────────────────────────────────────────┤
│ 💡灵感 │ ⚙️设定 │ 📖章节大纲 │ ✏️章节正文            │
├──────────────────────────────┬──────────────────────┤
│                              │                      │
│     工作区（标签页内容）       │   🤖 AI 搭档         │
│                              │   （常驻聊天侧栏）     │
│     切换标签不影响右侧         │   可折叠/展开         │
│                              │                      │
├──────────────────────────────┴──────────────────────┤
```

### AI 侧栏规格

| 属性 | 值 |
|------|------|
| 默认宽度 | 340px |
| 折叠后宽度 | 40px（仅显示图标+竖排文字） |
| 折叠按钮 | 侧栏顶部 header 右侧 |
| 主题色 | 深色主题（#0f172a 背景），与工作区白色形成视觉区分 |
| 位置 | 固定右侧，不随标签切换变化 |

### AI 侧栏内部结构

```
┌──────────────────────┐
│ 🤖 AI 搭档    [⟫]   │ ← header：标题 + 折叠按钮
├──────────────────────┤
│                      │
│  聊天消息区           │ ← 主要区域
│  - AI 回复（左对齐）  │
│  - 用户消息（右对齐）  │
│  - 操作步骤卡片       │
│                      │
├──────────────────────┤
│ [说说你的想法...] 发送│ ← 输入区
└──────────────────────┘
```

### 折叠状态

```
┌──┐
│⟪ │
│🤖│
│AI│
│搭│
│档│
└──┘
```

---

## 4. 大纲页面重构

### 布局：双栏自适应

移除 `max-w-3xl` 限制，改为左右双栏布局：

- **左栏**：基本信息（标题、章节数、概述）
- **右栏**：情节节点列表（可拖拽排序）

### 改进项

| 改进 | 说明 |
|------|------|
| 双栏布局 | 充分利用宽屏，基本信息与情节节点并排 |
| 情节节点可拖拽 | 使用 `@dnd-kit/core` + `@dnd-kit/sortable` 实现拖拽排序（新增依赖） |
| 移除右侧 AI 分析面板 | 原来的 AI 分析面板（假数据）删除，AI 能力由右侧 AI 搭档统一提供 |
| 空状态 | 大纲为空时显示引导文案：「在右侧 AI 搭档中描述你的故事想法，或点击设定侧边栏的大纲手动填写」 |
| 确认按钮 | 移至双栏底部居中，与现有位置一致（`text-center`） |

### AI 分析面板的处理

原 OutlinePanel 右侧的 AI 分析面板（`handleAnalyze`、`analysisResult` 等）全部删除。AI 介入统一由右侧 AI 搭档侧栏提供，用户在侧栏中说「帮我分析一下大纲」，AI 搭档自动调用分析 tool 并在聊天中展示结果。

---

## 5. AI 搭档模式

### 定位

AI 搭档是项目级别的常驻协作伙伴，不属于任何子页面。用户通过自然语言描述想法，AI 理解上下文后自主判断需要修改的模块并执行。

### 能力范围：全流程

| 模块 | AI 可读 | AI 可写 | 说明 |
|------|---------|---------|------|
| 大纲 | ✓ | ✓ | 修改标题/概述/情节节点 |
| 角色 | ✓ | ✓ | 修改角色设定/新增角色 |
| 关系 | ✓ | ✓ | 修改人物关系 |
| 章节大纲 | ✓ | ✓ | 生成/修改章节大纲 |
| 章节正文 | ✓ | ✓ | 写/重写章节内容 |
| 审核 | ✓ | ✓ | 审核+根据意见重写 |

### 交互模式

**用户 → AI**：自然语言描述需求

- 「主角的成长线太平了，让它更有层次」
- 「第3章的节奏太慢了，帮我调整」
- 「增加一个反派角色，跟主角有宿命纠葛」

**AI → 用户**：操作步骤 + 结果反馈

1. AI 在聊天中列出即将执行的操作步骤
2. 逐步执行，每步完成标记 ✓，进行中标记 ⏳
3. 执行完成后，左侧工作区对应区域标记「🤖 AI 已更新」
4. 用户可切换到对应标签页查看详情

### AI 修改的可见性

| 机制 | 说明 |
|------|------|
| 聊天中操作卡片 | 列出每步操作的类型和目标 |
| 左侧标记 | 被修改的区域显示「🤖 AI 已更新」徽标（通过 SSE 事件 `ai_update` 推送，前端标记后 5 分钟自动消失） |

### 上下文注入

每次用户发送消息时，后端自动将以下上下文注入 Agent：

1. **项目基础信息**：项目 ID、名称、当前工作流阶段
2. **当前视图上下文**：用户正在查看的标签页和子面板（`activeTab` + `activeMenuItem`）
3. **模块摘要**：大纲概要、角色列表（名称+一句话描述）、章节列表（标题+状态）
4. **聊天历史**：当前会话的最近 N 轮对话

上下文以 system message 形式注入，不占用用户可见的聊天空间。

### 并发控制

工作流模式和 Agent 模式**不允许同时操作同一项目**：

- 当工作流正在运行时，Agent 侧栏输入区禁用，显示提示「工作流运行中，请等待完成或取消后再与 AI 搭档对话」
- 当 Agent 正在执行 tool 调用时，工作流运行按钮禁用
- 通过数据库行级锁（`project` 表加 `is_busy` 字段）实现互斥

### 上下文感知

AI 知道用户当前查看的标签页和子面板。聊天中可以说「你现在看到的那段」，AI 能理解上下文。

---

## 6. 双模式并存策略

### 工作流模式（现有）

保持不变。点按钮跑流程，step/hybrid/auto 模式继续可用。

### Agent 模式（新增）

右侧 AI 侧栏，聊天驱动全流程。

### 两者关系

- 数据完全互通：工作流模式写入的数据，Agent 模式可读可改；反之亦然
- 不冲突：两者使用不同的 LangGraph 图实例和 API 端点
- 互斥运行：同一项目同一时间只能有一个模式在执行（见并发控制）
- 用户可随时切换：不需要退出或刷新

### 演进路径

```
阶段1：并存开发
├── 工作流模式保持不变
├── Agent 模式作为右侧栏上线
└── 观察用户行为

阶段2：验证+补能力
├── Agent 做不到的场景，补 tools
├── 工作流常用操作封装为 Agent 快捷指令
└── 两侧数据互通完善

阶段3：融合或替代
├── Agent 覆盖率足够 → 工作流降级为「快捷操作」
├── 两者各有场景 → 保留双入口，共享底层
└── 用数据说话
```

---

## 7. 后端架构

### 技术栈

**无变化**，仍然基于 LangGraph。两种模式共享同一框架，只是图的构建方式不同：

```
LangGraph
├── 工作流图（现有）
│   └── StateGraph + 固定节点 + 条件路由
└── Agent 图（新增）
    └── ReAct Agent + tools（封装现有节点能力）
```

| | 工作流模式 | Agent 模式 |
|---|---|---|
| 图结构 | 预定义线性图 | 动态 ReAct 图 |
| LangGraph API | `StateGraph` + 固定边 | `create_react_agent` + tools |
| 节点 | 现有的生成/审核节点 | 现有节点封装为 tools |
| Checkpoint | ✓ 有 | ✓ 有（LangGraph 原生） |
| Streaming | ✓ SSE | ✓ SSE（LangGraph 原生） |

### Agent 端点

新增 API 端点供 Agent 模式使用：

```
POST /api/projects/{id}/agent/chat    # 发送消息，SSE 流式返回
GET  /api/projects/{id}/agent/history # 获取聊天历史
```

### Agent Tool 设计

将现有 LangGraph 节点能力封装为 Agent 可调用的 tools：

| Tool 名称 | 对应现有节点/功能 | 说明 |
|-----------|------------------|------|
| `read_outline` | outline API get | 读取大纲 |
| `update_outline` | outline API update | 修改大纲 |
| `read_characters` | characters API list | 读取角色列表 |
| `update_character` | characters API update | 修改角色 |
| `create_character` | characters API create | 新增角色 |
| `read_relations` | relations API | 读取人物关系 |
| `update_relations` | relations API | 修改关系 |
| `read_chapter_outlines` | chapters API list | 读取章节大纲 |
| `update_chapter_outline` | chapters API update | 修改章节大纲 |
| `generate_chapter_content` | chapter generation node | 生成章节正文 |
| `review_chapter` | review node | 审核章节 |
| `rewrite_chapter` | rewrite node | 重写章节 |

### Agent 编排

- 使用 LangGraph 的 `create_react_agent` 构建 ReAct 循环
- Agent 接收用户消息 + 项目上下文（见上下文注入），LLM 决定调用哪些 tools
- 支持 SSE 流式输出，事件格式复用现有 `sse_events.py` 基础，新增以下事件类型：

| SSE 事件 | 说明 |
|----------|------|
| `agent_text` | AI 文本回复（流式 chunk） |
| `agent_tool_start` | Agent 开始调用某个 tool，含 tool 名称和参数 |
| `agent_tool_result` | Tool 调用结果，含成功/失败和返回数据 |
| `agent_done` | Agent 本轮思考完成 |
| `ai_update` | 通知前端某个模块被修改，含模块名和修改摘要（用于标记「🤖 AI 已更新」） |

- 支持多轮 tool 调用（一次用户消息可能触发多步操作）

### Agent State

Agent 图使用独立的 State 定义，与现有 NovelState 分离：

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]       # 对话历史
    project_id: int                    # 项目 ID
    project_context: dict              # 项目上下文（大纲/角色/章节摘要）
    current_view: dict                 # 用户当前视图（tab + 子面板）
    tool_results: list[dict]           # 本轮 tool 调用结果汇总
```

### 与现有工作流的关系

- 共享数据模型、数据库、LLM 服务、Prompt 体系
- 共享 LangGraph 节点代码（现有节点封装为 Agent tools）
- Agent 模式使用 LangGraph ReAct Agent，而非绕过框架
- 两套图共享 checkpoint 和 streaming 基础设施
- 两套入口互不干扰

---

## 8. 前端改动清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `components/workbench/AICompanionSidebar.tsx` | AI 搭档侧栏组件 |
| `components/workbench/AICompanionChat.tsx` | 聊天消息区组件 |
| `components/workbench/AICompanionInput.tsx` | 输入区组件 |
| `components/workbench/AIActionCard.tsx` | AI 操作步骤卡片 |
| `lib/agentApi.ts` | Agent API 客户端 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `types/workbench.ts` | `WorkbenchTab` 改为 `'inspiration' | 'settings' | 'chapter_outlines' | 'writing'`，`PlanningMenuItem` 改为 `SettingsMenuItem`（`'outline' | 'characters' | 'relations'`），`PLANNING_MENUS` 常量更名 `SETTINGS_MENUS` |
| `components/workbench/TabNavigation.tsx` | 4 个标签：灵感/设定/章节大纲/章节正文 |
| `components/workbench/WorkbenchSidebar.tsx` | 仅在设定标签显示（`activeTab === 'settings'`），菜单项改为大纲/人物/关系，引用 `SETTINGS_MENUS` |
| `components/workbench/WorkbenchLayout.tsx` | 增加 AI 侧栏区域 |
| `pages/ProjectWorkbench.tsx` | 调整路由分发逻辑 |
| `stores/workbenchStore.ts` | 新增 AI 侧栏状态（展开/折叠/聊天消息） |
| `components/workbench/creation/OutlinePanel.tsx` | 双栏布局 + 移除 AI 分析面板 + 情节节点拖拽 |
| `components/workbench/planning/InspirationPanel.tsx` | 适配独立标签页全宽布局 |

### 删除

| 内容 | 说明 |
|------|------|
| OutlinePanel 右侧 AI 分析面板 | `handleAnalyze`、`analysisResult`、`aiPanelCollapsed`、`rightCollapsed` 等状态和 UI |

---

## 9. 不在本设计范围内

- Agent 具体的 prompt 设计和 system prompt
- Agent 聊天历史的持久化方案（MVP 阶段仅内存存储，刷新后丢失）
- 多轮对话的上下文窗口管理策略
- 工作流模式的进一步优化
- 移动端适配
- Agent 操作回滚/版本控制（MVP 阶段用户可通过手动编辑恢复，后续版本实现）
