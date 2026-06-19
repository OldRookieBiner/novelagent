# Agent 聊天窗口增强设计

日期：2026-06-19
范围：仅前端（`frontend/src/components/workbench/AgentChatPanel.tsx` + 同目录新增 `MessageAnchorRail.tsx` + 类型扩展 + 测试）。无后端改动。

---

## 背景

7 项独立但互补的用户体验痛点，覆盖：选中可见性、输入体验、复制能力、耗时反馈、布局对齐、长会话导航。

## 总体目标

使 Agent 聊天窗口在长对话场景下达到与主流商用产品（deepseek、ChatGPT、reasonix）相当的可用性，同时控制本次改动不跨功能边界、不产生技术债、不在原生浏览器/窄面板/异常流程中抛错。

## 需求分解与设计

### 1. 用户气泡背景色调整

**问题**：当前 `bg-primary text-primary-foreground` 为近黑底 + 白字，浏览器默认选区（淡蓝半透明）叠加后对比度极低，无法判断选中范围。

**方案**：

- `bg-secondary text-secondary-foreground`（`#eef2f7` 浅灰蓝底 + 深字），与全局 design token 一致。
- 追加 `selection:bg-primary/25 selection:text-foreground`，保证选区在任意操作系统/主题下均有明显对比。
- 圆角、字号、max-w-[80%] 等其它样式不变。

**A11y**：不影响已存在的 `aria-label` 和 role。
**迁移检查**：需对比新旧气泡在长文本自动 wrap 和多行换行场景下的截图，确保视觉宽度一致。

### 2. ↑/↓ 切换历史输入

**行为对齐**：Bash readline / ChatGPT。

**交互细则**：

- 输入框 `onKeyDown` 中对 ↑/↓ 做条件拦截。
- ↑ 触发前提：`selectionStart` 之前的字符串中没有 `\n`（即光标在第一行）。
- ↓ 触发前提：`selectionStart` 之后的字符串中没有 `\n`（即光标在最后一行）。
- 上述检查前先判断 `e.nativeEvent.isComposing` —— composition 期间（中文输入法选词）不触发历史导航，避免误触。此项同样补到 Enter 发送逻辑中（已存在的边界 bug，顺手修复）。
- 历史来源：`aiMessages.filter(m => m.role === 'user').map(m => m.content)`（按时间升序）。
- 状态：`historyIndexRef = useRef<number>(-1)`、`draftRef = useRef<string>('')`。
| 状态 | 含义 |
|------|------|
| `-1` | 草稿态，当前输入为自由输入 |
| `0..n-1` | 历史态，`input` 已被替换为历史消息内容 |
- 第一次按 ↑（index === -1）时把当前 `input` 暂存到 `draftRef`。
- 按 ↑：`index = Math.min(n-1, Math.max(0, index+1))`
- 按 ↓：`index = Math.min(n-1, index-1)；若 index < 0 则恢复 draftRef 并复位为 -1`
- 达到尾部后不循环（↑ 到 0 后保持 0，不会回绕）。
- 重置时机统一封装为 `resetInputHistory()` 函数（避免 4 处散落）：内部执行 `historyIndexRef.current = -1; draftRef.current = ''`。调用方包括 `handleSend` 入口、`handleSwitchConversation`、`handleNewConversation`、加载历史消息的 `useEffect`。
- **0 条历史时 ↑/↓ 无操作**（不能报错、不能清空 input、不能修改文本）。

**闭包安全**：函数中用 ref 或直接从 `aiMessages` 派生历史数组，避免 future useCallback 依赖遗漏。

**边界**：连续快速 ↑↓ 导致多次 setState 在 React 18 batch 下安全。

### 3. 用户气泡复制按钮

