import { api } from './client'

export interface TvHealth {
  state: string
  is_alarm: boolean
  is_warning: boolean
  message: string
}

export interface TopPourer {
  operator: string
  rate_lph: number
}

export interface PackingBreakdownRow {
  resin: string
  lot_number: string
  units: number
  color: string
  skids: number
}

export interface WorkOrderRow {
  resin_type: string
  color: string
  pump_station: string
  current_units: number
  target_units: number
  progress_pct: number
}

export interface TvOverview {
  active_shift: string
  health: TvHealth
  current_output_l: number
  current_run_rate_lph: number
  expected_now_l: number
  target_lph: number
  pace_derived: boolean
  pace_station_count: number
  pace_gap_l: number
  projected_total_l: number
  shift_target_l: number
  build_pct: number
  scope_packed: number
  total_poured: number
  total_packed: number
  unpacked_wip: number
  packing_enabled: boolean
  show_runs_card: boolean
  top_pourers: TopPourer[]
  packing_breakdown: PackingBreakdownRow[]
  work_orders: WorkOrderRow[]
}

export const tvApi = {
  overview: (mode: 'auto' | 'daily') => api.get<TvOverview>(`/tv/overview?mode=${mode}`),
}
