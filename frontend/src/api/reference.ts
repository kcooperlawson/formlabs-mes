import { api } from './client'

export interface ResinColor {
  bg: string
  fg: string
  border: string
}

export interface ResinSpec {
  cartridge_type: string
  resin_name: string
  target_g: number
  min_g: number
  max_g: number
  target_kg: number
  units_per_skid: number
  color: ResinColor
}

export interface ContainerFormats {
  labels: string[]
  codes: Record<string, string> // label -> code, e.g. "V2 (1L Cartridge)" -> "V2"
}

export interface PlantSettings {
  simple_mode: boolean
  enable_bulk_pour: boolean
  enable_packing: boolean
  enable_device_gateway: boolean
  pump_form_url: string
  pump_form_label: string
}

export const referenceApi = {
  pumps: () => api.get<string[]>('/reference/pumps'),
  resins: () => api.get<ResinSpec[]>('/reference/resins'),
  containerFormats: (bulkEnabled: boolean) =>
    api.get<ContainerFormats>(`/reference/container-formats?bulk_enabled=${bulkEnabled}`),
  plantSettings: () => api.get<PlantSettings>('/reference/plant-settings'),
  downtimeReasons: () => api.get<string[]>('/reference/downtime-reasons'),
  activeOperators: () => api.get<string[]>('/reference/active-operators'),
  appVersion: () => api.get<{ version: string }>('/reference/app-version'),
}
