import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({
  settingsApi: {
    get: vi.fn().mockResolvedValue({
      model_provider: 'openai',
      model_name: 'gpt-4',
      has_api_key: true,
    }),
  },
  modelConfigsApi: {
    list: vi.fn().mockResolvedValue({ models: [] }),
  },
}))

vi.mock('@/stores/settingsStore', () => ({
  useSettingsStore: vi.fn(() => ({
    setSettings: vi.fn(),
  })),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import { settingsApi } from '@/lib/api'
import { useSettings } from '../useSettings'

describe('useSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('sets loading=true initially, then false after fetch', async () => {
    const { result } = renderHook(() => useSettings())

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })

  it('loads settings on mount', async () => {
    renderHook(() => useSettings())

    await waitFor(() => {
      expect(settingsApi.get).toHaveBeenCalled()
    })
  })
})
