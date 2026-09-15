import { api } from './client'

export interface AnalyticsKpis {
  total_poured_7d: number
  pour_delta_pct: number
  yield_7d: number
  yield_target_pct: number
  total_scrap_7d: number
  downtime_hours_7d: number
  downtime_minutes_7d: number
}

export interface LiveTicker {
  expected_now_l: number
  projected_daily_l: number
}

export interface TrendPoint {
  date: string
  units: number
}

export interface ResinOutput {
  resin: string
  units: number
  color: string
}

export interface DowntimeReason {
  reason: string
  minutes: number
}

export interface HeatmapCell {
  operator: string
  date: string
  units: number
}

export interface WeightReading {
  timestamp: string
  deviation_g: number
  pump_station: string
  resin_type: string | null
  check_weight_g: number | null
  operator_name: string
  status: string | null
}

export interface PumpDeviation {
  pump_station: string
  mean_deviation: number
  count: number
}

export interface FillWeightOut {
  has_readings: boolean
  samples: number
  in_band_pct: string
  mean_deviation: number
  kg_above_target: number
  scatter: WeightReading[]
  by_pump: PumpDeviation[]
  worst_pump_note: string | null
}

export interface AnalyticsOverview {
  kpis: AnalyticsKpis
  live_ticker: LiveTicker
  velocity_trend: TrendPoint[]
  formulation_output: ResinOutput[]
  downtime_pareto: DowntimeReason[]
  operator_matrix: HeatmapCell[]
  top_operators: string[]
  fill_weight: FillWeightOut
}

export const analyticsApi = {
  overview: () => api.get<AnalyticsOverview>('/analytics/overview'),
}
