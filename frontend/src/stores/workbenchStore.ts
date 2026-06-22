// workbenchStore.ts — Creation agent workbench state management

import { create } from 'zustand'

/** Workbench tab */
export type WorkbenchTab = 'writing' | 'knowledge' | 'structure' | 'tracking'

/** Creation phase */
export type Phase = 'incubation' | 'structure' | 'writing' | 'revision'

/** 工具调用状态：running 运行中、done 完成、error 失败、aborted 用户取消 */
export type ToolCallStatus = 'running' | 'done' | 'error' | 'aborted'

/** tool_call segment 的 data 形状（运行时唯一使用的工具调用表达） */
export interface ToolCallSegmentData {
  tool: string
  status: ToolCallStatus
  args?: Record<string, unknown>
  result?: Record<string, unknown>
  /** 运行时附加属性允许扩展（与 Record<string, unknown> 兼容） */
  [key: string]: unknown
}

/**
 * AI message content segment
 *
 * 说明：
 * - 运行时新生成的工具调用段统一为 `tool_call`（含 status 状态机）。
 * - `tool_start` / `tool_result` 仅保留用于解析历史 DB 行；进入前端内存前会被
 *   `normalizeLegacySegments` 归一化为 `tool_call`，渲染层不再消费这两种类型。
 */
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview' | 'warning' | 'tool_start' | 'tool_result' | 'tool_call' | 'progress'
  content: string
  data?: Record<string, unknown>
}

/** AI sidebar message */
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  segments: AiMessageSegment[]
  timestamp: number
  // 仅前端内存态，不持久化到后端
  startedAt?: number
  durationMs?: number
}

/** Impact assessment report from a propose_* tool */
export interface ImpactReport {
  change_id: number
  status: string
  impact_level: string
  impact_label: string
  affected_chapters: number
  affected_paragraphs: number
  detail: string
  next_steps: string
}

/** Warning from a perception tool */
export interface AgentWarning {
  type: string
  message: string
  timestamp: number
}

interface WorkbenchState {
  // Tab state
  activeTab: WorkbenchTab
  setActiveTab: (tab: WorkbenchTab) => void

  // Chapter selection
  selectedChapterNumber: number | null
  setSelectedChapterNumber: (n: number | null) => void

  // Phase
  phase: Phase
  setPhase: (p: Phase) => void

  // AI sidebar
  aiSidebarOpen: boolean
  toggleAiSidebar: () => void
  aiMessages: AiMessage[]
  addAiMessage: (message: AiMessage) => void
  updateAiMessage: (id: string, updater: (msg: AiMessage) => AiMessage) => void
  clearAiMessages: () => void
  setAiMessages: (messages: AiMessage[]) => void

  // Impact assessment
  pendingImpacts: ImpactReport[]
  addPendingImpact: (report: ImpactReport) => void
  removePendingImpact: (changeId: number) => void

  // Warnings
  agentWarnings: AgentWarning[]
  addAgentWarning: (warning: AgentWarning) => void
  clearAgentWarnings: () => void

  // Agent busy state
  isAgentBusy: boolean
  setIsAgentBusy: (busy: boolean) => void

  // Agent sending state
  isAgentSending: boolean
  setIsAgentSending: (sending: boolean) => void

  // Model selection
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void

  // Knowledge refresh trigger
  knowledgeVersion: number
  incrementKnowledgeVersion: () => void

  // Project isolation
  currentProjectId: number | null
  setCurrentProjectId: (id: number | null) => void

  // 多会话管理
  activeConversationId: number | null
  setActiveConversationId: (id: number | null) => void
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  // Tab
  activeTab: 'knowledge',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // Chapter
  selectedChapterNumber: null,
  setSelectedChapterNumber: (n) => set({ selectedChapterNumber: n }),

  // Phase
  phase: 'incubation',
  setPhase: (p) => set({ phase: p }),

  // AI sidebar
  aiSidebarOpen: true,
  toggleAiSidebar: () => set((s) => ({ aiSidebarOpen: !s.aiSidebarOpen })),
  aiMessages: [],
  addAiMessage: (message) =>
    set((s) => ({ aiMessages: [...s.aiMessages, message] })),
  updateAiMessage: (id, updater) =>
    set((s) => ({
      aiMessages: s.aiMessages.map((m) => (m.id === id ? updater(m) : m)),
    })),
  clearAiMessages: () => set({ aiMessages: [] }),
  setAiMessages: (messages) => set({ aiMessages: messages }),

  // Impact assessment
  pendingImpacts: [],
  addPendingImpact: (report) =>
    set((s) => ({ pendingImpacts: [...s.pendingImpacts, report] })),
  removePendingImpact: (changeId) =>
    set((s) => ({ pendingImpacts: s.pendingImpacts.filter((r) => r.change_id !== changeId) })),

  // Warnings
  agentWarnings: [],
  addAgentWarning: (warning) =>
    set((s) => ({ agentWarnings: [...s.agentWarnings, { ...warning, timestamp: Date.now() }] })),
  clearAgentWarnings: () => set({ agentWarnings: [] }),

  // Agent busy
  isAgentBusy: false,
  setIsAgentBusy: (busy) => set({ isAgentBusy: busy }),

  // Agent sending
  isAgentSending: false,
  setIsAgentSending: (sending) => set({ isAgentSending: sending }),

  // Model
  selectedModelKey: '',
  setSelectedModelKey: (key) => set({ selectedModelKey: key }),

  // Knowledge refresh trigger (incremented on agent_done to trigger tab refreshes)
  knowledgeVersion: 0,
  incrementKnowledgeVersion: () => set((s: { knowledgeVersion: number }) => ({ knowledgeVersion: s.knowledgeVersion + 1 })),

  // Project
  currentProjectId: null,
  setCurrentProjectId: (id) => set({
    currentProjectId: id,
    aiMessages: [],
    pendingImpacts: [],
    agentWarnings: [],
    knowledgeVersion: 0,
    activeConversationId: null,
  }),

  // 多会话管理
  activeConversationId: null,
  setActiveConversationId: (id) => set({ activeConversationId: id }),
}))
