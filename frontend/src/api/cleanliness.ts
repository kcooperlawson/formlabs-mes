import { api } from './client'

export interface CleanlinessStats {
  total_audits: number
  start_checks: number
  end_checks: number
  transfers: number
  spills: number
}

export interface CleanlinessAudit {
  id: number
  audit_type: string
  pump_station: string
  operator_name: string
  timestamp: string
  notes: string
  is_spill: boolean
  photos: string[]
}

export const cleanlinessApi = {
  stats: () => api.get<CleanlinessStats>('/cleanliness/stats'),
  audits: () => api.get<CleanlinessAudit[]>('/cleanliness/audits'),
  photoUrl: (filename: string) => `/api/cleanliness/photos/${encodeURIComponent(filename)}`,
  remove: (id: number) => api.del<{ ok: boolean }>(`/cleanliness/audits/${id}`),
}
