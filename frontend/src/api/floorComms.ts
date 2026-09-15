import { api } from './client'
import type { Note } from './notes'

export interface OperatorThreadSummary {
  name: string
  has_written: boolean
}

export const floorCommsApi = {
  operators: () => api.get<OperatorThreadSummary[]>('/floor-comms/operators'),
  thread: (operatorName: string) =>
    api.get<Note[]>(`/floor-comms/thread?${new URLSearchParams({ operator_name: operatorName })}`),
  reply: (operatorName: string, message: string) =>
    api.post<{ ok: boolean }>('/floor-comms/reply', { operator_name: operatorName, message }),
}
