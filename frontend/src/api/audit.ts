import { api } from './client'

export const AUDIT_TYPES = [
  'Start Of Shift (Cleanliness Check)',
  'End Of Shift (Cleanliness Check)',
  'Station / Pump Transfer Check',
  'Resin Spill / Containment Issue',
] as const

export const auditApi = {
  submit: (formData: FormData) => api.postForm<{ ok: boolean; message: string }>('/audit/submit', formData),
}
