// workbenchStore.ts — Creation agent workbench state management

import { create } from 'zustand'

/** Workbench tab */
export type WorkbenchTab = 'writing' | 'knowledge' | 'structure' | 'tracking'

/** Creation phase */
export type Phase = 'incubation' | 'structure' | 'writing' | 'revision'

/** AI message content segment */
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview' | 'warning' | 'tool_start' | 'tool_result'
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
  clearAiMessages: () => void

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

  // Project isolation
  currentProjectId: number | null
  setCurrentProjectId: (id: number | null) => void
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  // Tab
  activeTab: 'writing',
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
  clearAiMessages: () => set({ aiMessages: [] }),

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

  // Project
  currentProjectId: null,
  setCurrentProjectId: (id) => set({ currentProjectId: id }),
}))
