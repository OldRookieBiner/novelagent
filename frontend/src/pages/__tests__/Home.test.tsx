import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@/test/utils'
import Home from '@/pages/Home'

const mockIsAuthenticated = vi.fn()

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn((selector) => {
    const state = { isAuthenticated: mockIsAuthenticated(), setUser: vi.fn(), setToken: vi.fn() }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/lib/api', () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  authApi: {},
  settingsApi: {},
  modelConfigsApi: {},
  systemPromptsApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

import { projectsApi } from '@/lib/api'

describe('Home', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows loading skeleton initially when authenticated', () => {
    mockIsAuthenticated.mockReturnValue(true)
    vi.mocked(projectsApi.list).mockReturnValue(new Promise(() => {}))

    render(<Home />)

    expect(screen.getByText('我的项目')).toBeInTheDocument()
    expect(document.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })

  it('shows empty state when no projects exist', async () => {
    mockIsAuthenticated.mockReturnValue(true)
    vi.mocked(projectsApi.list).mockResolvedValueOnce({ projects: [], total: 0 })

    render(<Home />)

    await waitFor(() => {
      expect(screen.getByText('创建你的第一个项目，开始写作之旅')).toBeInTheDocument()
    })
  })
})
