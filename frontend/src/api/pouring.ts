import { api } from './client'

export interface VesselRef {
  reactor_name: string
  tag: string
  bay_marker: string | null
}

export interface VesselChoice {
  value: string
  label: string
}

export interface BatchInfo {
  id: number
  qc_result: string
  qc_open: boolean
  hours_in_reactor: number | null
}

// Mirrors api/schemas/pouring.py's ReactorLookupOut exactly - one shape,
// `status` says which of the five branches applies.
export interface ReactorLookup {
  status: 'blank' | 'changeover' | 'no_vessel' | 'ambiguous' | 'matched'
  vessel: VesselRef | null
  current_resin: string | null
  options: VesselChoice[]
  vessel_names: string[]
  batch: BatchInfo | null
  can_mark_empty: boolean
}

export interface FastPathInfo {
  since: string
  by: string
  entered_masked: string
}

// Mirrors api/schemas/pouring.py's LotGateOut. auto_lot is only meaningful
// when gate_applies is false - the real expected lot is never in here.
export interface LotGate {
  gate_applies: boolean
  noun: string
  field_label: string
  where_hint: string
  still_reads_label: string
  expected_is_real: boolean
  auto_lot: string
  matched_run: boolean
  fast_path: FastPathInfo | null
}

export interface BulkPreview {
  litres: number
  description: string
  blocked: boolean
  message: string
}

export interface PourSubmitResponse {
  ok: boolean
  log_id: number | null
  matched_run: boolean
  weight_icon: string
  weight_message: string
  messages: string[]
  landed: string
}

export interface UndoResponse {
  ok: boolean
  message: string
}

export interface StationBenchmark {
  /** The median hourly count on this pump - what an ordinary hour looks like. */
  typical: number
  /** The best single hourly count on record for it. */
  best: number
  samples: number
}

export interface LastEntry {
  found: boolean
  pump_station: string
  resin_type: string
  cartridge_type: string
  lot_number: string
  bottles: number
  logged_at: string | null
}

export const pouringApi = {
  lastEntry: (asOperator?: string) =>
    api.get<LastEntry>(asOperator
      ? `/pouring/last-entry?as_operator=${encodeURIComponent(asOperator)}`
      : '/pouring/last-entry'),
  stationBenchmark: (station: string) =>
    api.get<StationBenchmark>(`/pouring/station-benchmark?station=${encodeURIComponent(station)}`),
  reactorLookup: (station: string, resin: string) =>
    api.get<ReactorLookup>(
      `/pouring/reactor-lookup?${new URLSearchParams({ station, resin })}`,
    ),
  changeover: (reactor_name: string, new_resin: string, station: string, shift: string, as_operator?: string) =>
    api.post<{ ok: boolean }>('/pouring/changeover', { reactor_name, new_resin, station, shift, as_operator }),
  linkVessel: (reactor_name: string, station: string) =>
    api.post<{ ok: boolean }>('/pouring/link-vessel', { reactor_name, station }),
  markEmpty: (reactor_name: string, as_operator?: string) =>
    api.post<{ ok: boolean }>('/pouring/mark-empty', { reactor_name, as_operator }),

  lotGate: (station: string, resin: string, cartridgeType: string) =>
    api.get<LotGate>(
      `/pouring/lot-gate?${new URLSearchParams({ station, resin, cartridge_type: cartridgeType })}`,
    ),
  lotCheck: (station: string, resin: string, cartridgeType: string, enteredLot: string) =>
    api.get<{ result: 'verified' | 'recorded' | 'mismatch' }>(
      `/pouring/lot-check?${new URLSearchParams({ station, resin, cartridge_type: cartridgeType, entered_lot: enteredLot })}`,
    ),
  bulkPreview: (params: {
    resin: string
    station: string
    containers: number
    amount_each: number
    unit: string
    off_tank: boolean
    note?: string
  }) =>
    api.post<BulkPreview>(
      `/pouring/bulk-preview?${new URLSearchParams({
        resin: params.resin,
        station: params.station,
        containers: String(params.containers),
        amount_each: String(params.amount_each),
        unit: params.unit,
        off_tank: String(params.off_tank),
        note: params.note ?? '',
      })}`,
    ),
  submit: (formData: FormData) => api.postForm<PourSubmitResponse>('/pouring/submit', formData),
  undo: (log_id: number, as_operator?: string) => api.post<UndoResponse>('/pouring/undo', { log_id, as_operator }),
}
