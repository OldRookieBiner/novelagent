# AgentChatPanel store 订阅优化

**Labels**: `refactor`, `frontend`, `performance`

## 背景

[AgentChatPanel.tsx:528-543](../../frontend/src/components/workbench/AgentChatPanel.tsx) 当前用四段订阅 `useWorkbenchStore` 来取状态：

```typescript
const {
  setActiveTab,
  aiMessages,
  // ... 十余项
  incrementKnowledgeVersion,
} = useWorkbenchStore()        // ← (1) 无 selector：订阅整个 store

const phase = useWorkbenchStore((s) => s.phase)                              // (2)
const selectedChapterNumber = useWorkbenchStore((s) => s.selectedChapterNumber)  // (3)
const { setActiveConversationId } = useWorkbenchStore()                      // (4)
```

第 (1) 段没有 selector，**等同于订阅整个 store**——任何字段变更都会让 AgentChatPanel rerender，包括 `knowledgeVersion`、`isAgentBusy` 这些组件本身根本不关心的字段（虽然有些字段它确实关心，但 selector 缺失让所有变更都触发 rerender）。第 (2)(3)(4) 三段再单独订阅就显得多余。

这是组件**已有的反模式**，不是 commit 5a9356c 引入的。但该 commit 又加了一行 (3) `selectedChapterNumber` 订阅，让"订阅碎片化"问题更显眼。

## 影响范围

- AgentChatPanel 是工作台主用界面，写作时每秒可能因 SSE 流更新触发数十次 store 变更（agentWarnings、knowledgeVersion、aiMessages 各自独立 set）
- 实测 rerender 频率偏高，长会话场景下 React DevTools Profiler 应能看到 unnecessary renders

## 方案选项

### 方案 A：拆为多个细粒度 selector（推荐）

把第 (1) 段拆开，每个字段一个 selector：

```typescript
const setActiveTab = useWorkbenchStore((s) => s.setActiveTab)
const aiMessages = useWorkbenchStore((s) => s.aiMessages)
const addAiMessage = useWorkbenchStore((s) => s.addAiMessage)
// ...
```

action 类引用是稳定的，会被 zustand 自动 memo；state 类引用按字段精确订阅。

### 方案 B：聚合 selector + shallow 比较

```typescript
import { shallow } from 'zustand/shallow'

const { setActiveTab, aiMessages, /* ... */ } = useWorkbenchStore(
  (s) => ({
    setActiveTab: s.setActiveTab,
    aiMessages: s.aiMessages,
    // ...
  }),
  shallow,
)
```

写法接近现状，迁移成本低；但 selector 函数每次重建，对热路径不如方案 A。

## 验收

- DevTools Profiler 下，发送一条 Agent 消息整个 SSE 流过程中 AgentChatPanel 的 rerender 次数显著下降
- `npm run test:run` 全绿（含 AgentChatPanel 已有测试 / 新增 store 订阅断言）
- 行为无回归：消息流、impact dialog、警告浮层、章节选中传递都正常

## 关联

- 上游 commit: 5a9356c (fix(workflow): pass current_chapter_number to agent...)
- 触发审查的位置: AgentChatPanel.tsx:540-543
