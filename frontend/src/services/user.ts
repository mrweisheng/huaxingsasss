import api from './api'
import type { User, PaginatedResponse } from '@/types'

export interface UserListParams {
  page?: number
  per_page?: number
  keyword?: string
}

export interface CreateUserData {
  username: string
  full_name: string
  role?: string
  department?: string
  email?: string
}

export interface UpdateUserData {
  full_name?: string
  email?: string
  department?: string
  role?: string
}

export interface ChangePasswordData {
  old_password: string
  new_password: string
}

export const userApi = {
  getList: (params?: UserListParams, signal?: AbortSignal): Promise<PaginatedResponse<User>> =>
    api.get('/users', { params, signal }),

  create: (data: CreateUserData): Promise<User> =>
    api.post('/users', data),

  update: (id: number, data: UpdateUserData): Promise<User> =>
    api.put(`/users/${id}`, data),

  toggleActive: (id: number): Promise<User> =>
    api.patch(`/users/${id}/toggle-active`),

  resetPassword: (id: number): Promise<void> =>
    api.post(`/users/${id}/reset-password`),

  changePassword: (data: ChangePasswordData): Promise<void> =>
    api.put('/users/me/password', data),
}
