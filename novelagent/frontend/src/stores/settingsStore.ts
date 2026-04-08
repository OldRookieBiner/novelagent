import { create } from 'zustand'
import type { UserSettings } from '@/types'

interface SettingsState {
  settings: UserSettings | null
  setSettings: (settings: UserSettings) => void
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: null,
  setSettings: (settings) => set({ settings }),
}))