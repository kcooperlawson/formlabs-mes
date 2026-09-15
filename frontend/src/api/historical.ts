import { api } from './client'

export interface HistoricalTotals {
  total_poured: number
  total_packed: number
  total_scrap: number
  yield_pct: number
}

export interface TrendPoint {
  date: string
  bottles_filled: number
}

export interface OperatorOutput {
  operator: string
  bottles_filled: number
}

export interface HistoricalFilters {
  resins: string[]
  operators: string[]
}

export interface HistoricalData {
  filters: HistoricalFilters
  totals: HistoricalTotals
  trend: TrendPoint[]
  by_operator: OperatorOutput[]
}

export const historicalApi = {
  get: (horizon: string, resin: string, operator: string) =>
    api.get<HistoricalData>(
      `/historical?horizon=${encodeURIComponent(horizon)}&resin=${encodeURIComponent(resin)}&operator=${encodeURIComponent(operator)}`,
    ),
}
