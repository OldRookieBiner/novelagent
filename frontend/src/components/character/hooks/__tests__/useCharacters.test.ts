import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('@/lib/characterApi', () => ({
  characterApi: {
    list: vi.fn().mockResolvedValue({ characters: [{ id: 1, name: 'Test Character' }] }),
  },
  relationApi: {
    list: vi.fn().mockResolvedValue({ relations: [] }),
  },
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import { characterApi, relationApi } from '@/lib/characterApi'
import { useCharacters } from '../useCharacters'

describe('useCharacters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads characters when activeTab is "characters" and projectId is provided', async () => {
    renderHook(() => useCharacters(1, 'characters'))

    await waitFor(() => {
      expect(characterApi.list).toHaveBeenCalledWith(1)
    })
  })

  it('returns empty array and does not call API when projectId is null', async () => {
    const { result } = renderHook(() => useCharacters(null, 'characters'))

    expect(result.current.characters).toEqual([])
    expect(characterApi.list).not.toHaveBeenCalled()
    expect(relationApi.list).not.toHaveBeenCalled()
  })
})