- 用户气泡的外层结构改为 `<div className="group flex flex-col items-end">`（外层不限宽），气泡本身保留 `max-w-[80%]`，复制按钮位于气泡下方右对齐。这样短消息时按钮紧贴气泡右下角，长消息时按钮跟随 80% 宽度边界。
- 复制按钮使用 `lucide-react` 的 `Copy` / `Check`（需新增到现有 import 行），尺寸 `h-3 w-3`。
- 默认 `opacity-0 group-hover:opacity-100`，复制后图标切换 `Check` 1.5s。
- 复制内容：`msg.content`。
- Clipboard：`navigator.clipboard.writeText(content).catch(() => fallbackExecCommand(content))`，显式 `.catch` 吞 reject，防止 `unhandledrejection`。fallback `execCommand('copy')` 基于临时 `textarea` 元素 + `select()`。
- 容错情景：navigator.clipboard 在 Firefox 非 HTTPS 可为 undefined、`writeText` 返回 promise reject、`execCommand` 返回 false —— 均不做 toast 也不抛错，仅按钮不切换图标。
- A11y：CopyButton 接收 `ariaLabel` prop（驼峰，避免与 React JSX 中的标准 `aria-label` attribute 混用），内部渲染为 `aria-label={ariaLabel || '复制'}`。用户气泡传 `ariaLabel="复制用户消息"`、工具条传 `ariaLabel="复制回复内容"`。

### 4&5. Agent 答复工具条（耗时 + 复制按钮）

两功能共享"toolbar"行，渲染在 assistant 消息内容下方。

**时间语义**：从 **用户点发送** 到 **onAgentDone / onError / abort 落地** 的总耗时（包含网络 + busy lock + 生成 + SSE 传输）。这是用户感知的最直接指标，且不需要后端配合。

**数据流**：

- `handleSend` 中创建 assistant 消息时存储 `startedAt`（`Date.now()`）。
- 以下三个出口统一计时写回（`updateAiMessage`）：
  1. `onAgentDone` —— 先 `flushTextBuffer()` 确保文本已刷新，再写 `durationMs`（`(m) => ({ ...m, durationMs })`）。
  2. `onError` —— 同样写入 `durationMs`（显示"错误/用时 X.Xs"）。
  3. `finally` 块中当 `err?.name !== 'AbortError'` 时——即 abort 路径也写 `durationMs`，显示"已停止 / 用时 X.Xs"。
- 历史消息（`fetchConversation` 加载的）不含 `durationMs`、`startedAt`，渲染时长 null-check，不显示"未知"。

**Flush 竞态保护**：`flushTextBuffer()` 用 `updateAiMessage(id, m => ({ ...m, ... }))`，它扩展对象而非替换整个 state，所以即使 `onAgentDone` 先运行写入了 `durationMs`，后续的 `flushTextBuffer` 调用会保留该字段。但 spec 约定：**写 `durationMs` 前必须 flush**，不依赖函数式更新保序。

**渲染**：

- `<div className="flex items-center gap-2 text-[10px] text-muted-foreground">`
- 复制按钮 `opacity-100`（始终可见，不与 anchor 列冲突），居左。
- 耗时紧随其后，居中。
- 复制内容 = `msg.content`（markdown 源码）；与用户气泡相同的 clipboard 逻辑。
- 仅在**消息已完成、且有内容**时显示工具条。流式中的 `ThinkingIndicator` 和工具条互斥。

**消息气泡组**：将每条消息包裹在 `<div className="group">` 内，以便 hover 和工具条定位共享。

### 6. 发送按钮垂直居中

- inputRows >= 2 → `self-end`（保持多行时贴底）。
- inputRows === 1 → `self-center`（单行时与文本框垂直中线对齐）。
- 按钮 height 固定（保持 36px line-height），不随行数拉伸。

### 7. 右侧消息锚点列（快速跳转）

**组件**：`MessageAnchorRail.tsx`（新文件），在 `AgentChatPanel.tsx` 中引入。

**Props**：

```ts
interface MessageAnchorRailProps {
  userMessages: AiMessage[]
  activeId: string | null
  onJump: (id: string) => void
  scrollContainerRef: React.RefObject<HTMLDivElement | null>
}
```

**视觉**：

- 绝对定位在消息滚动区（`scrollRef`）内部右边缘：`position: absolute right-[2px] top-0 bottom-0 flex flex-col justify-center items-center gap-1.5 w-[12px]`，`pointer-events-none` 最外层 + `pointer-events-auto` 按钮层。
- 每条 user 消息对应一根横线按钮：`w-[8px] h-[2px] rounded-full bg-muted-foreground/30 hover:bg-muted-foreground/60`，平滑 `transition-all duration-150`。
- activeId 对应横线：`w-[12px] bg-primary` + 过渡动画。
- 当 `userMessages.length < 2` 时不渲染。

