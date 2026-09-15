import { api } from './client'

export interface HourlyPoint {
  hour: string
  units: number
}

export interface ResinPoint {
  resin: string
  units: number
}

export interface ShiftSummary {
  has_logs_today: boolean
  units: number
  scrap: number
  yield_pct: number
  logs_submitted: number
  has_output_logs: boolean
  hourly_timeline: HourlyPoint[]
  by_resin: ResinPoint[]
}

export const summaryApi = {
  today: (asOperator?: string) =>
    api.get<ShiftSummary>(asOperator ? `/summary/today?${new URLSearchParams({ as_operator: asOperator })}` : '/summary/today'),
}
