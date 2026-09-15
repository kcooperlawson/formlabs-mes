import { api } from './client'

export interface FloorUser {
  id: number
  full_name: string
  username: string
  role: string
  shift: string
}

export const rosterApi = {
  list: () => api.get<FloorUser[]>('/roster'),
  provision: (body: {
    full_name: string; email: string; username: string; pin: string
    role: 'operator' | 'packer'; shift: string; target_lph?: number
  }) => api.post<{ ok: boolean }>('/roster/provision', body),
  resetPin: (userId: number, newPin: string) =>
    api.post<{ ok: boolean }>('/roster/reset-pin', { user_id: userId, new_pin: newPin }),
}
