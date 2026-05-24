// frontend/src/stores/workbenchStore.ts

import { create } from 'zustand'
import type { WorkbenchTab, MenuItem } from '@/types/workbench'
import { SETTINGS_MENUS } from '@/types/workbench'
import type { InspirationData, FieldStatus } from '@/lib/inspiration/types'

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

  // 灵感面板状态（Agent↔表单双向桥接）
  inspirationFields: InspirationData
  inspirationFieldStatus: Record<string, FieldStatus>
  setInspirationField: <K extends keyof InspirationData>(key: K, value: InspirationData[K]) => void
  setInspirationFieldStatus: (key: string, status: FieldStatus) => void
  setInspirationFields: (fields: Partial<InspirationData>) => void

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
  inspirationFields: {
    novelType: '',
    targetWords: 50000,
    contextStrategy: 'fulltext',
    coreTheme: '',
    targetReader: '',
    wordsPerChapter: '',
  } as InspirationData,
  inspirationFieldStatus: {} as Record<string, FieldStatus>,
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
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

  setInspirationField: (key, value) => set((state) =>
  {
    const newStatus = { ...state.inspirationFieldStatus }
    // 用户手动设置字段时，清除 agent_asking 状态（表示用户已响应 Agent 询问）
    // 保留 agent_populated 状态不变（仅 Agent 自身可清除）
    if (newStatus[key] === 'agent_asking')
    {
      delete newStatus[key]
    }
    return {
      inspirationFields: { ...state.inspirationFields, [key]: value },
      inspirationFieldStatus: newStatus,
    }
  }),

  setInspirationFieldStatus: (key, status) => set((state) => ({
    inspirationFieldStatus: { ...state.inspirationFieldStatus, [key]: status }
  })),

  setInspirationFields: (fields) => set((state) => ({
    inspirationFields: { ...state.inspirationFields, ...fields }
  })),

  reset: () => set(initialState),
}))
