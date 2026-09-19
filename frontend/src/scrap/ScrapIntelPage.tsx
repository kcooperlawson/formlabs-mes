import { useQuery } from '@tanstack/react-query'
import { scrapIntelApi } from '../api/scrapIntel'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

const tile = fl.tile
const card = fl.card

// Deterministic hue per downtime reason, so the same reason keeps the same
// slice colour across reloads without needing a stored palette the way
// resins have one - there's no existing "reason colour" identity to reuse.
function hueFor(label: string): number {
  let h = 0
  for (let i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) >>> 0
  return h % 360
}

function Donut({ data }: { data: { reason: string; duration_min: number }[] }) {
  const total = data.reduce((s, d) => s + d.duration_min, 0)
  if (total <= 0) return null
  let acc = 0
  const stops = data.map((d) => {
    const start = (acc / total) * 360
    acc += d.duration_min
    const end = (acc / total) * 360
    return `hsl(${hueFor(d.reason)} 65% 55%) ${start}deg ${end}deg`
  })
  return (
    <div className="flex items-center gap-4">
      <div
        className="h-32 w-32 shrink-0 rounded-full"
        style={{ background: `conic-gradient(${stops.join(', ')})` }}
      />
      <div className="flex flex-col gap-1 text-xs">
        {data.map((d) => (
          <div key={d.reason} className="flex items-center gap-2">
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: `hsl(${hueFor(d.reason)} 65% 55%)` }}
            />
            <span className="text-[#CBD5E1]">{d.reason}</span>
            <span className={fl.muted}>
              {d.duration_min} min ({((d.duration_min / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function BarList({ data }: { data: { resin_type: string; bottles_filled: number; color: string }[] }) {
  const max = Math.max(...data.map((d) => d.bottles_filled), 1)
  return (
    <div className="flex flex-col gap-2">
      {data
        .slice()
        .sort((a, b) => b.bottles_filled - a.bottles_filled)
        .map((d) => (
          <div key={d.resin_type} className="flex items-center gap-2 text-xs">
            <span className="w-32 shrink-0 truncate text-[#CBD5E1]"><Drill f={{ resin: d.resin_type }}>{d.resin_type}</Drill></span>
            <div className="h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
              <div
                className="h-full rounded"
                style={{ width: `${(d.bottles_filled / max) * 100}%`, backgroundColor: d.color }}
              />
            </div>
            <span className="w-12 shrink-0 text-right font-medium">{d.bottles_filled}</span>
          </div>
        ))}
    </div>
  )
}

// Quality Ops Canvas, ported from pages/Mgr_Scrap_Intel.py - scrap totals,
// output by formulation, and downtime by reason. All-time totals, same as
// the original page (no date filter there either).
export function ScrapIntelPage() {
  const query = useQuery({ queryKey: ['scrap-intel'], queryFn: scrapIntelApi.get })
  const data = query.data

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>📊 Quality Ops Canvas — Scrap Reject &amp; FPY Engine</h1>

      {data && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.empty_scrap} units</p>
            <p className={`text-xs ${fl.muted}`}>Empty Bottles Scrapped</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.filled_scrap} units</p>
            <p className={`text-xs ${fl.muted}`}>Filled Bottles Scrapped</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.total_scrap} units</p>
            <p className={`text-xs ${fl.muted}`}>Total Scrap Volume</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-emerald-400">Optimal</p>
            <p className={`text-xs ${fl.muted}`}>Yield Severity Status (0% Resin Loss)</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">Output by Formulation</p>
          {!data || data.by_resin.length === 0 ? (
            <p className={`py-6 text-center text-sm ${fl.muted}`}>
              🧪 No production logged in this window. Output by formulation appears here once operators start
              logging pouring.
            </p>
          ) : (
            <BarList data={data.by_resin} />
          )}
        </div>

        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">Downtime Reasons</p>
          {!data || data.downtime_by_reason.length === 0 ? (
            <p className={`py-6 text-center text-sm ${fl.muted}`}>
              ⏱️ No downtime recorded. Every stoppage an operator logs is broken down here by reason.
            </p>
          ) : (
            <Donut data={data.downtime_by_reason} />
          )}
        </div>
      </div>
    </div>
  )
}
