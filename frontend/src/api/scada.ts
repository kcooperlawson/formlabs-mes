import { api } from './client'

export interface ScadaHealth {
  state: string
  is_alarm: boolean
  is_warning: boolean
  message: string
}

export interface Trajectory {
  is_live: boolean
  active_shift_name: string
  elapsed_net: number
  remaining_hours: number
  shift_pct: number
  expected_display: string
  projected_total: number
  pace_variance_l: number
  oee_pct: number
  status_badge: string
  next_shift_label: string
}

export interface LeaderboardEntry {
  operator: string
  velocity_lh: number
}

export interface CartTypeCount {
  cartridge_type: string
  units: number
}

export interface PouringOverview {
  liters_output: number
  resin_mass_kg: number
  run_velocity_lh: number
  target_rate_lh: number
  yield_pct: number
  total_scrap: number
  cart_type_counts: CartTypeCount[]
  trajectory: Trajectory | null
  leaderboard: LeaderboardEntry[]
}

export interface PackedByResinLot {
  resin: string
  lot_number: string
  units: number
  skids: number
}

export interface PackingOverview {
  total_packed: number
  total_skids_est: number
  pack_velocity_uh: number
  unpacked_wip: number
  by_resin_lot: PackedByResinLot[]
}

export interface LogRow {
  timestamp: string
  date: string
  log_type: string
  operator_name: string
  pump_station: string
  cartridge_type: string
  resin_type: string
  bottles_filled: number
  scrap_empty: number
  scrap_filled: number
  notes: string
}

export interface ScadaFilters {
  pumps: string[]
  resins: string[]
  operators: string[]
  shifts: string[]
  dates: string[]
}

export interface ScadaOverview {
  health: ScadaHealth
  headline_liters: number
  headline_pace_variance_l: number
  headline_is_live: boolean
  filters: ScadaFilters
  show_pouring: boolean
  show_packing: boolean
  pouring: PouringOverview | null
  packing: PackingOverview | null
  log_stream: LogRow[]
  log_stream_title: string
}

export interface ScadaQuery {
  horizon: 'live' | 'specific' | 'week' | 'month' | 'all'
  date?: string
  pump: string
  resin: string
  operator: string
  shift: string
  sort: 'newest' | 'oldest' | 'units' | 'resin'
}

export const scadaApi = {
  overview: (q: ScadaQuery) => {
    const params: Record<string, string> = {
      horizon: q.horizon, pump: q.pump, resin: q.resin, operator: q.operator, shift: q.shift, sort: q.sort,
    }
    if (q.date) params.date = q.date
    return api.get<ScadaOverview>(`/scada/overview?${new URLSearchParams(params)}`)
  },
}
