import { api } from './client'

export interface DeviceRow {
  id: number
  device_name: string
  device_role: string
  protocol: string
  assigned_pump: string
  assigned_reactor: string
  poll_interval_s: number
  is_enabled: boolean
  status: string
  last_seen_at: string | null
  seconds_since_seen: number | null
  last_error: string | null
}

export interface CreateDeviceRequest {
  device_name: string
  device_role: string
  protocol: string
  connection: Record<string, unknown>
  poll_interval_s?: number
  pump_station_id?: number | null
  reactor_id?: number | null
  notes?: string
}

export interface TagMapRow {
  id: number
  raw_tag: string
  canonical_metric: string
  data_type: string
  scale_factor: number
  unit: string | null
}

export interface ReadingRow {
  timestamp: string
  metric: string
  value_numeric: number | null
  value_text: string | null
}

export interface TestConnectionResult {
  ok: boolean
  raw: Record<string, unknown>
  error: string | null
}

export interface SerialPort {
  port: string
  description: string | null
  manufacturer: string | null
}

export interface NetworkHost {
  ip: string
  hostname: string | null
  open_ports: number[]
  guessed_protocol: string | null
}

export interface DeviceOption {
  id: number
  name: string
}

export interface DeviceMeta {
  gateway_enabled: boolean
  server_hostname: string
  protocol_labels: Record<string, string>
  canonical_metrics: string[]
  role_options: string[]
  pumps: DeviceOption[]
  reactors: DeviceOption[]
}

export interface GatewayNode {
  hostname: string
  ip_address: string | null
  app_version: string | null
  started_at: string | null
  last_heartbeat_at: string | null
  seconds_since_heartbeat: number | null
  online: boolean
}

export type GatewayJobKind = 'serial_ports' | 'subnet' | 'scan' | 'test_connection'

export interface GatewayJob {
  id: number
  target_host: string
  kind: GatewayJobKind
  status: 'pending' | 'running' | 'done' | 'error'
  result: unknown
  error: string | null
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// Leaves a job for the gateway on `hostname` and waits for its answer. The
// server gives up on a job nobody picks up within a minute and says so, so
// this only needs its own ceiling for a gateway that dies mid-job.
async function runOnGateway<T>(hostname: string, kind: GatewayJobKind, params: Record<string, unknown> = {}): Promise<T> {
  const { id } = await api.post<{ id: number }>(`/devices/gateways/${encodeURIComponent(hostname)}/jobs`, { kind, params })
  const deadline = Date.now() + 5 * 60 * 1000
  while (Date.now() < deadline) {
    await sleep(1000)
    const job = await api.get<GatewayJob>(`/devices/gateway-jobs/${id}`)
    if (job.status === 'done') return job.result as T
    if (job.status === 'error') throw new Error(job.error ?? `The gateway on ${hostname} couldn't run this.`)
  }
  throw new Error(`The gateway on ${hostname} didn't finish in time.`)
}

export const devicesApi = {
  meta: () => api.get<DeviceMeta>('/devices/meta'),
  list: () => api.get<DeviceRow[]>('/devices'),
  create: (body: CreateDeviceRequest) => api.post<DeviceRow>('/devices', body),
  setEnabled: (id: number, enabled: boolean) => api.put(`/devices/${id}/enabled?enabled=${enabled}`),
  remove: (id: number) => api.del(`/devices/${id}`),

  tags: (deviceId: number) => api.get<TagMapRow[]>(`/devices/${deviceId}/tags`),
  saveTag: (deviceId: number, body: { raw_tag: string; canonical_metric: string; data_type: string; scale_factor: number; unit: string }) =>
    api.post(`/devices/${deviceId}/tags`, body),
  deleteTag: (tagId: number) => api.del(`/devices/tags/${tagId}`),

  readings: (deviceId: number, hours: number) => api.get<ReadingRow[]>(`/devices/${deviceId}/readings?hours=${hours}`),

  testConnection: (protocol: string, connection: Record<string, unknown>, probeTags: string[]) =>
    api.post<TestConnectionResult>('/devices/test-connection', { protocol, connection, probe_tags: probeTags }),

  gateways: () => api.get<GatewayNode[]>('/devices/gateways'),
  gatewaySerialPorts: (hostname: string) => runOnGateway<SerialPort[]>(hostname, 'serial_ports'),
  gatewaySubnet: (hostname: string) => runOnGateway<{ subnet: string }>(hostname, 'subnet'),
  gatewayScan: (hostname: string, subnet: string) => runOnGateway<NetworkHost[]>(hostname, 'scan', { subnet }),
  gatewayTestConnection: (hostname: string, protocol: string, connection: Record<string, unknown>, probeTags: string[]) =>
    runOnGateway<TestConnectionResult>(hostname, 'test_connection', { protocol, connection, probe_tags: probeTags }),

  serialPorts: () => api.get<SerialPort[]>('/devices/discovery/serial-ports'),
  guessSubnet: () => api.get<{ subnet: string }>('/devices/discovery/subnet'),
  scanNetwork: (subnet: string) => api.get<NetworkHost[]>(`/devices/discovery/scan?subnet=${encodeURIComponent(subnet)}`),
}
