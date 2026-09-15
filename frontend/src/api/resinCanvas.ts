import { api } from './client'

export interface ResinCanvasRow {
  id: number
  cartridge_type: string
  sku: string
  resin_code: string
  resin_name: string
  actual_spec_g: number
  min_weight_g: number
  max_weight_g: number
  target_kg: number
  multiplier: number
  lifetime_months: string
  color: string
}

export interface AddResinBody {
  cartridge_type: string
  sku: string
  resin_code: string
  resin_name: string
  actual_spec_g: number
  min_weight_g: number
  max_weight_g: number
  color_tag?: string | null
}

export interface UpdateResinBody {
  actual_spec_g: number
  min_weight_g: number
  max_weight_g: number
  color_tag: string
}

export const resinCanvasApi = {
  list: (format: string, search: string) =>
    api.get<ResinCanvasRow[]>(`/resin-canvas?format=${encodeURIComponent(format)}&search=${encodeURIComponent(search)}`),
  add: (body: AddResinBody) => api.post<ResinCanvasRow>('/resin-canvas', body),
  update: (id: number, body: UpdateResinBody) => api.put<ResinCanvasRow>(`/resin-canvas/${id}`, body),
  remove: (id: number) => api.del<{ ok: boolean }>(`/resin-canvas/${id}`),
}
