import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setSessionToken, getSessionToken } from '@/lib/api'

// Mock fetch
const mockFetch = vi.fn()
;(globalThis as any).fetch = mockFetch

describe('API Client', () => {
  beforeEach(() => {
    mockFetch.mockReset()
    setSessionToken(null)
  })

  describe('Session Token Management', () => {
    it('sets and gets session token', () => {
      setSessionToken('test-token-123')
      expect(getSessionToken()).toBe('test-token-123')
    })

    it('clears session token', () => {
      setSessionToken('test-token')
      setSessionToken(null)
      expect(getSessionToken()).toBeNull()
    })
  })

  describe('API Requests', () => {
    it('makes authenticated request with token', async () => {
      setSessionToken('test-token')
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      // Import after setting token to use current state
      const { projectsApi } = await import('@/lib/api')

      await projectsApi.list()

      const [_url, options] = mockFetch.mock.calls[0]
      expect(options.headers.Authorization).toContain('Basic')
    })

    it('handles 401 error', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })

      const { projectsApi } = await import('@/lib/api')

      await expect(projectsApi.list()).rejects.toThrow('Unauthorized')
    })

    it('handles network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const { projectsApi } = await import('@/lib/api')

      await expect(projectsApi.list()).rejects.toThrow('Network error')
    })
  })
})