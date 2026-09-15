import { api } from './client'

export interface Note {
  sender_name: string
  message: string
  timestamp: string
  is_manager_reply: boolean
  avatar_data_uri: string | null
}

export const notesApi = {
  list: (asOperator?: string) =>
    api.get<Note[]>(asOperator ? `/notes?${new URLSearchParams({ as_operator: asOperator })}` : '/notes'),
  send: (message: string, as_operator?: string) => api.post<{ ok: boolean }>('/notes', { message, as_operator }),
}
