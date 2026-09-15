import { api } from './client'

export interface ScrapTotals {
  empty_scrap: number
  filled_scrap: number
  total_scrap: number
}

export interface ResinOutput {
  resin_type: string
  bottles_filled: number
  color: string
}

export interface DowntimeReason {
  reason: string
  duration_min: number
}

export interface ScrapIntel {
  totals: ScrapTotals
  by_resin: ResinOutput[]
  downtime_by_reason: DowntimeReason[]
}

export const scrapIntelApi = {
  get: () => api.get<ScrapIntel>('/scrap-intel'),
}
