import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { devicesApi, type DeviceRow } from '../api/devices'
import { fl } from '../theme'

const card = fl.card
const select = fl.select
const input = fl.input

function TrendLine({ points }: { points: { timestamp: string; value_numeric: number }[] }) {
  const w = 600, h = 160, pad = 10
  const maxY = Math.max(...points.map((p) => p.value_numeric), 1)
  const minY = Math.min(...points.map((p) => p.value_numeric), 0)
  const range = maxY - minY || 1
  const stepX = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0
  const coords = points.map((p, i) => {
    const x = pad + i * stepX
    const y = h - pad - ((p.value_numeric - minY) / range) * (h - pad * 2)
    return [x, y] as const
  })
  const path = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 160 }}>
      <path d={path} fill="none" stroke="#00D2FF" strokeWidth={2} />
      {coords.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={2.5} fill="#00D2FF" />)}
    </svg>
  )
}

export function ReadingsTab({ devices }: { devices: DeviceRow[] }) {
  const [deviceId, setDeviceId] = useState<number | ''>(devices[0]?.id ?? '')
  const [hours, setHours] = useState(4)
  const query = useQuery({
    queryKey: ['device-readings', deviceId, hours],
    queryFn: () => devicesApi.readings(deviceId as number, hours),
    enabled: deviceId !== '',
  })

  if (devices.length === 0) {
    return <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>No devices registered yet.</p>
  }

  const readings = query.data ?? []
  const byMetric = new Map<string, { timestamp: string; value_numeric: number }[]>()
  for (const r of readings) {
    if (r.value_numeric == null) continue
    const arr = byMetric.get(r.metric) ?? []
    arr.push({ timestamp: r.timestamp, value_numeric: r.value_numeric })
    byMetric.set(r.metric, arr)
  }
  for (const arr of byMetric.values()) arr.reverse()

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[2fr_1fr]">
        <select className={select} value={deviceId} onChange={(e) => setDeviceId(Number(e.target.value))}>
          {devices.map((d) => <option key={d.id} value={d.id}>{d.device_name}</option>)}
        </select>
        <label className={`flex items-center gap-2 text-sm ${fl.muted}`}>
          Look back
          <input className={`${input} w-20`} type="number" min={1} max={72} value={hours} onChange={(e) => setHours(Number(e.target.value))} />
          hours
        </label>
      </div>

      {readings.length === 0 ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>No readings yet for this device in that window — check that the gateway process is running.</p>
      ) : (
        <>
          {Array.from(byMetric.entries()).map(([metric, points]) => (
            <div key={metric} className={card}>
              <p className="mb-2 text-sm font-semibold text-white">{metric}</p>
              <TrendLine points={points} />
            </div>
          ))}
          <div className={card}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className={fl.tableHead}>
                  <tr><th className="py-1 pr-2">Timestamp</th><th className="py-1 pr-2">Metric</th><th className="py-1 pr-2">Value</th></tr>
                </thead>
                <tbody>
                  {readings.slice(0, 100).map((r, i) => (
                    <tr key={i} className={fl.tableRow}>
                      <td className="py-1 pr-2 whitespace-nowrap text-[#CBD5E1]">{new Date(r.timestamp).toLocaleString()}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{r.metric}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{r.value_numeric ?? r.value_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
