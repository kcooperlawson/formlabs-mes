import type { GatewayNode } from '../api/devices'
import { fl } from '../theme'
import { ago, gatewayHost, SERVER, type LookFrom } from './gateways'

// Pick the PC that does the looking - see gateways.ts for why it matters.
export function LookFromPicker({ value, onChange, serverHostname, gateways, label }: {
  value: LookFrom
  onChange: (v: LookFrom) => void
  serverHostname: string
  gateways: GatewayNode[]
  label: string
}) {
  const host = gatewayHost(value)
  const picked = host ? gateways.find((g) => g.hostname === host) : null
  return (
    <div className="flex flex-col gap-1">
      <label className={fl.label}>{label}</label>
      <select className={fl.select} value={value} onChange={(e) => onChange(e.target.value)}>
        {gateways.map((g) => (
          <option key={g.hostname} value={`gw:${g.hostname}`}>
            🖥️ {g.hostname} — gateway PC{g.ip_address ? ` (${g.ip_address})` : ''} · {g.online ? `checked in ${ago(g.seconds_since_heartbeat)}` : `not running, last seen ${ago(g.seconds_since_heartbeat)}`}
          </option>
        ))}
        <option value={SERVER}>🗄️ {serverHostname} — the MES server itself</option>
      </select>
      {host === null ? (
        <p className={`text-xs ${fl.muted}`}>
          Runs on the MES server. That only finds machines if they're plugged into, or on the same network as,
          {' '}{serverHostname}. For machines cabled to a floor PC, pick that PC's gateway instead.
        </p>
      ) : picked && !picked.online ? (
        <p className="text-xs text-amber-400">
          The gateway on {host} isn't running right now, so it can't answer. Start it on that PC (START_HERE.bat,
          option 4), or pick another PC.
        </p>
      ) : (
        <p className={`text-xs ${fl.muted}`}>Runs on {host}, the PC the machines are cabled to.</p>
      )}
    </div>
  )
}
