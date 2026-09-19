import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { devicesApi, type DeviceMeta } from '../api/devices'
import { fl } from '../theme'
import type { Prefill } from './FindDevicesTab'
import { defaultLookFrom, gatewayHost, lookFromName, useGateways, type LookFrom } from './gateways'
import { LookFromPicker } from './LookFromPicker'

const input = fl.input
const select = fl.select

function ConnectionFields({ protocol, connection, setField }: { protocol: string; connection: Record<string, unknown>; setField: (k: string, v: unknown) => void }) {
  const str = (k: string) => (connection[k] as string) ?? ''
  const num = (k: string, d: number) => (connection[k] as number) ?? d

  switch (protocol) {
    case 'modbus_tcp':
      return (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <input className={input} placeholder="Host / IP (10.0.4.22)" value={str('host')} onChange={(e) => setField('host', e.target.value)} />
          <input className={input} type="number" placeholder="Port" value={num('port', 502)} onChange={(e) => setField('port', Number(e.target.value))} />
          <input className={input} type="number" placeholder="Unit / Slave ID" value={num('unit_id', 1)} onChange={(e) => setField('unit_id', Number(e.target.value))} />
        </div>
      )
    case 'modbus_rtu':
      return (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
          <input className={input} placeholder="COM Port (COM5)" value={str('port')} onChange={(e) => setField('port', e.target.value)} />
          <input className={input} type="number" placeholder="Baud" value={num('baud', 9600)} onChange={(e) => setField('baud', Number(e.target.value))} />
          <select className={select} value={str('parity') || 'N'} onChange={(e) => setField('parity', e.target.value)}>
            {['N', 'E', 'O'].map((p) => <option key={p}>{p}</option>)}
          </select>
          <input className={input} type="number" placeholder="Unit / Slave ID" value={num('unit_id', 1)} onChange={(e) => setField('unit_id', Number(e.target.value))} />
        </div>
      )
    case 'opcua':
      return (
        <div className="flex flex-col gap-2">
          <input className={input} placeholder="Endpoint URL (opc.tcp://10.0.4.40:4840)" value={str('endpoint')} onChange={(e) => setField('endpoint', e.target.value)} />
          <div className="grid grid-cols-2 gap-2">
            <input className={input} placeholder="Username (optional)" value={str('username')} onChange={(e) => setField('username', e.target.value || null)} />
            <input className={input} type="password" placeholder="Password (optional)" value={str('password')} onChange={(e) => setField('password', e.target.value || null)} />
          </div>
        </div>
      )
    case 'mqtt':
      return (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-2 gap-2">
            <input className={input} placeholder="Broker Host (10.0.4.5)" value={str('host')} onChange={(e) => setField('host', e.target.value)} />
            <input className={input} type="number" placeholder="Broker Port" value={num('port', 1883)} onChange={(e) => setField('port', Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <input className={input} placeholder="Username (optional)" value={str('username')} onChange={(e) => setField('username', e.target.value || null)} />
            <input className={input} type="password" placeholder="Password (optional)" value={str('password')} onChange={(e) => setField('password', e.target.value || null)} />
          </div>
        </div>
      )
    case 'serial_ascii':
      return (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input className={input} placeholder="COM Port (COM4)" value={str('port')} onChange={(e) => setField('port', e.target.value)} />
            <input className={input} type="number" placeholder="Baud" value={num('baud', 9600)} onChange={(e) => setField('baud', Number(e.target.value))} />
            <input className={input} type="number" step={0.1} placeholder="Read Timeout (s)" value={num('read_timeout_s', 1.0)} onChange={(e) => setField('read_timeout_s', Number(e.target.value))} />
          </div>
          <input className={input} placeholder={String.raw`Request Command (leave blank for continuous-stream scales), e.g. P\r\n`}
                value={str('request_command')} onChange={(e) => setField('request_command', e.target.value || null)} />
        </div>
      )
    case 'http_poll':
      return (
        <div className="flex flex-col gap-2">
          <input className={input} placeholder="URL (http://10.0.4.60/api/status)" value={str('url')} onChange={(e) => setField('url', e.target.value)} />
          <div className="grid grid-cols-2 gap-2">
            <select className={select} value={str('method') || 'GET'} onChange={(e) => setField('method', e.target.value)}>
              {['GET', 'POST'].map((m) => <option key={m}>{m}</option>)}
            </select>
            <input className={input} type="number" placeholder="Timeout (s)" value={num('timeout_s', 5.0)} onChange={(e) => setField('timeout_s', Number(e.target.value))} />
          </div>
        </div>
      )
    case 'simulator': {
      const profile = str('sim_profile') || 'pump'
      return (
        <div className="flex flex-col gap-2">
          <p className={`text-xs ${fl.muted}`}>
            No real hardware — generates a repeating fill cycle so you can try out the gateway, Analytics, and the
            TV Dashboard before any machine is actually wired up. The tag map is filled in for you when you save.
          </p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <select className={select} value={profile} onChange={(e) => setField('sim_profile', e.target.value)}>
              <option value="pump">Pump / filling station</option>
              <option value="scale">Scale (weight only)</option>
            </select>
            <input className={input} type="number" step={0.5} min={1} placeholder="Cycle length (seconds)" value={num('cycle_seconds', 8)} onChange={(e) => setField('cycle_seconds', Number(e.target.value))} />
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <input className={input} type="number" placeholder="Target fill weight (g)" value={num('target_weight_g', 850)} onChange={(e) => setField('target_weight_g', Number(e.target.value))} />
            <input className={input} type="number" step={0.1} placeholder="Noise (%)" value={num('noise_pct', 1.5)} onChange={(e) => setField('noise_pct', Number(e.target.value))} />
            {profile !== 'scale' && (
              <input className={input} type="number" step={0.1} placeholder="Fault rate (%)" value={num('fault_rate_pct', 0)} onChange={(e) => setField('fault_rate_pct', Number(e.target.value))} />
            )}
          </div>
        </div>
      )
    }
    default:
      return null
  }
}

export function AddDeviceTab({ meta, prefill, onSaved }: { meta: DeviceMeta; prefill: Prefill | null; onSaved: () => void }) {
  const queryClient = useQueryClient()
  const [deviceName, setDeviceName] = useState('')
  const [deviceRole, setDeviceRole] = useState(meta.role_options[0])
  const [protocol, setProtocol] = useState(Object.keys(meta.protocol_labels)[0])
  const [pumpId, setPumpId] = useState<number | ''>('')
  const [reactorId, setReactorId] = useState<number | ''>('')
  const [pollInterval, setPollInterval] = useState(5.0)
  const [connection, setConnection] = useState<Record<string, unknown>>({})
  const [notes, setNotes] = useState('')
  const [probeText, setProbeText] = useState('')
  const gatewaysQuery = useGateways()
  const [chosen, setChosen] = useState<LookFrom | null>(null)
  const testFrom = chosen ?? defaultLookFrom(gatewaysQuery.data)

  useEffect(() => {
    if (prefill) {
      setDeviceName(prefill.device_name)
      setDeviceRole(prefill.device_role)
      setProtocol(prefill.protocol)
      setConnection(prefill.connection)
      // Test from the same PC that found it - that's the one known to reach it.
      if (prefill.look_from) setChosen(prefill.look_from)
    }
  }, [prefill])

  const setField = (k: string, v: unknown) => setConnection((c) => ({ ...c, [k]: v }))

  const testMutation = useMutation({
    mutationFn: () => {
      const probes = probeText.split('\n').map((l) => l.trim()).filter(Boolean)
      const host = gatewayHost(testFrom)
      return host
        ? devicesApi.gatewayTestConnection(host, protocol, connection, probes)
        : devicesApi.testConnection(protocol, connection, probes)
    },
  })

  const saveMutation = useMutation({
    mutationFn: () => devicesApi.create({
      device_name: deviceName, device_role: deviceRole, protocol, connection,
      poll_interval_s: pollInterval, pump_station_id: pumpId || null, reactor_id: reactorId || null, notes,
    }),
    onSuccess: () => {
      setDeviceName(''); setConnection({}); setNotes(''); setProbeText('')
      queryClient.invalidateQueries({ queryKey: ['devices'] })
      onSaved()
    },
  })

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-semibold text-white">Register a Device</p>
      {prefill && <p className="rounded-lg border border-emerald-800 bg-emerald-950 px-3 py-2 text-sm text-emerald-200">Filled in from Find Devices — double-check the details below, then Test Connection.</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <input className={input} placeholder="Device Name (e.g. Filling Station 3)" value={deviceName} onChange={(e) => setDeviceName(e.target.value)} />
          <select className={select} value={deviceRole} onChange={(e) => setDeviceRole(e.target.value)}>
            {meta.role_options.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select className={select} value={protocol} onChange={(e) => { setProtocol(e.target.value); setConnection({}) }}>
            {Object.entries(meta.protocol_labels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-2">
          <select className={select} value={pumpId} onChange={(e) => setPumpId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">Assign to Pump Station — none —</option>
            {meta.pumps.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className={select} value={reactorId} onChange={(e) => setReactorId(e.target.value ? Number(e.target.value) : '')}>
            <option value="">Assign to Reactor — none —</option>
            {meta.reactors.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <label className={`block ${fl.label}`}>Poll Interval (seconds)</label>
          <input className={input} type="number" min={0.5} step={0.5} value={pollInterval} onChange={(e) => setPollInterval(Number(e.target.value))} />
        </div>
      </div>

      <div>
        <p className="mb-1 text-sm font-semibold text-white">Connection Details</p>
        <ConnectionFields protocol={protocol} connection={connection} setField={setField} />
      </div>

      <div>
        <p className="mb-1 text-sm font-semibold text-white">Probe Tags (optional — see what the machine actually reports before saving)</p>
        <textarea
          className={`${input} h-24`}
          placeholder={'Modbus: register addresses (e.g. 40001, or 40002:float for a two-register float)\nOPC-UA: node ids\nMQTT: topics\nserial_ascii: a regex with a (?P<value>...) group\nhttp_poll: dotted JSON paths'}
          value={probeText} onChange={(e) => setProbeText(e.target.value)}
        />
        <div className="mt-2">
          <LookFromPicker label="Test from" value={testFrom} onChange={setChosen}
                          serverHostname={meta.server_hostname} gateways={gatewaysQuery.data ?? []} />
        </div>
        <button className={`${fl.btnSecondary} mt-2`} disabled={testMutation.isPending} onClick={() => testMutation.mutate()}>
          {testMutation.isPending ? (gatewayHost(testFrom) ? `Asking ${gatewayHost(testFrom)}…` : 'Connecting…') : '🔎 Test Connection'}
        </button>
        {testMutation.isError && <p className="mt-2 text-sm text-red-400">{(testMutation.error as Error).message}</p>}
        {testMutation.data && (
          testMutation.data.ok ? (
            <div className="mt-2">
              <p className="text-sm text-emerald-400">Connected successfully from {lookFromName(testFrom, meta.server_hostname)}.</p>
              <pre className="mt-1 max-h-40 overflow-auto rounded bg-[#0F172A] p-2 text-xs text-[#94A3B8]">{JSON.stringify(testMutation.data.raw, null, 2)}</pre>
            </div>
          ) : (
            <p className="mt-2 text-sm text-red-400">Connection failed from {lookFromName(testFrom, meta.server_hostname)}: {testMutation.data.error}</p>
          )
        )}
      </div>

      <hr className={fl.divider} />
      <textarea className={input} placeholder="Notes (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {saveMutation.isError && <p className="text-xs text-red-400">{(saveMutation.error as Error).message}</p>}
      <button className={fl.btn} disabled={!deviceName.trim() || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
        💾 Save Device
      </button>
    </div>
  )
}
