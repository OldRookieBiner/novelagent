// frontend/src/stores/workbenchStore.ts

import { create } from 'zustand'
import type { WorkbenchTab, MenuItem } from '@/types/workbench'
import { SETTINGS_MENUS } from '@/types/workbench'

/** AI 消息内容段 */
export interface AiMessageSegment {
  type: 'agent_text' | 'chunk' | 'review' | 'chapter_preview'
  content: string
  data?: Record<string, unknown>
}

/** AI 侧栏消息 */
export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  segments: AiMessageSegment[]
  actions?: AiAction[]
  timestamp: number
}

/** AI 工具调用动作 */
export interface AiAction {
  tool: string
  status: 'running' | 'done' | 'error'
  description: string
  args?: Record<string, unknown>
  result?: Record<string, unknown>
}

interface WorkbenchState
{
  // Tab 状态
  activeTab: WorkbenchTab
  setActiveTab: (tab: WorkbenchTab) => void

  // 菜单状态
  activeMenuItem: MenuItem
  setActiveMenuItem: (item: MenuItem) => void

  // 侧边栏状态
  sidebarCollapsed: boolean
  toggleSidebar: () => void

  // AI 面板状态
  aiPanelTab: 'assist' | 'review'
  setAiPanelTab: (tab: 'assist' | 'review') => void

  // AI 侧栏状态
  aiSidebarOpen: boolean
  toggleAiSidebar: () => void
  aiMessages: AiMessage[]
  addAiMessage: (message: AiMessage) => void
  clearAiMessages: () => void

  // AI 更新标记
  aiUpdateMarkers: Record<string, boolean>
  addAiUpdateMarker: (module: string) => void
  clearAiUpdateMarker: (module: string) => void

  // Agent 并发控制
  isAgentBusy: boolean
  setIsAgentBusy: (busy: boolean) => void

  // Tab 切换状态保留
  panelStates: Record<string, { dirty: boolean }>
  setPanelDirty: (panelKey: string, dirty: boolean) => void

  // 模型选择状态（灵感面板写入，全局读取）
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void

  // 灵感简报状态（AI 生成，用户在 Brief 组件中编辑）
  inspirationBrief: string
  setInspirationBrief: (brief: string) => void

  // 项目隔离
  currentProjectId: number | null
  setCurrentProjectId: (id: number | null) => void
  loadingMessages: boolean
  loadConversation: (projectId: number) => Promise<void>
  clearConversation: (projectId: number) => Promise<void>

  // 重置
  reset: () => void
}

const initialState = {
  activeTab: 'inspiration' as WorkbenchTab,
  activeMenuItem: 'outline' as MenuItem,
  sidebarCollapsed: false,
  aiPanelTab: 'assist' as const,
  aiSidebarOpen: true,
  aiMessages: [] as AiMessage[],
  aiUpdateMarkers: {} as Record<string, boolean>,
  panelStates: {} as Record<string, { dirty: boolean }>,
  selectedModelKey: '' as string,
  isAgentBusy: false as boolean,
  inspirationBrief: '' as string,
  currentProjectId: null as number | null,
  loadingMessages: false,
}

export const useWorkbenchStore = create<WorkbenchState>()((set, get) => ({
  ...initialState,

  setActiveTab: (tab) =>
  {
    // 切换到设定 Tab 时重置菜单项为大纲
    if (tab === 'settings')
    {
      set({ activeTab: tab, activeMenuItem: SETTINGS_MENUS[0].key })
    }
    else
    {
      set({ activeTab: tab })
    }
  },

  setActiveMenuItem: (item) => set({ activeMenuItem: item }),

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setAiPanelTab: (tab) => set({ aiPanelTab: tab }),

  toggleAiSidebar: () => set((state) => ({ aiSidebarOpen: !state.aiSidebarOpen })),

  addAiMessage: (message) => set((state) => ({
    aiMessages: [...state.aiMessages, {
      ...message,
      segments: message.segments || [],
    }]
  })),

  clearAiMessages: () => set({ aiMessages: [] }),

  addAiUpdateMarker: (module) => set((state) => ({
    aiUpdateMarkers: { ...state.aiUpdateMarkers, [module]: true }
  })),

  clearAiUpdateMarker: (module) => set((state) =>
  {
    const markers = { ...state.aiUpdateMarkers }
    delete markers[module]
    return { aiUpdateMarkers: markers }
  }),

  setPanelDirty: (panelKey, dirty) => set((state) => ({
    panelStates: {
      ...state.panelStates,
      [panelKey]: { ...state.panelStates[panelKey], dirty }
    }
  })),

  setSelectedModelKey: (key) => set({ selectedModelKey: key }),

  setIsAgentBusy: (busy) => set({ isAgentBusy: busy }),

  setInspirationBrief: (brief) => set({ inspirationBrief: brief }),

  setCurrentProjectId: (id) => {
    const { currentProjectId } = get()
    if (id !== currentProjectId) {
      set({
        currentProjectId: id,
        aiMessages: [],
        aiUpdateMarkers: {},
        loadingMessages: !!id,
      })
      if (id) {
        Promise.resolve().then(() => get().loadConversation(id))
      }
    }
  },

  loadConversation: async (projectId) => {
    try {
      const { fetchConversation } = await import('@/lib/agentApi')
      const data = await fetchConversation(projectId, 50)
      set({
        aiMessages: data.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          segments: (m.segments || []) as AiMessageSegment[],
          actions: (m.actions || []) as AiAction[],
          timestamp: m.timestamp,
        })),
        loadingMessages: false,
      })
    } catch {
      set({ loadingMessages: false })
    }
  },

  clearConversation: async (projectId) => {
    try {
      const { deleteConversation } = await import('@/lib/agentApi')
      await deleteConversation(projectId)
      set({ aiMessages: [] })
    } catch {
      // 静默失败
    }
  },

  reset: () => set(initialState),
}))
