import { api } from './client'
import type { User } from './auth'

export const FEEDBACK_CATEGORIES = ['Feature Request', 'App Bug / Error', 'Plant Floor Issue', 'General Feedback'] as const

export interface MyFeedback {
  id: number
  timestamp: string | null
  category: string
  suggestion: string
  status: string
  admin_notes: string | null
}

export const accountApi = {
  updateCredentials: (fullName: string, username: string, pin: string) =>
    api.put<User>('/account/credentials', { full_name: fullName, username, pin }),
  updateTheme: (theme: string) => api.put<User>('/account/theme', { theme }),
  uploadAvatar: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.postForm<User>('/account/avatar', formData)
  },
  avatarUrl: (filename: string) => `/api/account/avatar/${encodeURIComponent(filename)}`,

  submitFeedback: (category: string, suggestion: string) =>
    api.post<{ ok: boolean }>('/account/feedback', { category, suggestion }),
  myFeedback: () => api.get<MyFeedback[]>('/account/feedback'),
}
