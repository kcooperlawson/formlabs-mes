import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { historicalApi } from '../api/historical'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

const tile = fl.tile
const card = fl.card
const select = fl.select

const HORIZONS = [
  ['7d', 'Past 7 Days'],
  ['30d', 'Past 30 Days'],
  ['ytd', 'Year to Date'],
  ['all', 'All Time'],
] as const

function TrendLine({ points }: { points: { date: string; bottles_filled: number }[] }) {
  const w = 600
  const h = 180
  const pad = 10
  const maxY = Math.max(...points.map((p) => p.bottles_filled), 1)
  const stepX = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0
  const coords = points.map((p, i) => {
    const x = pad + i * stepX
    const y = h - pad - (p.bottles_filled / maxY) * (h - pad * 2)
    return [x, y] as const
  })
  const path = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ')
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 180 }}>
        <path d={path} fill="none" stroke="#00D2FF" strokeWidth={2} />
        {coords.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={3} fill="#00D2FF" />
        ))}
      </svg>
      <div className={`flex justify-between text-xs ${fl.muted}`}>
        <span>{points[0]?.date}</span>
        <span>{points[points.length - 1]?.date}</span>
      </div>
    </div>
  )
}

function BarList({ data }: { data: { operator: string; bottles_filled: number }[] }) {
  const max = Math.max(...data.map((d) => d.bottles_filled), 1)
  return (
    <div className="flex flex-col gap-2">
      {data.map((d) => (
        <div key={d.operator} className="flex items-center gap-2 text-xs">
          <span className="w-28 shrink-0 truncate text-[#CBD5E1]"><Drill f={{ operator: d.operator }}>{d.operator}</Drill></span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
            <div className="h-full rounded bg-[#EA580C]" style={{ width: `${(d.bottles_filled / max) * 100}%` }} />
          </div>
          <span className="w-12 shrink-0 text-right font-medium text-white">{d.bottles_filled}</span>
        </div>
      ))}
    </div>
  )
}

// Historical Plant Analytics, ported from pages/Mgr_Historical.py - output,
// scrap and yield trends over a time horizon, filterable by resin/operator.
export function HistoricalPage() {
  const [horizon, setHorizon] = useState<(typeof HORIZONS)[number][0]>('7d')
  const [resin, setResin] = useState('All Resins')
  const [operator, setOperator] = useState('All Operators')

  const query = useQuery({
    queryKey: ['historical', horizon, resin, operator],
    queryFn: () => historicalApi.get(horizon, resin, operator),
  })
  const data = query.data

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>📈 Historical Plant Analytics &amp; Production Trends</h1>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <div>
          <label className={`mb-1 block ${fl.label}`}>📅 Time Horizon</label>
          <select className={select} value={horizon} onChange={(e) => setHorizon(e.target.value as (typeof HORIZONS)[number][0])}>
            {HORIZONS.map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={`mb-1 block ${fl.label}`}>🧪 Resin Filter</label>
          <select className={select} value={resin} onChange={(e) => setResin(e.target.value)}>
            <option>All Resins</option>
            {data?.filters.resins.map((r) => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div>
          <label className={`mb-1 block ${fl.label}`}>👤 Operator Filter</label>
          <select className={select} value={operator} onChange={(e) => setOperator(e.target.value)}>
            <option>All Operators</option>
            {data?.filters.operators.map((o) => <option key={o}>{o}</option>)}
          </select>
        </div>
      </div>

      {!data || (data.totals.total_poured === 0 && data.totals.total_packed === 0) ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
          📈 Nothing logged in this range. Historical trends compare output, scrap and yield over time, so they
          need at least a few days of logs before the shape means anything. Widen the date range, or clear the
          operator and resin filters above.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.total_poured.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Total Units Poured</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.total_packed.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Total Units Packed</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.total_scrap.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Total Scrap Units</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.yield_pct.toFixed(1)}%</p>
              <p className={`text-xs ${fl.muted}`}>Average Yield</p>
            </div>
          </div>

          {data.trend.length > 0 && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className={card}>
                <p className="mb-2 text-sm font-semibold text-white">Units Poured Over Time</p>
                <TrendLine points={data.trend} />
              </div>
              <div className={card}>
                <p className="mb-2 text-sm font-semibold text-white">Total Output by Operator</p>
                <BarList data={data.by_operator} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
