import { api } from './client'

export interface UpdateStatus {
  current_version: string
  latest_version: string | null
  update_available: boolean
  notes: string | null
  published_at: string | null
  error: string | null
  publish_enabled: boolean
}

export interface ApplyUpdateResult {
  ok: boolean
  version: string
  log: string
  restarting: boolean
  restart_mode: 'supervised' | 'relaunch' | 'manual'
}

export interface PublishUpdateResult {
  html_url: string
  tag_name: string
  asset_name: string
  asset_size: number
}

export interface UpdateSource {
  kind: 'server' | 'github'
  address: string
  repo: string
  token_set: boolean
}

export interface AvailableUpdate {
  version: string
  notes: string
  published_at: string
  size: number | null
  current: boolean
  newer: boolean
}

export const updatesApi = {
  status: () => api.get<UpdateStatus>('/updates/status'),
  // Skips the server's 15-minute cache - the "Check now" button.
  checkNow: () => api.get<UpdateStatus>('/updates/status?force=true'),
  apply: () => api.post<ApplyUpdateResult>('/updates/apply', {}),
  applyVersion: (version: string, allowOlder: boolean) =>
    api.post<ApplyUpdateResult>('/updates/apply', { version, allow_older: allowOlder }),

  source: () => api.get<UpdateSource>('/updates/source'),
  setSource: (address: string, token: string | null) =>
    api.put<UpdateSource>('/updates/source', { address, token }),
  available: () => api.get<AvailableUpdate[]>('/updates/available'),
  publish: (from_version: string, notes: string) =>
    api.post<PublishUpdateResult>('/updates/publish', { from_version, notes }),
}
