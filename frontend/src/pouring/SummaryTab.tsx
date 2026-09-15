import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { summaryApi } from '../api/summary'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { fl } from '../theme'

const btn = `w-full ${fl.btn}`
const tile = fl.tile

// Ported from pages/operator_form/summary_tab.py - an opt-in, read-only
// personal breakdown. Nothing here is written anywhere. The original uses
// Plotly for the hourly timeline and by-resin donut; this pilot pass uses
// plain proportional bars instead of pulling in a chart library for two
// small visualizations - the data (server-aggregated in
// api/routers/summary.py) is what has to be exactly right, not the paint.
export function SummaryTab() {
  const [shown, setShown] = useState(false)
  const asOperator = useDebugOperator()
  const query = useQuery({
    queryKey: ['summary', 'today', asOperator],
    queryFn: () => summaryApi.today(asOperator),
    enabled: shown,
  })

  if (!shown) {
    return (
      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-[#CBD5E1]">📊 My Shift Summary</h3>
        <p className={`text-sm ${fl.muted}`}>
          A personal breakdown of today's numbers, generated on demand. Nothing is saved or sent
          anywhere - built fresh from what you've already logged today.
        </p>
        <button className={btn} onClick={() => setShown(true)}>
          📊 View My Shift Summary
        </button>
      </div>
    )
  }

  const data = query.data

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <p className={`text-sm ${fl.muted}`}>Today so far - tap again any time.</p>
        <button className={fl.btnSecondary} onClick={() => setShown(false)}>
          Hide
        </button>
      </div>

      {!data ? null : !data.has_logs_today ? (
        <p className={`${fl.card} text-center text-sm ${fl.muted}`}>
          📭 Nothing logged yet today. Come back once you've poured, packed, or logged something.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.units.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Units</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.scrap.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Scrap</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.yield_pct.toFixed(1)}%</p>
              <p className={`text-xs ${fl.muted}`}>Yield</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.logs_submitted.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Logs</p>
            </div>
          </div>

          {!data.has_output_logs ? (
            <p className={`${fl.card} text-center text-sm ${fl.muted}`}>
              📭 No output logs yet today. The breakdown below fills in once you've submitted one.
            </p>
          ) : (
            <>
              <div>
                <h4 className={`mb-1 text-xs font-semibold uppercase tracking-wide ${fl.muted}`}>
                  ⏱️ Hourly Timeline
                </h4>
                <div className="flex flex-col gap-1">
                  {data.hourly_timeline.map((h) => {
                    const max = Math.max(...data.hourly_timeline.map((p) => p.units), 1)
                    return (
                      <div key={h.hour} className="flex items-center gap-2 text-xs">
                        <span className={`w-12 shrink-0 ${fl.muted}`}>
                          {new Date(h.hour).toLocaleTimeString([], { hour: 'numeric' })}
                        </span>
                        <div className="h-3 flex-1 overflow-hidden rounded bg-[#0F172A]">
                          <div className="h-full bg-[#EA580C]" style={{ width: `${(h.units / max) * 100}%` }} />
                        </div>
                        <span className="w-10 shrink-0 text-right text-[#CBD5E1]">{h.units}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div>
                <h4 className={`mb-1 text-xs font-semibold uppercase tracking-wide ${fl.muted}`}>
                  🧪 By Formulation
                </h4>
                <div className="flex flex-col gap-1">
                  {data.by_resin.map((r) => {
                    const total = data.by_resin.reduce((sum, p) => sum + p.units, 0) || 1
                    return (
                      <div key={r.resin} className="flex items-center gap-2 text-xs">
                        <span className="w-32 shrink-0 truncate text-[#CBD5E1]">{r.resin}</span>
                        <div className="h-3 flex-1 overflow-hidden rounded bg-[#0F172A]">
                          <div className="h-full bg-violet-500" style={{ width: `${(r.units / total) * 100}%` }} />
                        </div>
                        <span className="w-10 shrink-0 text-right text-[#CBD5E1]">{r.units}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
