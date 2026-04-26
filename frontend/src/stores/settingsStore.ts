/**
 * Settings Store - 用户设置状态管理
 *
 * 注意：workflowMode 已迁移到项目级别（后端 WorkflowState 表）
 * 此处仅作为临时缓存，不再持久化到 localStorage
 * 项目的 workflowMode 应从后端获取
 */

import { create } from 'zustand'
import type { UserSettings, WorkflowMode } from '@/types'

interface SettingsState {
  settings: UserSettings | null
  workflowMode: WorkflowMode  // 临时缓存，不持久化
  setSettings: (settings: UserSettings) => void
  setWorkflowMode: (mode: WorkflowMode) => void
}

export const useSettingsStore = create<SettingsState>()((set) => ({
  settings: null,
  workflowMode: 'hybrid', // 默认使用混合模式
  setSettings: (settings) => set({ settings }),
  setWorkflowMode: (mode) => set({ workflowMode: mode }),
}))