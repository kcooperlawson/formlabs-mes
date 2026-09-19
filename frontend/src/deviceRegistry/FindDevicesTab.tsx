import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { devicesApi, type DeviceMeta, type NetworkHost, type SerialPort } from '../api/devices'
import { fl } from '../theme'
import { defaultLookFrom, gatewayHost, lookFromName, useGateways, type LookFrom } from './gateways'
import { LookFromPicker } from './LookFromPicker'

const input = fl.input

export interface Prefill {
  device_name: string
  device_role: string
  protocol: string
  connection: Record<string, unknown>
  look_from?: LookFrom
}

// Find Devices - a serial-port enumeration (pure OS device listing, no I/O
// to the ports themselves) and a network scan (real outbound TCP connects
// to the conventional ports Modbus/OPC-UA/MQTT/HTTP use on this subnet,
// like a Wi-Fi picker for plant equipment). Both read-only, and both run on
// whichever PC is picked at the top - normally the gateway PC the machines
// are cabled to, not the server this page happens to be served from.
export function FindDevicesTab({ meta, onUse }: { meta: DeviceMeta; onUse: (prefill: Prefill) => void }) {
  const gatewaysQuery = useGateways()
  const gateways = gatewaysQuery.data ?? []
  const [chosen, setChosen] = useState<LookFrom | null>(null)
  const lookFrom = chosen ?? defaultLookFrom(gatewaysQuery.data)
  const host = gatewayHost(lookFrom)
  const where = lookFromName(lookFrom, meta.server_hostname)

  const [serialResults, setSerialResults] = useState<SerialPort[] | null>(null)
  const serialMutation = useMutation({
    mutationFn: () => (host ? devicesApi.gatewaySerialPorts(host) : devicesApi.serialPorts()),
    onSuccess: setSerialResults,
  })

  const subnetQuery = useQuery({
    queryKey: ['devices-subnet', lookFrom],
    queryFn: () => (host ? devicesApi.gatewaySubnet(host) : devicesApi.guessSubnet()),
    enabled: !gatewaysQuery.isLoading,
    retry: false,
  })
  const [subnet, setSubnet] = useState('')
  const effectiveSubnet = subnet || subnetQuery.data?.subnet || ''
  const [netResults, setNetResults] = useState<NetworkHost[] | null>(null)
  const scanMutation = useMutation({
    mutationFn: () => (host ? devicesApi.gatewayScan(host, effectiveSubnet) : devicesApi.scanNetwork(effectiveSubnet)),
    onSuccess: setNetResults,
  })

  // Results from one PC mean nothing once a different PC is picked.
  useEffect(() => {
    setSerialResults(null)
    setNetResults(null)
    setSubnet('')
    serialMutation.reset()
    scanMutation.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lookFrom])

  const use = (prefill: Prefill) => onUse({ ...prefill, look_from: lookFrom })

  return (
    <div className="flex flex-col gap-4">
      <LookFromPicker label="Look for machines from" value={lookFrom} onChange={setChosen}
                      serverHostname={meta.server_hostname} gateways={gateways} />

      <hr className={fl.divider} />

      <div>
        <p className="mb-1 text-sm font-semibold text-white">🔎 Serial / COM Ports on {where}</p>
        <p className={`mb-2 text-xs ${fl.muted}`}>
          Everything {where} currently sees plugged in — bench scales and RS-485/RS-232 dongles show up here the
          moment they're connected. Covers Modbus RTU and Serial ASCII devices.
        </p>
        <button className={fl.btnSecondary} disabled={serialMutation.isPending} onClick={() => serialMutation.mutate()}>
          {serialMutation.isPending ? (host ? `Asking ${host}…` : 'Checking…') : '🔄 Refresh serial ports'}
        </button>
        {serialMutation.isError && <p className="mt-1 text-xs text-red-400">{(serialMutation.error as Error).message}</p>}
        <div className="mt-2 flex flex-col gap-1.5">
          {serialResults === null ? (
            <p className={`text-sm ${fl.muted}`}>Click Refresh serial ports to see what's plugged into {where}.</p>
          ) : serialResults.length === 0 ? (
            <p className={`text-sm ${fl.muted}`}>Nothing found on {where} — plug in the scale or serial adapter, then refresh again.</p>
          ) : (
            serialResults.map((sp) => (
              <div key={sp.port} className="flex items-center justify-between rounded-md border border-[#1E293B] bg-[#0F172A] px-3.5 py-2.5">
                <span>
                  <b className="text-white">🔌 {sp.port}</b>{' '}
                  <span className={`text-sm ${fl.muted}`}>{[sp.manufacturer, sp.description].filter(Boolean).join(' · ')}</span>
                </span>
                <button
                  className={fl.btnSecondary}
                  onClick={() => use({ device_name: `Device on ${sp.port}`, device_role: 'scale', protocol: 'serial_ascii', connection: { port: sp.port, baud: 9600 } })}
                >
                  Use →
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      <hr className={fl.divider} />

      <div>
        <p className="mb-1 text-sm font-semibold text-white">📡 Network Scan from {where}</p>
        <p className={`mb-2 text-xs ${fl.muted}`}>
          Probes this subnet for the ports the network protocols conventionally use (502 Modbus TCP, 4840 OPC-UA,
          1883 MQTT, 80/443 HTTP). An open port is a strong hint, not a confirmed match — use Test Connection in the
          Add tab afterward to be sure before saving. This only opens plain outbound TCP connections on {where}'s
          network — nothing is written to any machine.
        </p>
        <div className="flex gap-2">
          <input className={`${input} flex-1`} placeholder={subnetQuery.isFetching ? `Asking ${where} for its subnet…` : 'Subnet to scan (CIDR)'}
                 value={effectiveSubnet} onChange={(e) => setSubnet(e.target.value)} />
          <button className={fl.btn} disabled={scanMutation.isPending || !effectiveSubnet} onClick={() => scanMutation.mutate()}>
            {scanMutation.isPending ? 'Scanning…' : '🔍 Scan network'}
          </button>
        </div>
        {subnetQuery.isError && <p className="mt-1 text-xs text-amber-400">{(subnetQuery.error as Error).message} Type the subnet in by hand to scan anyway.</p>}
        {scanMutation.isError && <p className="mt-1 text-xs text-red-400">{(scanMutation.error as Error).message}</p>}
        <div className="mt-2 flex flex-col gap-1.5">
          {netResults === null ? (
            <p className={`text-sm ${fl.muted}`}>Click Scan network to look for machines on this subnet.</p>
          ) : netResults.length === 0 ? (
            <p className={`text-sm ${fl.muted}`}>
              Nothing answered on those ports from {where} — the machine may be on a network {where} can't reach, or
              need its Modbus/OPC-UA/MQTT server turned on first.
            </p>
          ) : (
            netResults.map((found) => (
              <div key={found.ip} className="flex items-center justify-between rounded-md border border-[#1E293B] bg-[#0F172A] px-3.5 py-2.5">
                <span>
                  <b className="text-white">📟 {found.ip}</b>{found.hostname ? ` (${found.hostname})` : ''}{' '}
                  <span className={`text-sm ${fl.muted}`}>
                    · ports open: {found.open_ports.join(', ')} · likely: {found.guessed_protocol ?? 'unknown protocol'}
                  </span>
                </span>
                <button
                  className={fl.btnSecondary}
                  onClick={() => {
                    const proto = found.guessed_protocol || 'modbus_tcp'
                    let connection: Record<string, unknown> = { host: found.ip }
                    if (proto === 'modbus_tcp') connection = { host: found.ip, port: 502, unit_id: 1 }
                    else if (proto === 'opcua') connection = { endpoint: `opc.tcp://${found.ip}:4840` }
                    else if (proto === 'mqtt') connection = { host: found.ip, port: 1883 }
                    else if (proto === 'http_poll') connection = { url: `http://${found.ip}/`, method: 'GET', timeout_s: 5.0 }
                    use({ device_name: `Device @ ${found.ip}`, device_role: proto === 'modbus_tcp' ? 'filling_station' : 'other', protocol: proto, connection })
                  }}
                >
                  Use →
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
