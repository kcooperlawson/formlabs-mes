import { api } from './client'

export const packingApi = {
  submit: (body: {
    cartridge_type: string
    resin: string
    lot_number: string
    units_packed: number
    notes?: string
    as_operator?: string
  }) => api.post<{ ok: boolean; message: string }>('/packing/submit', body),
}