**交互**：

- 横线排列方式：**均匀分布在容器高度上**（按总条数均分），水平居中。
- 点击横线：从 `userMessageRefs Map` 中找到对应 DOM 节点，`scrollContainerRef.current.scrollTop = el.offsetTop - container.offsetTop - 12`（留 12px 呼吸空间）。不依赖 `scrollIntoView`（避免 Safari 兼容差异和 body 滚动干扰）。
- 跳转后在该消息上短暂添加 `animate-pulse` 或 ring 样式 1s。
- 浮层：鼠标进入锚点列区域（container `onMouseEnter`）展示浮层，`onMouseLeave` 延迟 200ms 关闭。
  - 浮层绝对定位在容器右侧 `right: 100% + 8px`，`position: absolute right-[calc(100%+8px)] top-1/2 -translate-y-1/2`。
  - `max-w-[280px]`，`z-50`，白色背景 + 阴影 + 圆角。
  - 标题列表：每条 user 消息一行，点击项触发 `onJump` + 关闭浮层。
  - 标题取 `content` 前 15 个 grapheme cluster（用 `Array.from(str).slice(0, 15).join('')`），再 `replace(/\s+/g, ' ').trim()` 去掉多余的空白。超过 15 字加 `…`。纯空白或空串使用 `"(空消息)"` 占位。

**当前消息定位**（activeId 计算）：

- 浮层不可见时仍持续计算，因为 active 锚点高亮持续可见。
- 监听 `scrollRef` 的 `scroll` 事件，用 `requestAnimationFrame` 节流。每次事件后 `cancelAnimationFrame` 旧 id 再提交新的，避免积压。
- 逐条判断 user 消息对应 DOM 的 `offsetTop`（相对 `scrollRef`），找到最接近视口顶部 + 80px（给 header 留空间）的 user 消息 id，设为 `activeId`。若无任意 user 消息在可视区内，`activeId = null`（不高亮）。
- `aiMessages` 删除/重新构造（setAiMessages）时，`userMessageRefs` Map 保留旧 DOM 不变。需要在 useEffect cleanup 中 `userMessageRefs.current.clear()`，或使用回调 ref 的 unmount 分支自动删除。

**A11y**：每根横线 `aria-label="跳转到第{n}条消息"`；浮层 `role="tooltip"`。
**窄面板保护**：`z-50` 避免面板拖拽时浮层覆盖内容。面板宽度变化时浮层重新布局（position: right based，不受影响）。

---

## 数据结构变更

`frontend/src/stores/workbenchStore.ts`：

```ts
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  segments: AiMessageSegment[]
  timestamp: number
  // 新增（仅前端内存态，不持久化）
  startedAt?: number
  durationMs?: number
}
```

`fetchConversation` 返回的历史消息不会含这两个字段，渲染时 `durationMs` 为 `undefined`，直接跳过即可。后端 schema/migration 不变。

---

## 受影响文件

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `AgentChatPanel.tsx` | 主更改 | 1-7 项全部在此新增/修改 |
| `MessageAnchorRail.tsx` | 新增 | 锚点列独立组件 |
| `workbenchStore.ts` | 类型扩展 | `AiMessage` 加 `startedAt?` / `durationMs?` |
| 测试文件（详见测试节） | 新增 | |

---

## 测试

### 完整覆盖（自动化）

**文件** `frontend/src/lib/__tests__/truncateTitle.test.ts`
- 空串 → `"(空消息)"`
- 纯空白 → `"(空消息)"`
- 全英文 14/15/16 字边界
- 中文 15/16 字边界
- emoji 组合字符按 grapheme 长度
- 含换行的截断
- 截断后加 `…`

