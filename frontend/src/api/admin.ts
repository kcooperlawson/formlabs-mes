import { api } from './client'

export interface AdminUser {
  id: number
  full_name: string
  username: string
  email: string | null
  role: string
  shift: string | null
  target_lph: number | null
  is_locked: boolean
  locked_minutes_left: number | null
  failed_login_attempts: number
}

export interface CreateUserRequest {
  full_name: string
  email: string
  username: string
  pin: string
  role: string
  shift: string
  target_lph?: number
}

export interface AbilityInfo {
  key: string
  label: string
  help: string
  status: '' | 'role' | 'granted'
  can_grant: boolean
}

export interface AbilityHistoryEntry {
  ability: string
  label: string
  granted_by: string | null
  granted_at: string | null
  revoked_by: string | null
  revoked_at: string | null
  active: boolean
}

export interface UserAbilities {
  user_id: number
  full_name: string
  role: string
  abilities: AbilityInfo[]
  history: AbilityHistoryEntry[]
}

export interface ErrorReport {
  id: number
  ref_code: string
  occurred_at: string | null
  last_seen_at: string | null
  page: string | null
  user_name: string | null
  user_role: string | null
  app_version: string | null
  error_type: string | null
  message: string | null
  traceback: string | null
  hits: number
  resolved: boolean
  resolved_at: string | null
  resolved_by: string | null
  note: string | null
}

export interface Suggestion {
  id: number
  timestamp: string | null
  user_name: string
  user_role: string
  category: string
  suggestion: string
  status: string
  admin_notes: string | null
  avatar_data_uri: string | null
}

export interface WipStatus {
  poured_today: number
  packed_today: number
  wip: number
}

export interface BackupStatus {
  state: string
  count: number
  newest: string | null
  age_hours: number | null
  message: string
  due_after_hours: number
  keep_backups: number
}

export interface PlantSettings {
  shift_1_start: string
  shift_1_hours: number
  shift_1_break_mins: number
  shift_2_start: string
  shift_2_hours: number
  shift_2_break_mins: number
  shift_count: number
  target_lph: number
  yield_target_pct: number
  enable_packing: boolean
  enable_bulk_pour: boolean
  enable_device_gateway: boolean
  operating_days: string
  operating_days_desc: string
  simple_mode: boolean
  pump_form_url: string
  pump_form_label: string
}

export interface UpdatePlantSettingsRequest {
  shift_1_start: string
  shift_1_hours: number
  shift_1_break_mins: number
  shift_2_start: string
  shift_2_hours: number
  shift_2_break_mins: number
  shift_count: number
  target_lph: number
  yield_target_pct: number
  enable_packing: boolean
  enable_bulk_pour: boolean
  enable_device_gateway: boolean
  operating_days: number[]
  use_work_orders: boolean
  pump_form_url: string
  pump_form_label: string
}

export interface UpdatePlantSettingsResult {
  saved: PlantSettings
  pump_form_warning: string | null
  orders_off_warning: string | null
  no_admin_warning: string | null
}

export interface AdminPump {
  id: number
  station_name: string
  status: string
  pump_type: string | null
  pump_type_label: string | null
  target_lph: number | null
  effective_lph: number
  measured_median_lph: number | null
  measured_samples: number | null
}

export interface DowntimeReasonRow {
  id: number
  reason_name: string
}

const q = (params: Record<string, string | number | boolean | undefined>) => {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined) usp.set(k, String(v))
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export const adminApi = {
  users: () => api.get<AdminUser[]>('/admin/users'),
  createUser: (body: CreateUserRequest) => api.post<AdminUser>('/admin/users', body),
  updateRoleShift: (id: number, role: string, shift: string) => api.put(`/admin/users/${id}/role-shift`, { role, shift }),
  resetPin: (id: number, pin: string) => api.put(`/admin/users/${id}/pin`, { pin }),
  unlockUser: (id: number) => api.post(`/admin/users/${id}/unlock`),
  deleteUser: (id: number) => api.del(`/admin/users/${id}`),

  userAbilities: (id: number) => api.get<UserAbilities>(`/admin/users/${id}/abilities`),
  grantAbility: (id: number, key: string) => api.post(`/admin/users/${id}/abilities/${key}`),
  revokeAbility: (id: number, key: string) => api.del(`/admin/users/${id}/abilities/${key}`),

  errorReports: (includeResolved: boolean) => api.get<ErrorReport[]>(`/admin/error-reports${q({ include_resolved: includeResolved })}`),
  resolveErrorReport: (id: number, note: string) => api.post(`/admin/error-reports/${id}/resolve`, { note }),

  suggestions: () => api.get<Suggestion[]>('/admin/suggestions'),
  updateSuggestion: (id: number, status: string, adminNotes: string) =>
    api.put(`/admin/suggestions/${id}`, { status, admin_notes: adminNotes }),
  deleteSuggestion: (id: number) => api.del(`/admin/suggestions/${id}`),

  wip: () => api.get<WipStatus>('/admin/wip'),
  clearWip: () => api.post<{ cleared: number }>('/admin/wip/clear'),

  backupStatus: () => api.get<BackupStatus>('/admin/backups/status'),
  backups: () => api.get<string[]>('/admin/backups'),
  createBackup: () => api.post<{ filename: string }>('/admin/backups'),
  restoreBackup: (filename: string) => api.post('/admin/backups/restore', { filename }),

  settings: () => api.get<PlantSettings>('/admin/settings'),
  updateSettings: (body: UpdatePlantSettingsRequest) => api.put<UpdatePlantSettingsResult>('/admin/settings', body),

  pumps: () => api.get<AdminPump[]>('/admin/pumps'),
  addPump: (stationName: string, pumpType: string) =>
    api.post('/admin/pumps', { station_name: stationName, pump_type: pumpType }),
  setPumpType: (id: number, pumpType: string) =>
    api.put(`/admin/pumps/${id}/type`, { pump_type: pumpType }),
  setPumpRate: (id: number, targetLph: number) => api.put(`/admin/pumps/${id}/rate`, { target_lph: targetLph }),
  deletePump: (id: number) => api.del(`/admin/pumps/${id}`),

  downtimeReasons: () => api.get<DowntimeReasonRow[]>('/admin/downtime-reasons'),
  addDowntimeReason: (reasonName: string) => api.post('/admin/downtime-reasons', { reason_name: reasonName }),
  deleteDowntimeReason: (id: number) => api.del(`/admin/downtime-reasons/${id}`),
}
