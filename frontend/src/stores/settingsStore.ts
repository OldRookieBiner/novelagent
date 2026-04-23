import { create } from 'zustand'
import type { UserSettings, WorkflowMode } from '@/types'

interface SettingsState {
  settings: UserSettings | null
  workflowMode: WorkflowMode
  setSettings: (settings: UserSettings) => void
  setWorkflowMode: (mode: WorkflowMode) => void
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  workflowMode: 'hybrid', // 默认使用混合模式
  setSettings: (settings) => set({ settings }),
  setWorkflowMode: (mode) => set({ workflowMode: mode }),
}))