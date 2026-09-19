import { api } from './client'

export interface BatchInfo {
  hours_in_reactor: number | null
  qc_result: string
  qc_open: boolean
  hours_at_qc: number | null
}

export interface ReactorCard {
  id: number
  reactor_name: string
  capacity_l: number
  asset_tag: string
  bay_marker: string
  current_resin: string | null
  assigned_pump: string | null
  is_idle: boolean
  remaining_l: number
  remaining_kg: number
  fill_pct: number
  lot: string
  svg: string
  batch: BatchInfo | null
  can_mark_empty: boolean
  can_manage: boolean
}

export interface VesselTypeOption {
  value: string
  label: string
  help: string
}

export interface ManageOptions {
  vessel_types: VesselTypeOption[]
  resins: string[]
  pumps: string[]
  bulk_enabled: boolean
}

export interface ManageReactorRow {
  id: number
  reactor_name: string
  capacity_l: number
  vessel_type: string
  asset_tag: string
  bay_marker: string
  assigned_pump: string
  current_resin: string
}

export interface BulkCandidate {
  id: number
  reactor_name: string
  label: string
  current_resin: string
}

export interface DrawInfo {
  capacity_l: number
  current_resin: string
  lot: string
  remaining_l: number
  density_kg_l: number
}

export const reactorsApi = {
  fleet: () => api.get<ReactorCard[]>('/reactors/fleet'),
  manageOptions: () => api.get<ManageOptions>('/reactors/manage-options'),
  manageList: () => api.get<ManageReactorRow[]>('/reactors/manage-list'),
  add: (body: { reactor_name: string; max_capacity_l: number; vessel_type: string; asset_tag: string; bay_marker: string }) =>
    api.post<{ ok: boolean }>('/reactors', body),
  remove: (id: number) => api.del<{ ok: boolean }>(`/reactors/${id}`),
  update: (id: number, body: { vessel_type: string; asset_tag: string; bay_marker: string; assigned_pump: string; current_resin: string }) =>
    api.put<{ ok: boolean }>(`/reactors/${id}`, body),
  bulkCandidates: () => api.get<BulkCandidate[]>('/reactors/bulk-candidates'),
  drawInfo: (id: number) => api.get<DrawInfo>(`/reactors/${id}/draw-info`),
  bulkPour: (id: number, body: { containers: number; amount_each: number; unit: string; note: string }) =>
    api.post<{ ok: boolean; litres: number }>(`/reactors/${id}/bulk-pour`, body),
  markEmpty: (id: number) => api.post<{ ok: boolean }>(`/reactors/${id}/mark-empty`),
  markFilled: (id: number, body: { resin_type: string; lot_number: string; filled_at: string | null; note: string }) =>
    api.post<{ ok: boolean }>(`/reactors/${id}/mark-filled`, body),
  reconcile: (id: number, body: { mode: 'percent' | 'liters'; value: number; notes: string }) =>
    api.post<{ ok: boolean }>(`/reactors/${id}/reconcile`, body),
}
