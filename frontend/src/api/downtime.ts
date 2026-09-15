import { api } from './client'

export const downtimeApi = {
  submit: (body: { station: string; reason: string; duration_min: number; notes?: string; as_operator?: string }) =>
    api.post<{ ok: boolean; message: string }>('/downtime/submit', body),
}
