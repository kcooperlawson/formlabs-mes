import { api } from './client'

export interface BatchTotals {
  fillings_in_window: number
  sitting_now: number
  waiting_qc: number
  avg_qc_turnaround_h: number | null
  avg_time_in_vessel_h: number | null
  longest_sitting_h: number | null
  longest_qc_wait_h: number | null
  no_qc_recorded: number
}

export interface DwellByVessel {
  reactor_name: string
  avg_hours: number
}

export interface QcTrendPoint {
  day: string
  avg_hours: number
}

export interface OutAtQc {
  id: number
  reactor_name: string
  resin_type: string
  hours_at_qc: number
}

export interface BatchRow {
  id: number
  reactor_name: string
  resin_type: string
  filled_at: string | null
  emptied_at: string | null
  hours_in_reactor: number | null
  qc_sent_at: string | null
  qc_result_at: string | null
  hours_at_qc: number | null
  qc_result: string
  qc_note: string
  qc_by: string
  open: boolean
  qc_open: boolean
}

export interface BatchHistoryData {
  totals: BatchTotals
  dwell_by_vessel: DwellByVessel[]
  qc_trend: QcTrendPoint[]
  out_at_qc: OutAtQc[]
  batches: BatchRow[]
  can_manage_qc: boolean
}

export interface SetBatchQcBody {
  sent_at: string
  result_at?: string | null
  result?: string
  note?: string
}

export const batchHistoryApi = {
  get: (days: number) => api.get<BatchHistoryData>(`/batch-history?days=${days}`),
  saveQc: (batchId: number, body: SetBatchQcBody) =>
    api.post<{ ok: boolean; message: string }>(`/batch-history/${batchId}/qc`, body),
}
