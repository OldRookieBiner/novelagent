import { describe, it, expect, beforeEach } from 'vitest'
import { act } from '@testing-library/react'
import { useAuthStore } from '@/stores/authStore'

// Reset store before each test
beforeEach(() => {
  useAuthStore.setState({
    user: null,
    token: null,
    isAuthenticated: false,
  })
})

describe('AuthStore', () => {
  it('starts with default state', () => {
    const state = useAuthStore.getState()

    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
  })

  it('sets user correctly', () => {
    const user = {
      id: 1,
      username: 'testuser',
      created_at: '2024-01-01T00:00:00',
    }

    act(() => {
      useAuthStore.getState().setUser(user)
    })

    const state = useAuthStore.getState()
    expect(state.user).toEqual(user)
    expect(state.isAuthenticated).toBe(true)
  })

  it('sets token correctly', () => {
    const token = 'test-token-123'

    act(() => {
      useAuthStore.getState().setToken(token)
    })

    const state = useAuthStore.getState()
    expect(state.token).toBe(token)
    expect(state.isAuthenticated).toBe(true)
  })

  it('logout clears state', () => {
    // First set some state
    act(() => {
      useAuthStore.getState().setUser({
        id: 1,
        username: 'testuser',
        created_at: '2024-01-01T00:00:00',
      })
      useAuthStore.getState().setToken('token')
    })

    // Then logout
    act(() => {
      useAuthStore.getState().logout()
    })

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
  })

  it('setUser with null clears authentication', () => {
    // First authenticate
    act(() => {
      useAuthStore.getState().setUser({
        id: 1,
        username: 'testuser',
        created_at: '2024-01-01T00:00:00',
      })
    })

    // Then clear user
    act(() => {
      useAuthStore.getState().setUser(null)
    })

    const state = useAuthStore.getState()
    expect(state.isAuthenticated).toBe(false)
  })
})