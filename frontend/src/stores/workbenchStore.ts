// workbenchStore.ts — 创作智能体工作台状态管理

import { create } from 'zustand'

/** 工作台标签页 */
export type WorkbenchTab = 'writing' | 'knowledge' | 'structure' | 'tracking'

/** 创作阶段 */
export type Phase = 'incubation' | 'structure' | 'writing' | 'revision'

/** AI 消息内容段 */
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview' | 'warning'
  content: string
  data?: Record<string, unknown>
}

/** AI 侧栏消息 */
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  segments: AiMessageSegment[]
  timestamp: number
}

interface WorkbenchState {
  // Tab 状态
  activeTab: WorkbenchTab
  setActiveTab: (tab: WorkbenchTab) => void

  // 章节选择
  selectedChapterNumber: number | null
  setSelectedChapterNumber: (n: number | null) => void

  // 创作阶段
  phase: Phase
  setPhase: (p: Phase) => void

  // AI 侧栏状态
  aiSidebarOpen: boolean
  toggleAiSidebar: () => void
  aiMessages: AiMessage[]
  addAiMessage: (message: AiMessage) => void
  clearAiMessages: () => void

  // Agent 并发控制
  isAgentBusy: boolean
  setIsAgentBusy: (busy: boolean) => void

  // 模型选择
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void

  // 项目隔离
  currentProjectId: number | null
  setCurrentProjectId: (id: number | null) => void
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  // Tab
  activeTab: 'writing',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // 章节
  selectedChapterNumber: null,
  setSelectedChapterNumber: (n) => set({ selectedChapterNumber: n }),

  // 阶段
  phase: 'incubation',
  setPhase: (p) => set({ phase: p }),

  // AI 侧栏
  aiSidebarOpen: true,
  toggleAiSidebar: () => set((s) => ({ aiSidebarOpen: !s.aiSidebarOpen })),
  aiMessages: [],
  addAiMessage: (message) =>
    set((s) => ({ aiMessages: [...s.aiMessages, message] })),
  clearAiMessages: () => set({ aiMessages: [] }),

  // Agent
  isAgentBusy: false,
  setIsAgentBusy: (busy) => set({ isAgentBusy: busy }),

  // 模型
  selectedModelKey: '',
  setSelectedModelKey: (key) => set({ selectedModelKey: key }),

  // 项目
  currentProjectId: null,
  setCurrentProjectId: (id) => set({ currentProjectId: id }),
}))