**文件** `frontend/src/components/workbench/__tests__/MessageAnchorRail.test.tsx`
- 0 / 1 条不渲染
- 锚点数量与 userMessages 一致
- 点击锚点调用 `onJump` 并传入正确 id
- `activeId` 对应锚点高亮样式
- 非 active 锚点无高亮
- mouseenter 容器后浮层显现
- 点击浮层标题项触发 `onJump` 并关闭浮层

### 推迟覆盖（手动验收 + tsc）

- 历史导航 ↑/↓
- 用户气泡复制 / 工具条复制
- duration 三出口（done/error/abort）写入

**取舍原因**：当前 AgentChatPanel 与 `useWorkbenchStore` / `agentApi.sendAgentMessage` / `navigator.clipboard` 强耦合，组件无 props 注入入口。要写这三类集成测试，需要：
1. mock SSE 端点（`fetch` + ReadableStream）
2. 注入 zustand store 测试 fixture
3. mock clipboard API
4. 用 user-event 模拟键盘交互 + composition

落地后单测覆盖度提升有限，反而引入约 200 行 mock 基础设施 + fragile snapshot；本次"小幅 UX 改动"投入产出失衡。

**短期保障**：
- `tsc --noEmit` 兜底类型一致性
- Task 8 的 18 项手动验收清单覆盖三类功能的所有分支（包括 abort 路径、composition 拦截、clipboard fallback）

**长期清债**：未来如果要继续在 AgentChatPanel 上加功能，先做一次组件解耦重构 —— 把 SSE 副作用抽到 `useAgentChat` hook，组件改为接 props 的展示组件，届时统一补充集成测试。本次设计在风险表中保留这条作为已知技术债。

---

## 风险与取舍

| 风险 | 评级 | 缓解措施 |
|------|------|----------|
| 锚点列 DOM Map 泄露 | P1 | ref callback unmount 分支 `delete(id)`；组件 cleanup 调 `clear()` |
| 中文输入 ↑ 误触发历史 | P1 | `e.nativeEvent.isComposing` 拦截；顺手补到 Enter 发送 |
| clipboard API reject 未 catch | P1 | `.catch(fallback)` 显式链，不依赖浏览器默认行为 |
| duration flush 竞态 | P1 | 写 duration 前必须 flush；函数式 update 保留未覆盖字段 |
| abort 路径无耗时 | P2 | `finally` 块差异捕获 AbortError/non-AbortError，都写 duration |
| scroll 监听 rAF 积压 | P2 | `cancelAnimationFrame` 旧 id 再提交新 id |
| 浮层溢出窄面板 | P2 | `max-w-[280px]` + `text-wrap: balance` |
| 面板拖拽时锚点列布局抖动 | P2 | `right: 4px` 基于容器，与拖拽无关 |
| 0 条历史 ↑ 误操作 | P2 | 显式 `if (userMsgs.length === 0) return` |
| truncateTitle grapheme 安全 | P2 | `Array.from(str).slice(0, 15)` 而非 `.slice(0, 15)` |
| AgentChatPanel 集成测试缺失 | 已知债 | 历史导航/复制/duration 仅靠 tsc + 手动验收；待组件解耦重构后补充 |
| 前端 build 报错（新增 import） | P2 | 确认 `lucide-react` 已有 Copy/Check 图标（已在内联工具函数中用过） |
| Safari scrollTop 精度 | P3 | 跳转用 `offsetTop - container.offsetTop`（不依赖 scrollIntoView）；activeId 判定用 `getBoundingClientRect`，两 API 在无 transform 容器内一致 |
| 锚点列遮挡消息右边缘 | P1 | 消息容器右 padding 改为 `pr-6`（让出 24px 空间） |
| 锚点列 12px 热区窄 | P2 | 容器 `pl-2 + w-[20px]`（视觉仍 12px，hover 热区扩到 20px）；按钮 `pointer-events-auto`，容器 `pointer-events-none` |
| CopyButton 复用顺序依赖 | P2 | Task 4 复用 Task 2 定义的 CopyButton；plan 显式标注依赖，subagent 模式按序执行 |

**不在本次范围**：
- 后端 `agent_messages` 表增 `duration_ms` 列
- token 统计 / 价格估算
- 锚点列对 assistant 消息的索引
- 移动端适配
