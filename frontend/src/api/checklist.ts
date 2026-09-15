import { api } from './client'

export interface ChecklistStatus {
  checklist_done: boolean
  cleanliness_done_today: boolean
}

export interface VesselOption {
  value: string
  label: string
}

export interface VesselOptions {
  has_vessel: boolean
  options: VesselOption[]
}

export const checklistApi = {
  status: (station: string, shift: string) =>
    api.get<ChecklistStatus>(`/checklist/status?${new URLSearchParams({ station, shift })}`),
  vesselOptions: (station: string) =>
    api.get<VesselOptions>(`/checklist/vessel-options?${new URLSearchParams({ station })}`),
  submitCleanliness: (formData: FormData) =>
    api.postForm<{ ok: boolean }>('/checklist/cleanliness', formData),
  submit: (body: {
    station: string
    shift: string
    qr_checked: boolean
    materials_checked: boolean
    vessel_reactor_name?: string | null
  }) => api.post<{ ok: boolean }>('/checklist/submit', body),
  markAlreadyDone: (body: { station: string; shift: string; already_who: string }) =>
    api.post<{ ok: boolean }>('/checklist/mark-already-done', body),
}
