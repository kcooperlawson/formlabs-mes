import { useQuery } from '@tanstack/react-query'
import { devicesApi, type GatewayNode } from '../api/devices'

// Which PC a Find Devices scan or a Test Connection runs on. Until 4.07 it was
// always the MES server, because that's where the API runs - but on a plant
// where the machines are cabled to a separate floor PC, the server sees the
// wrong COM ports and often can't reach the machines' network at all. A
// gateway PC runs these for us instead (device_gateway/jobs.py).
//
// Encoded as a plain string so it drops straight into a <select>:
// 'server', or 'gw:<hostname>'.
export type LookFrom = string

export const SERVER: LookFrom = 'server'

export function gatewayHost(lookFrom: LookFrom): string | null {
  return lookFrom.startsWith('gw:') ? lookFrom.slice(3) : null
}

export function useGateways() {
  return useQuery({ queryKey: ['device-gateways'], queryFn: devicesApi.gateways, refetchInterval: 10_000 })
}

// The gateway that's actually running, if there is one. The server is only
// the default when no gateway has checked in recently.
export function defaultLookFrom(gateways: GatewayNode[] | undefined): LookFrom {
  const live = (gateways ?? []).find((g) => g.online)
  return live ? `gw:${live.hostname}` : SERVER
}

export function lookFromName(lookFrom: LookFrom, serverHostname: string): string {
  return gatewayHost(lookFrom) ?? serverHostname
}

export function ago(seconds: number | null | undefined): string {
  if (seconds == null) return 'never'
  const s = Math.max(0, Math.floor(seconds))
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}
