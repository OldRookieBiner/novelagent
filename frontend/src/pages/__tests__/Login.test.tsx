import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test/utils'
import Login from '@/pages/Login'

const mockSetUser = vi.fn()
const mockSetToken = vi.fn()
const mockNavigate = vi.fn()

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn((selector) => {
    const state = { setUser: mockSetUser, setToken: mockSetToken }
    return selector ? selector(state) : state
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('@/lib/api', () => ({
  authApi: {
    login: vi.fn(),
  },
  projectsApi: {},
  settingsApi: {},
  modelConfigsApi: {},
  systemPromptsApi: {},
  outlineApi: {},
  chapterOutlinesApi: {},
  chaptersApi: {},
}))

import { authApi } from '@/lib/api'

describe('Login', () => {
  it('renders login form with title, inputs and button', () => {
    render(<Login />)

    expect(screen.getByText('NovelAgent')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('shows error message on failed login', async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(new Error('用户名或密码错误'))

    render(<Login />)

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'wrong' } })
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'pass' } })
    fireEvent.submit(screen.getByRole('button', { name: '登录' }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText('用户名或密码错误')).toBeInTheDocument()
    })
    expect(mockSetToken).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })
})
