import { api } from './client'

export interface ProductionLogRow {
  id: number
  timestamp: string
  log_type: string
  pump_station: string
  resin_type: string | null
  resin_color: string | null
  operator_name: string
  bottles_filled: number
}

export interface ProductionLogFilters {
  log_types: string[]
  pumps: string[]
  operators: string[]
  min_date: string | null
  max_date: string | null
}

export interface ProductionLogsData {
  filters: ProductionLogFilters
  total_matches: number
  rows: ProductionLogRow[]
}

export interface DowntimeLogRow {
  id: number
  timestamp: string
  pump_station: string
  reason: string
  duration_min: number
  operator_name: string
}

export interface DowntimeLogFilters {
  pumps: string[]
  reasons: string[]
  min_date: string | null
  max_date: string | null
}

export interface DowntimeLogsData {
  filters: DowntimeLogFilters
  total_matches: number
  rows: DowntimeLogRow[]
}

export interface ProductionFilterParams {
  start_date?: string
  end_date?: string
  log_type?: string
  pump_station?: string
  operator?: string
  limit?: number
}

export interface DowntimeFilterParams {
  start_date?: string
  end_date?: string
  pump_station?: string
  reason?: string
  limit?: number
}

function qs(params: object): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export const logManagementApi = {
  production: (params: ProductionFilterParams) => api.get<ProductionLogsData>(`/log-management/production${qs(params)}`),
  deleteProduction: (id: number) => api.del<{ ok: boolean }>(`/log-management/production/${id}`),
  bulkDeleteProduction: (params: Omit<ProductionFilterParams, 'limit'>) =>
    api.post<{ deleted: number }>(`/log-management/production/bulk-delete${qs(params)}`),
  downtime: (params: DowntimeFilterParams) => api.get<DowntimeLogsData>(`/log-management/downtime${qs(params)}`),
  deleteDowntime: (id: number) => api.del<{ ok: boolean }>(`/log-management/downtime/${id}`),
  bulkDeleteDowntime: (params: Omit<DowntimeFilterParams, 'limit'>) =>
    api.post<{ deleted: number }>(`/log-management/downtime/bulk-delete${qs(params)}`),
}
