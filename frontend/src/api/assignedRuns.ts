import { api } from './client'

export interface ReactorOption {
  reactor_name: string
  max_capacity_l: number
}

export interface RunOptions {
  reactors: ReactorOption[]
  pumps: string[]
  operators: string[]
  packers: string[]
  pump_count: number
  enable_packing: boolean
}

export interface AssignedRun {
  id: number
  run_type: string
  status: string
  reactor_id: string
  reactor_size_l: number
  resin_type: string
  resin_color: string
  cartridge_type: string
  target_units: number
  current_units: number
  assigned_operator: string
  pump_station: string
  lot_number: string
  notes: string
  created_at: string
}

export interface RunTotals {
  total_target: number
  total_actual: number
  fleet_pct: number
  active_count: number
  queued_count: number
  done_count: number
  pumps_configured: number
  pumps_in_use: number
  active_operators_count: number
}

export interface AssignedRunsData {
  runs: AssignedRun[]
  totals: RunTotals
}

export interface CreateRunBody {
  run_type: string
  reactor_id: string
  reactor_size_l: number
  cartridge_type: string
  resin_type: string
  target_units: number
  assigned_pump: string
  assigned_operator: string
  lot_number: string
  notes?: string
  status?: string
}

export const assignedRunsApi = {
  options: () => api.get<RunOptions>('/assigned-runs/options'),
  list: () => api.get<AssignedRunsData>('/assigned-runs'),
  create: (body: CreateRunBody) => api.post<{ ok: boolean; auto_detected_units: number }>('/assigned-runs', body),
  sync: () => api.post<{ ok: boolean }>('/assigned-runs/sync'),
  progress: (id: number, delta: number) => api.post<{ ok: boolean }>(`/assigned-runs/${id}/progress`, { delta }),
  setStatus: (id: number, status: string) => api.post<{ ok: boolean }>(`/assigned-runs/${id}/status`, { status }),
  complete: (id: number, finalUnits: number) =>
    api.post<{ ok: boolean }>(`/assigned-runs/${id}/complete`, { final_units: finalUnits }),
  remove: (id: number) => api.del<{ ok: boolean }>(`/assigned-runs/${id}`),
}
