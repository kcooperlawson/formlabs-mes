import { api } from './client'

export interface SheetTarget {
  id: number
  name: string
  webhook_url: string
  owner_user_id: number | null
  owner_name: string
  is_shared: boolean
  label: string
  last_sync_text: string
  editable: boolean
}

export interface ClassifyUrlResult {
  kind: string
  url: string
  ok: boolean
  message: string
}

export interface TestResult {
  ok: boolean
  message: string
}

export interface ExportPreview {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
}

export interface PushResult {
  ok: boolean
  message: string
  rows?: number | null
  tab?: string | null
  sheet?: string | null
  url?: string | null
}

export const HORIZONS = [
  '⚡ Live Today (Active Shift)',
  '📆 Past 7 Days',
  '📊 Past 30 Days',
  '🌐 All Time History',
] as const

export const EXPORT_MODES = [
  '📊 Aggregated Calculated Metrics (KPI Summary)',
  '📋 Raw Production Audit Stream',
] as const

export const googleSyncApi = {
  targets: () => api.get<SheetTarget[]>('/google-sync/targets'),
  classifyUrl: (url: string) => api.get<ClassifyUrlResult>(`/google-sync/classify-url?url=${encodeURIComponent(url)}`),
  addTarget: (body: { name: string; url: string; is_shared: boolean }) =>
    api.post<SheetTarget>('/google-sync/targets', body),
  updateTarget: (id: number, body: { name?: string; webhook_url?: string; is_shared?: boolean }) =>
    api.put<SheetTarget>(`/google-sync/targets/${id}`, body),
  deleteTarget: (id: number) => api.del<{ ok: boolean }>(`/google-sync/targets/${id}`),
  testTarget: (id: number) => api.post<TestResult>(`/google-sync/targets/${id}/test`),
  exportPreview: (exportMode: string, horizon: string) =>
    api.get<ExportPreview>(`/google-sync/export-preview?export_mode=${encodeURIComponent(exportMode)}&horizon=${encodeURIComponent(horizon)}`),
  exportXlsxUrl: (exportMode: string, horizon: string, columns: string[]) =>
    `/api/google-sync/export.xlsx?export_mode=${encodeURIComponent(exportMode)}&horizon=${encodeURIComponent(horizon)}&columns=${encodeURIComponent(columns.join(','))}`,
  push: (body: { target_id: number; export_mode: string; horizon: string; columns: string[] }) =>
    api.post<PushResult>('/google-sync/push', body),
}
