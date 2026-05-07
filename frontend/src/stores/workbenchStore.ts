// frontend/src/stores/workbenchStore.ts

import { create } from 'zustand'
import type { WorkbenchTab, MenuItem } from '@/types/workbench'

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

  // Tab 切换状态保留
  panelStates: Record<string, { dirty: boolean }>
  setPanelDirty: (panelKey: string, dirty: boolean) => void

  // 模型选择状态（灵感面板写入，全局读取）
  selectedModelKey: string
  setSelectedModelKey: (key: string) => void

  // 重置
  reset: () => void
}

const initialState = {
  activeTab: 'planning' as WorkbenchTab,
  activeMenuItem: 'inspiration' as MenuItem,
  sidebarCollapsed: false,
  aiPanelTab: 'assist' as const,
  panelStates: {} as Record<string, { dirty: boolean }>,
  selectedModelKey: '' as string,
}

export const useWorkbenchStore = create<WorkbenchState>((set) => ({
  ...initialState,

  setActiveTab: (tab) =>
  {
    // 切换到规划 Tab 时重置菜单项为灵感
    if (tab === 'planning')
    {
      set({ activeTab: tab, activeMenuItem: 'inspiration' })
    }
    else
    {
      set({ activeTab: tab })
    }
  },

  setActiveMenuItem: (item) => set({ activeMenuItem: item }),

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setAiPanelTab: (tab) => set({ aiPanelTab: tab }),

  setPanelDirty: (panelKey, dirty) => set((state) => ({
    panelStates: {
      ...state.panelStates,
      [panelKey]: { ...state.panelStates[panelKey], dirty }
    }
  })),

  setSelectedModelKey: (key) => set({ selectedModelKey: key }),

  reset: () => set(initialState),
}))