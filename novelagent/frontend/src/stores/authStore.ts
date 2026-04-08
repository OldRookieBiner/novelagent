import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { setSessionToken } from '@/lib/api'

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  setToken: (token: string | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => {
        setSessionToken(token)
        set({ token, isAuthenticated: !!token })
      },
      logout: () => {
        setSessionToken(null)
        set({ user: null, token: null, isAuthenticated: false })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ token: state.token }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          setSessionToken(state.token)
        }
      },
    }
  )
)