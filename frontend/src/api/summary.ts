import { api } from './client'

export interface HourlyPoint {
  hour: string
  units: number
}

export interface ResinPoint {
  resin: string
  units: number
  litres: number
}

export interface CartridgePoint {
  cartridge_type: string
  units: number
  litres: number
}

export interface ShiftSummary {
  has_logs_today: boolean
  units: number
  litres: number
  scrap: number
  yield_pct: number
  logs_submitted: number
  has_output_logs: boolean
  hourly_timeline: HourlyPoint[]
  by_resin: ResinPoint[]
  by_cartridge: CartridgePoint[]
}

export interface MonthlyRecap {
  has_data: boolean
  month_label: string
  units: number
  best_day_ordinal: string | null
  best_day_units: number
  mismatches: number
}

export const summaryApi = {
  today: (asOperator?: string) =>
    api.get<ShiftSummary>(asOperator ? `/summary/today?${new URLSearchParams({ as_operator: asOperator })}` : '/summary/today'),
  monthly: () => api.get<MonthlyRecap>('/summary/monthly'),
}
