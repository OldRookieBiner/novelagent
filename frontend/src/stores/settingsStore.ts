/**
 * Settings Store - 用户设置状态管理
 * 使用 Zustand persist middleware 持久化 workflowMode
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UserSettings, WorkflowMode } from '@/types'

interface SettingsState {
  settings: UserSettings | null
  workflowMode: WorkflowMode
  setSettings: (settings: UserSettings) => void
  setWorkflowMode: (mode: WorkflowMode) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      settings: null,
      workflowMode: 'hybrid', // 默认使用混合模式
      setSettings: (settings) => set({ settings }),
      setWorkflowMode: (mode) => set({ workflowMode: mode }),
    }),
    {
      name: 'settings-storage', // localStorage key
      // 只持久化 workflowMode，settings 从 API 获取
      partialize: (state) => ({
        workflowMode: state.workflowMode,
      }),
    }
  )
)