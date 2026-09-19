import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { devicesApi } from '../api/devices'
import { ApiError } from '../api/client'
import { fl } from '../theme'
import { AddDeviceTab } from './AddDeviceTab'
import { DevicesTab } from './DevicesTab'
import { FindDevicesTab, type Prefill } from './FindDevicesTab'
import { ReadingsTab } from './ReadingsTab'
import { ago, useGateways } from './gateways'

const tile = fl.tile

type TabKey = 'find' | 'devices' | 'add' | 'readings'

// Device Gateway, ported from pages/Device_Registry.py - register a
// machine (whatever protocol it speaks), assign it to the pump station it
// sits on, map its raw tags to canonical metrics. The background gateway
// process (not part of this app) is what actually polls; this page only
// edits the registry it reads from.
export function DeviceRegistryPage() {
  const metaQuery = useQuery({ queryKey: ['devices-meta'], queryFn: devicesApi.meta, retry: false })
  const [tab, setTab] = useState<TabKey>('devices')
  const [prefill, setPrefill] = useState<Prefill | null>(null)

  const devicesQuery = useQuery({
    queryKey: ['devices'], queryFn: devicesApi.list,
    enabled: !!metaQuery.data?.gateway_enabled,
    refetchInterval: 10_000,
  })
  const gatewaysQuery = useGateways()

  if (metaQuery.isLoading) return null
  if (metaQuery.isError) {
    const denied = metaQuery.error instanceof ApiError && metaQuery.error.status === 403
    return (
      <div className="flex flex-col gap-4">
        <h1 className={fl.heading}>🔌 Device Gateway</h1>
        <p className={`${fl.card} py-6 text-center text-sm text-red-400`}>
          {denied ? '🔒 Access Denied: Restricted to IT Administrators.' : 'Could not reach the device gateway.'}
        </p>
      </div>
    )
  }
  if (!metaQuery.data) return null

  if (!metaQuery.data.gateway_enabled) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className={fl.heading}>🔌 Device Gateway</h1>
        <div className="rounded-lg border border-amber-800 bg-amber-950 px-4 py-3 text-sm text-amber-200">
          🔌 The hardware gateway is switched off for this plant.
          <p className="mt-1 text-xs text-amber-300">
            Turn it on in IT Admin under Plant Configuration, then come back here to register machines. Nothing is
            polled until the gateway process is running as well.
          </p>
        </div>
      </div>
    )
  }

  const devices = devicesQuery.data ?? []
  const total = devices.length
  const online = devices.filter((d) => d.is_enabled && d.status === 'Online').length
  const attention = devices.filter((d) => d.is_enabled && ['Error', 'No data', 'Not reporting'].includes(d.status)).length
  const disabled = devices.filter((d) => !d.is_enabled).length

  const gateways = gatewaysQuery.data ?? []
  const liveGateways = gateways.filter((g) => g.online)

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={fl.heading}>🔌 Device Gateway</h1>
        <p className={`text-xs ${fl.muted}`}>
          Register machines here — filling stations, scales, label printers, whatever's next — regardless of what
          protocol they speak. Assign each one to the pump station it sits on, map its tags, and the gateway service
          does the rest: readings land in Analytics the same way a hand-typed count does.
        </p>
      </div>

      {gatewaysQuery.isSuccess && (
        liveGateways.length > 1 ? (
          <div className="rounded-lg border border-red-800 bg-red-950 px-4 py-3 text-sm text-red-200">
            ⚠️ {liveGateways.length} gateway PCs are running at once: {liveGateways.map((g) => g.hostname).join(', ')}.
            <p className="mt-1 text-xs text-red-300">
              Every one of them polls every device, so each machine is read — and its production logged — once per
              gateway. Stop the gateway on all but one PC.
            </p>
          </div>
        ) : liveGateways.length === 1 ? (
          <p className={`text-xs ${fl.muted}`}>
            🖥️ Gateway running on <b className="text-white">{liveGateways[0].hostname}</b>
            {liveGateways[0].ip_address ? ` (${liveGateways[0].ip_address})` : ''} · checked in {ago(liveGateways[0].seconds_since_heartbeat)}
            {liveGateways[0].app_version ? ` · ${liveGateways[0].app_version}` : ''}
          </p>
        ) : (
          <div className="rounded-lg border border-amber-800 bg-amber-950 px-4 py-3 text-sm text-amber-200">
            🖥️ {gateways.length ? `No gateway is running — ${gateways[0].hostname} last checked in ${ago(gateways[0].seconds_since_heartbeat)}.` : 'No gateway PC has checked in yet.'}
            <p className="mt-1 text-xs text-amber-300">
              Nothing is being read from any machine until the gateway runs on the PC they're cabled to
              (START_HERE.bat, option 4). A gateway PC still on 4.06 or older doesn't check in — update it too.
            </p>
          </div>
        )
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={tile}><p className="text-lg font-semibold text-white">{total}</p><p className={`text-xs ${fl.muted}`}>Total Devices</p></div>
        <div className={tile}><p className="text-lg font-semibold text-emerald-400">{online}</p><p className={`text-xs ${fl.muted}`}>Online</p></div>
        <div className={tile}><p className="text-lg font-semibold text-red-400">{attention}</p><p className={`text-xs ${fl.muted}`}>Need attention</p></div>
        <div className={tile}><p className="text-lg font-semibold text-white">{disabled}</p><p className={`text-xs ${fl.muted}`}>Disabled</p></div>
      </div>

      <div className={fl.tabStrip}>
        {([
          ['find', '🔍 Find Devices'], ['devices', '📋 Devices'], ['add', '➕ Add / Test Device'], ['readings', '📈 Recent Readings'],
        ] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={tab === key ? fl.tabActive : fl.tabInactive}>{label}</button>
        ))}
      </div>

      {tab === 'find' && <FindDevicesTab meta={metaQuery.data} onUse={(p) => { setPrefill(p); setTab('add') }} />}
      {tab === 'devices' && <DevicesTab meta={metaQuery.data} />}
      {tab === 'add' && <AddDeviceTab meta={metaQuery.data} prefill={prefill} onSaved={() => setTab('devices')} />}
      {tab === 'readings' && <ReadingsTab devices={devices} />}
    </div>
  )
}
