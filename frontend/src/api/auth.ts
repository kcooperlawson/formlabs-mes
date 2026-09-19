import { api } from './client'

// Mirrors api/schemas/auth.py's UserOut exactly.
export interface User {
  id: number
  username: string
  full_name: string
  role: string
  shift: string | null
  preferred_theme: string | null
  avatar_filename: string | null
  abilities: string[]
}

export interface LoginRequest {
  username: string
  pin: string
  remember?: boolean
}

export interface RegisterRequest {
  full_name: string
  email: string
  username: string
  pin: string
  role: 'Operator' | 'Packer'
  shift: string
}

export const authApi = {
  me: () => api.get<User>('/auth/me'),
  login: (body: LoginRequest) => api.post<User>('/auth/login', body),
  logout: () => api.post<void>('/auth/logout'),
  register: (body: RegisterRequest) => api.post<{ ok: boolean }>('/auth/register', body),
  mode: () => api.get<{ simple_mode: boolean }>('/auth/mode'),
}
