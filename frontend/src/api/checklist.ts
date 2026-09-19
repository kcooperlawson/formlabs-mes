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

export interface ComplianceRow {
  operator_name: string
  pump_station: string
  shift: string
  poured: number
  checklist_at: string | null
  start_audit_at: string | null
  transfer_audit_at: string | null
  end_audit_at: string | null
  start_expected: boolean
  transfer_expected: boolean
  end_expected: boolean
  complete: boolean
}

export interface ComplianceOut {
  date: string
  rows: ComplianceRow[]
  /** "self" for an operator, "everyone" for a manager or admin. */
  scope: string
}

export const checklistApi = {
  compliance: (onDate: string, asOperator?: string) => {
    const params = new URLSearchParams({ on_date: onDate })
    if (asOperator) params.set('as_operator', asOperator)
    return api.get<ComplianceOut>(`/checklist/compliance?${params}`)
  },
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
