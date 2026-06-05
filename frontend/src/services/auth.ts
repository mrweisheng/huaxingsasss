import api from './api'
import type { User } from '@/types'

export interface LoginData {
  username: string
  password: string
}

export interface PublicChangePasswordData {
  username: string
  old_password: string
  new_password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  expires_in: number
  user: User
}

export const authApi = {
  login: (data: LoginData): Promise<TokenResponse> =>
    api.post('/auth/login', data),

  refreshToken: (refreshToken: string): Promise<{ access_token: string; expires_in: number; user?: User }> =>
    api.post('/auth/refresh', { refresh_token: refreshToken }),

  getCurrentUser: (): Promise<User> =>
    api.get('/auth/me'),

  changePasswordPublic: (data: PublicChangePasswordData): Promise<{ message: string }> =>
    api.post('/auth/change-password', data),
}
