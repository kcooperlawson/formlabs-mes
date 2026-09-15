import { api } from './client'

export interface LotVerificationTotals {
  checks_logged: number
  full_checks: number
  pct_full: number
  flagged: number
  cartridges_pulled: number
  flag_rate: number
}

export interface LotCheck {
  id: number
  timestamp: string
  operator_name: string
  pump_station: string
  cartridge_type: string
  resin_type: string | null
  resin_color: string | null
  expected_lot: string | null
  entered_lot: string | null
  result: string
  check_level: string
  reason: string | null
  production_log_id: number | null
  photo_filename: string | null
}

export interface OperatorCoverage {
  operator_name: string
  checks: number
  full: number
  fast: number
  flags: number
  pct_full: number
}

export interface StationCoverage {
  pump_station: string
  checks: number
  flags: number
}

export interface LotVerificationData {
  totals: LotVerificationTotals
  checks: LotCheck[]
  by_operator: OperatorCoverage[]
  by_station: StationCoverage[]
}

export const lotVerificationApi = {
  get: (days: number) => api.get<LotVerificationData>(`/lot-verification?days=${days}`),
  photoUrl: (filename: string) => `/api/lot-verification/photos/${encodeURIComponent(filename)}`,
}
