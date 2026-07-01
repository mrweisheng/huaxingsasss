import { create } from 'zustand'
import type { User } from '@/types'
import { authApi, type LoginData, type TokenResponse } from '@/services/auth'

interface AuthState {
  user: User | null
  accessToken: string | null
  isAuthenticated: boolean
  login: (data: LoginData) => Promise<void>
  logout: () => void
}

// 凭证刷新（401 时）走 src/services/api.ts 的响应拦截器直接 api.post('/auth/refresh')，
// 因此本 store 不再保留 refreshToken 字段 / refreshAccessToken action。
export const useAuthStore = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  accessToken: localStorage.getItem('access_token'),
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (data: LoginData) => {
    const response: TokenResponse = await authApi.login(data)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    set({
      user: response.user,
      accessToken: response.access_token,
      isAuthenticated: true,
    })
  },

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
    })
  },
}))