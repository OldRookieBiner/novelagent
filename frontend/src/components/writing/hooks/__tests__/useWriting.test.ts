import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

vi.mock('@/lib/api', () => ({
  projectsApi: {
    get: vi.fn().mockResolvedValue({
      id: 1,
      title: 'Test Project',
      workflow_state: { stage: 'writing' },
    }),
  },
  chapterOutlinesApi: {
    list: vi.fn().mockResolvedValue([]),
  },
  chaptersApi: {
    get: vi.fn().mockResolvedValue({ content: '', word_count: 0 }),
  },
  workflowApi: {
    updateStage: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('@/lib/sseParser', () => ({
  createSSEStream: vi.fn(),
}))

import { projectsApi } from '@/lib/api'
import { useWriting } from '../useWriting'

describe('useWriting', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns null project when projectId is undefined', () => {
    const { result } = renderHook(() => useWriting(undefined))

    expect(result.current.project).toBeNull()
  })

  it('fetches project data when projectId is provided', async () => {
    renderHook(() => useWriting('1'))

    await waitFor(() => {
      expect(projectsApi.get).toHaveBeenCalledWith(1)
    })
  })
})
