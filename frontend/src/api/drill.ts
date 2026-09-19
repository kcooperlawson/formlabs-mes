import { api } from './client'

/** What to look at. Any combination - a lot, a pump's day, one operator's
 *  pours of one resin. Empty fields are left off. */
export interface DrillFilter {
  lot?: string
  run_id?: number
  pump?: string
  operator?: string
  resin?: string
  reactor?: string
  shift?: string
  date_from?: string
  date_to?: string
  /** Set by a manager standing in for an operator - narrows it to them. */
  as_operator?: string
}

export interface DrillBreakdownRow {
  key: string
  logs: number
  units: number
}

export interface DrillLog {
  id: number
  timestamp: string | null
  date: string | null
  log_type: string
  operator_name: string
  pump_station: string
  shift: string
  resin_type: string
  cartridge_type: string
  lot_number: string
  bottles: number
  litres: number
  scrap_empty: number
  scrap_filled: number
  weight_status: string
  check_weight_g: number | null
  verify_status: string
  notes: string
  pour_note: string
}

export interface DrillRun {
  id: number
  resin_type: string
  pump_station: string
  lot_number: string
  assigned_operator: string
  target_units: number
  current_units: number
  status: string
  created_at: string | null
  cartridge_type?: string
  reactor_id?: string
  notes?: string
  run_type?: string
}

export interface DrillOut {
  scope: 'self' | 'everyone'
  filters: Record<string, string | number>
  summary: {
    logs: number
    units: number
    litres: number
    scrap_empty: number
    scrap_filled: number
    first_at: string | null
    last_at: string | null
    weight: Record<string, number>
    verify: Record<string, number>
    breakdown: Record<'operator' | 'pump' | 'resin' | 'lot' | 'day' | 'shift', DrillBreakdownRow[]>
  }
  truncated: boolean
  run: DrillRun | null
  reactor: {
    name: string
    capacity_l: number
    status: string
    current_resin: string
    assigned_pump: string
    asset_tag: string
    bay_marker: string
  } | null
  logs: DrillLog[]
  runs: DrillRun[]
  batches: {
    id: number
    reactor_name: string
    resin_type: string
    lot_number: string
    pump_station: string
    filled_at: string | null
    emptied_at: string | null
    qc_result: string
    qc_sent_at: string | null
    qc_result_at: string | null
    qc_note: string
  }[]
  verifications: {
    id: number
    timestamp: string | null
    operator_name: string
    pump_station: string
    expected_lot: string
    entered_lot: string
    result: string
    check_level: string
    expiry_status: string
    reason: string
    photo_filename: string
  }[]
  downtime: {
    id: number
    timestamp: string | null
    operator_name: string
    pump_station: string
    shift: string
    reason: string
    duration_min: number
    notes: string
  }[]
  downtime_min: number
  audits: {
    id: number
    timestamp: string | null
    operator_name: string
    pump_station: string
    shift: string
    audit_type: string
    is_spill: boolean
    image_filename: string
    notes: string
  }[]
}

export function drillParams(filter: DrillFilter): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filter)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  return params.toString()
}

export const drillApi = {
  get: (filter: DrillFilter) => api.get<DrillOut>(`/drill?${drillParams(filter)}`),
}
