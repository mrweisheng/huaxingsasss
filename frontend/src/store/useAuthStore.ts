import { create } from 'zustand'
import type { User } from '@/types'
import { authApi, type LoginData, type TokenResponse } from '@/services/auth'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  login: (data: LoginData) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (data: LoginData) => {
    const response: TokenResponse = await authApi.login(data)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    set({
      user: response.user,
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      isAuthenticated: true,
    })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    })
  },

  refreshAccessToken: async () => {
    const { refreshToken } = get()
    if (!refreshToken) return
    
    const response = await authApi.refreshToken(refreshToken)
    localStorage.setItem('access_token', response.access_token)
    set({ accessToken: response.access_token })
  },
}))
