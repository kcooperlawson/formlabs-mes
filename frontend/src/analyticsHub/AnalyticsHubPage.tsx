import { useQuery } from '@tanstack/react-query'
import { analyticsApi, type DowntimeReason, type HeatmapCell, type PumpDeviation, type ResinOutput, type TrendPoint, type WeightReading } from '../api/analytics'
import { fl } from '../theme'

const card = fl.card
const tile = fl.tile

const PUMP_COLORS = ['#00D2FF', '#F97316', '#A855F7', '#10B981', '#F59E0B', '#38BDF8', '#FB7185']

function KpiCard({
  title, value, valueColor, trend,
}: {
  title: string
  value: string
  valueColor?: string
  trend: { label: string; tone: 'up' | 'down' | 'neutral' }
}) {
  const toneClass =
    trend.tone === 'up' ? 'bg-[#10B981]/20 text-[#10B981]'
    : trend.tone === 'down' ? 'bg-[#EF4444]/20 text-[#EF4444]'
    : 'bg-white/10 text-[#CBD5E1]'
  return (
    <div className={card}>
      <p className={`text-[0.7rem] font-extrabold uppercase tracking-widest ${fl.muted}`}>{title}</p>
      <p className={`my-1 text-3xl font-black ${valueColor ?? 'text-white'}`}>{value}</p>
      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-extrabold ${toneClass}`}>{trend.label}</span>
    </div>
  )
}

// Production Velocity Stream - the original's plotly area chart, hand-rolled
// as SVG (the house pattern already established in HistoricalPage's TrendLine).
function VelocityArea({ points }: { points: TrendPoint[] }) {
  const w = 600, h = 200, pad = 12
  const maxY = Math.max(...points.map((p) => p.units), 1)
  const stepX = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0
  const coords = points.map((p, i) => {
    const x = pad + i * stepX
    const y = h - pad - (p.units / maxY) * (h - pad * 2)
    return [x, y] as const
  })
  const linePath = coords.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ')
  const areaPath = `${linePath} L${coords[coords.length - 1][0]},${h - pad} L${coords[0][0]},${h - pad} Z`
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 200 }}>
        <path d={areaPath} fill="rgba(0,210,255,0.12)" stroke="none" />
        <path d={linePath} fill="none" stroke="#00D2FF" strokeWidth={3} />
        {coords.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={4} fill="#fff" stroke="#00D2FF" strokeWidth={2} />
        ))}
      </svg>
      <div className={`flex justify-between text-xs ${fl.muted}`}>
        <span>{points[0]?.date}</span>
        <span>{points[points.length - 1]?.date}</span>
      </div>
    </div>
  )
}

// Formulation Output - a donut built from stroke-dasharray arcs sharing the
// same resin colours used everywhere else a resin is named.
function Donut({ data, total }: { data: ResinOutput[]; total: number }) {
  const size = 180, r = 62, cx = size / 2, cy = size / 2
  const circumference = 2 * Math.PI * r
  let acc = 0
  const segments = data.map((d) => {
    const frac = total > 0 ? d.units / total : 0
    const dash = frac * circumference
    const seg = { ...d, dash, offset: acc }
    acc += dash
    return seg
  })
  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <g transform={`rotate(-90 ${cx} ${cy})`}>
            {segments.map((s) => (
              <circle
                key={s.resin} cx={cx} cy={cy} r={r} fill="none" stroke={s.color} strokeWidth={22}
                strokeDasharray={`${s.dash} ${circumference - s.dash}`} strokeDashoffset={-s.offset}
              />
            ))}
          </g>
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-black text-white">{total.toLocaleString()}</span>
          <span className={`text-[0.6rem] uppercase ${fl.muted}`}>Total</span>
        </div>
      </div>
      <div className="flex flex-wrap justify-center gap-x-3 gap-y-1 text-xs">
        {data.map((d) => (
          <span key={d.resin} className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
            <span className={fl.muted}>{d.resin}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

// Downtime Pareto - horizontal bars, worst reason on top.
function ParetoBars({ data }: { data: DowntimeReason[] }) {
  const sorted = [...data].sort((a, b) => b.minutes - a.minutes)
  const max = Math.max(...sorted.map((d) => d.minutes), 1)
  return (
    <div className="flex flex-col gap-2">
      {sorted.map((d) => (
        <div key={d.reason} className="flex items-center gap-2 text-xs">
          <span className={`w-28 shrink-0 truncate ${fl.muted}`}>{d.reason}</span>
          <div className="h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
            <div className="h-full rounded bg-[#A855F7]" style={{ width: `${(d.minutes / max) * 100}%` }} />
          </div>
          <span className="w-14 shrink-0 text-right font-medium text-white">{d.minutes.toFixed(0)}m</span>
        </div>
      ))}
    </div>
  )
}

// Operator Contribution Matrix - top-5 operators x day, teal intensity scale.
function Heatmap({ cells, operators }: { cells: HeatmapCell[]; operators: string[] }) {
  const dates = Array.from(new Set(cells.map((c) => c.date))).sort()
  const max = Math.max(...cells.map((c) => c.units), 1)
  const lookup = new Map(cells.map((c) => [`${c.operator}|${c.date}`, c.units]))
  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th></th>
            {dates.map((d) => (
              <th key={d} className={`px-1 text-[0.6rem] font-normal ${fl.muted}`}>{d.slice(5)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {operators.map((op) => (
            <tr key={op}>
              <td className={`whitespace-nowrap pr-2 text-xs ${fl.muted}`}>{op}</td>
              {dates.map((d) => {
                const v = lookup.get(`${op}|${d}`) ?? 0
                const t = v / max
                return (
                  <td
                    key={d} title={`${op} · ${d}: ${v}`}
                    style={{ width: 28, height: 28, borderRadius: 4, background: `rgba(45, 212, 191, ${0.08 + t * 0.85})` }}
                  />
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// Fill weight scatter - deviation from target over time, coloured by pump,
// out-of-band readings rendered as a diamond overlay (a status colour alone
// gets lost among the in-band points, and the exceptions are the point).
function WeightScatter({ readings }: { readings: WeightReading[] }) {
  const w = 600, h = 220, pad = 24
  const sorted = [...readings].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
  const maxAbs = Math.max(...sorted.map((r) => Math.abs(r.deviation_g)), 1)
  const stepX = sorted.length > 1 ? (w - pad * 2) / (sorted.length - 1) : 0
  const pumps = Array.from(new Set(sorted.map((r) => r.pump_station)))
  const colorFor = (pump: string) => PUMP_COLORS[pumps.indexOf(pump) % PUMP_COLORS.length]
  const yFor = (dev: number) => h / 2 - (dev / maxAbs) * (h / 2 - pad)
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: 220 }}>
        <line x1={pad} y1={h / 2} x2={w - pad} y2={h / 2} stroke="#64748B" strokeDasharray="4 4" />
        <text x={w - pad} y={h / 2 - 6} textAnchor="end" fontSize={10} fill="#94A3B8">target</text>
        {sorted.map((r, i) => {
          const x = pad + i * stepX
          const y = yFor(r.deviation_g)
          const outside = r.status === 'over' || r.status === 'under'
          return outside ? (
            <rect
              key={i} x={x - 6} y={y - 6} width={12} height={12} fill="none" stroke="#F87171" strokeWidth={2}
              transform={`rotate(45 ${x} ${y})`}
            />
          ) : (
            <circle key={i} cx={x} cy={y} r={5} fill={colorFor(r.pump_station)} opacity={0.75} />
          )
        })}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
        {pumps.map((p) => (
          <span key={p} className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: colorFor(p) }} />
            <span className={fl.muted}>{p}</span>
          </span>
        ))}
        {sorted.some((r) => r.status === 'over' || r.status === 'under') && (
          <span className="flex items-center gap-1">
            <span className="h-2.5 w-2.5 rotate-45 border-2 border-[#F87171]" />
            <span className={fl.muted}>outside band</span>
          </span>
        )}
      </div>
    </div>
  )
}

// Per-pump mean deviation, centred at zero - running heavy (orange, costs
// resin) and running light (blue) get different colours on purpose.
function PumpDeviationBars({ data }: { data: PumpDeviation[] }) {
  const maxAbs = Math.max(...data.map((d) => Math.abs(d.mean_deviation)), 1)
  return (
    <div className="flex flex-col gap-2">
      {data.map((d) => {
        const over = d.mean_deviation > 0
        const widthPct = (Math.abs(d.mean_deviation) / maxAbs) * 50
        return (
          <div key={d.pump_station} className="flex items-center gap-2 text-xs">
            <span className={`w-28 shrink-0 truncate ${fl.muted}`}>{d.pump_station}</span>
            <div className="relative h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
              <div className="absolute inset-y-0 left-1/2 w-px bg-[#64748B]" />
              <div
                className={`absolute inset-y-0 rounded ${over ? 'bg-[#EA580C]' : 'bg-[#38BDF8]'}`}
                style={over ? { left: '50%', width: `${widthPct}%` } : { right: '50%', width: `${widthPct}%` }}
              />
            </div>
            <span className="w-16 shrink-0 text-right font-medium text-white">
              {d.mean_deviation > 0 ? '+' : ''}{d.mean_deviation.toFixed(1)}g
            </span>
          </div>
        )
      })}
    </div>
  )
}

// Nexus Analytics, ported from pages/Analytics_Hub.py - the rolling 7-day
// KPI/trend/heatmap dashboard, plus the fill-weight give-away panel. The
// live ticker bar recomputes server-side on every poll, so a 15s refetch
// keeps it visibly "ticking" without hammering the API.
export function AnalyticsHubPage() {
  const query = useQuery({
    queryKey: ['analytics-overview'],
    queryFn: () => analyticsApi.overview(),
    refetchInterval: 15_000,
  })
  const data = query.data
  if (!data) {
    return <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>Loading analytics...</p>
  }

  const { kpis, live_ticker, velocity_trend, formulation_output, downtime_pareto, operator_matrix, top_operators, fill_weight } = data
  const pourTone: 'up' | 'down' = kpis.pour_delta_pct >= 0 ? 'up' : 'down'
  const pourArrow = kpis.pour_delta_pct >= 0 ? '▲' : '▼'

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className={fl.heading}>🌌 Nexus Analytics</h1>
        <span className="rounded-lg border border-[#A855F7]/30 bg-[#A855F7]/10 px-3 py-1.5 text-xs font-bold uppercase tracking-widest text-[#A78BFA]">
          Rolling 7-Day Intelligence
        </span>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-[#00D2FF]/20 bg-[#00D2FF]/5 px-5 py-3">
        <div>
          <p className="text-[0.7rem] font-extrabold uppercase tracking-widest text-[#00D2FF]">Live Daily Expectation (Ticking)</p>
          <p className="text-2xl font-black text-white">{live_ticker.expected_now_l.toLocaleString()} L</p>
        </div>
        <div className="text-right">
          <p className="text-[0.7rem] font-extrabold uppercase tracking-widest text-[#A855F7]">Self-Adjusting Daily Projection</p>
          <p className="text-2xl font-black text-white">{live_ticker.projected_daily_l.toLocaleString()} L</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard
          title="Total Units Poured" value={kpis.total_poured_7d.toLocaleString()}
          trend={{ label: `${pourArrow} ${Math.abs(kpis.pour_delta_pct).toFixed(1)}% vs Prev Week`, tone: pourTone }}
        />
        <KpiCard
          title="Quality Yield (FPY)" value={`${kpis.yield_7d.toFixed(2)}%`} valueColor="text-[#10B981]"
          trend={{ label: `Target: ${kpis.yield_target_pct}%`, tone: 'neutral' }}
        />
        <KpiCard
          title="Total Scrap Volume" value={kpis.total_scrap_7d.toLocaleString()} valueColor="text-[#F59E0B]"
          trend={{ label: 'Lost Units', tone: 'down' }}
        />
        <KpiCard
          title="Accumulated Downtime" value={`${kpis.downtime_hours_7d.toFixed(1)}h`} valueColor="text-[#A855F7]"
          trend={{ label: `${kpis.downtime_minutes_7d} Minutes Logged`, tone: 'neutral' }}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className={`${card} lg:col-span-2`}>
          <p className="mb-2 text-sm font-semibold text-white">📈 Production Velocity Stream</p>
          {velocity_trend.length > 0 ? (
            <VelocityArea points={velocity_trend} />
          ) : (
            <p className={`py-8 text-center text-sm ${fl.muted}`}>No pouring data available for the last 7 days.</p>
          )}
        </div>
        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">🧪 Formulation Output</p>
          {formulation_output.length > 0 ? (
            <Donut data={formulation_output} total={kpis.total_poured_7d} />
          ) : (
            <p className={`py-8 text-center text-sm ${fl.muted}`}>No pouring data available for the last 7 days.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">⚠️ Downtime Pareto</p>
          {downtime_pareto.length > 0 ? (
            <ParetoBars data={downtime_pareto} />
          ) : (
            <p className={`py-8 text-center text-sm ${fl.muted}`}>🎉 No downtime events logged in the last 7 days!</p>
          )}
        </div>
        <div className={`${card} lg:col-span-2`}>
          <p className="mb-2 text-sm font-semibold text-white">👥 Operator Contribution Matrix</p>
          {operator_matrix.length > 0 ? (
            <Heatmap cells={operator_matrix} operators={top_operators} />
          ) : (
            <p className={`py-8 text-center text-sm ${fl.muted}`}>Insufficient data for matrix.</p>
          )}
        </div>
      </div>

      <div className={card}>
        <p className="mb-3 text-sm font-semibold text-white">⚖️ Fill weight</p>
        {!fill_weight.has_readings ? (
          <p className={`text-sm ${fl.muted}`}>
            No check weights recorded yet. The pouring form has an optional{' '}
            <strong className="text-[#CBD5E1]">Check weight (g)</strong> box — one reading an hour from any pump is
            enough to show where that pump is sitting in its tolerance window, and how much resin is being given
            away above target.
          </p>
        ) : (
          <>
            <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className={tile}>
                <p className="text-lg font-semibold text-white">{fill_weight.samples.toLocaleString()}</p>
                <p className={`text-xs ${fl.muted}`}>Readings taken</p>
              </div>
              <div className={tile}>
                <p className="text-lg font-semibold text-white">{fill_weight.in_band_pct}</p>
                <p className={`text-xs ${fl.muted}`}>In band</p>
              </div>
              <div className={tile}>
                <p className="text-lg font-semibold text-white">
                  {fill_weight.mean_deviation > 0 ? '+' : ''}{fill_weight.mean_deviation.toFixed(1)} g
                </p>
                <p className={`text-xs ${fl.muted}`}>Mean deviation</p>
              </div>
              <div className={tile}>
                <p className="text-lg font-semibold text-white">
                  {fill_weight.kg_above_target > 0 ? '+' : ''}{fill_weight.kg_above_target.toFixed(1)} kg
                </p>
                <p className={`text-xs ${fl.muted}`}>Resin above target</p>
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <WeightScatter readings={fill_weight.scatter} />
              </div>
              <div>
                <PumpDeviationBars data={fill_weight.by_pump} />
                {fill_weight.worst_pump_note && (
                  <p className={`mt-3 text-xs ${fl.muted}`}>{fill_weight.worst_pump_note}</p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
