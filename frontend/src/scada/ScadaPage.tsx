import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useState } from 'react'
import { scadaApi, type ScadaQuery } from '../api/scada'
import { useFlashOnChange } from '../hooks/useFlashOnChange'
import { useRealtimeInvalidate } from '../hooks/useRealtimeInvalidate'
import { Skeleton, StatCardSkeleton } from '../shell/Skeleton'
import { Odometer } from '../tv/PrintBuild'
import { fl } from '../theme'
import type { DrillFilter } from '../api/drill'
import { Drill } from '../drill/DrillContext'

function isoDay(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** The dashboard's own filters, as a drill filter - so clicking a card shows
 *  exactly the rows that card was added up from. */
function scadaDrill(q: ScadaQuery, activeShift?: string): DrillFilter {
  const today = new Date()
  const back = (days: number) => isoDay(new Date(today.getFullYear(), today.getMonth(), today.getDate() - days))
  const f: DrillFilter = {}
  if (q.horizon === 'live') {
    f.date_from = f.date_to = isoDay(today)
    if (activeShift) f.shift = activeShift
  } else if (q.horizon === 'specific') {
    f.date_from = f.date_to = q.date || isoDay(today)
  } else if (q.horizon === 'week') {
    f.date_from = back(7)
  } else if (q.horizon === 'month') {
    f.date_from = back(30)
  }
  if (q.pump && q.pump !== 'All Pumps') f.pump = q.pump
  if (q.resin && q.resin !== 'All Resins') f.resin = q.resin
  if (q.operator && q.operator !== 'All Operators') f.operator = q.operator
  if (q.shift && q.shift !== 'All Shifts') f.shift = q.shift
  // "All Time, every pump" is still a real question; the server just needs
  // one field to know it was asked on purpose.
  if (!f.date_from && !f.pump && !f.resin && !f.operator) f.date_from = '2000-01-01'
  return f
}

const card = fl.card
const select = fl.select
const label = fl.label

const HORIZONS: { value: ScadaQuery['horizon']; label: string }[] = [
  { value: 'live', label: '⚡ Live Today' },
  { value: 'specific', label: '📅 Specific Day' },
  { value: 'week', label: '📆 Past 7 Days' },
  { value: 'month', label: '📊 Past 30 Days' },
  { value: 'all', label: '🌐 All Time' },
]

// Live SCADA - the manager/admin plant dashboard, ported from Home.py's
// post-login body. api/routers/scada.py computes everything server-side
// (the same math Home.py itself ran); this component is presentation plus
// the filter controls. 10s polling replaces Home.py's
// @st.fragment(run_every="10s") - the same refresh cadence, without a
// full-page rerun to get it.
export function ScadaPage() {
  const [query, setQuery] = useState<ScadaQuery>({
    horizon: 'live', pump: 'All Pumps', resin: 'All Resins', operator: 'All Operators',
    shift: 'All Shifts', sort: 'newest',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['scada', 'overview', query],
    queryFn: () => scadaApi.overview(query),
    refetchInterval: 10_000,
  })

  // Belt-and-suspenders with the refetchInterval above: a live pour/pack/
  // downtime push re-fetches immediately instead of waiting up to 10s, and
  // if the socket is ever down the polling above still gets there.
  useRealtimeInvalidate([['scada']])

  const patch = (p: Partial<ScadaQuery>) => setQuery((prev) => ({ ...prev, ...p }))

  // The same "notice the update, not just have it be correct" treatment the
  // KPI cards above already get (see useFlashOnChange) - only meaningful
  // when the newest row is actually sorted to the top, so a row logged
  // while someone's sorted by units or resin doesn't flash something that
  // isn't visually "new" to them.
  const newestTimestamp = query.sort === 'newest' ? data?.log_stream[0]?.timestamp : undefined
  const newestFlash = useFlashOnChange(newestTimestamp)
  const base = scadaDrill(query, data?.pouring?.trajectory?.is_live ? data.pouring.trajectory.active_shift_name : undefined)

  return (
    <div className="flex flex-col gap-4">
        {data?.health && (data.health.is_alarm || data.health.is_warning) && (
          <div
            className={
              data.health.is_alarm
                ? 'rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-sm text-red-300'
                : 'rounded-lg border border-amber-800 bg-amber-950 px-3 py-2 text-sm text-amber-200'
            }
          >
            {data.health.is_alarm ? '🔴' : '🟠'} {data.health.message}
          </div>
        )}

        <details className={card}>
          <summary className="cursor-pointer text-sm font-medium text-white">🔍 Filters and time horizon</summary>
          <div className="mt-3 flex flex-wrap gap-3">
            <div>
              <label className={label}>Time Horizon</label>
              <select className={select} value={query.horizon} onChange={(e) => patch({ horizon: e.target.value as ScadaQuery['horizon'] })}>
                {HORIZONS.map((h) => (
                  <option key={h.value} value={h.value}>{h.label}</option>
                ))}
              </select>
            </div>
            {query.horizon === 'specific' && (
              <div>
                <label className={label}>Date</label>
                <select className={select} value={query.date ?? ''} onChange={(e) => patch({ date: e.target.value })}>
                  {(data?.filters.dates ?? []).map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className={label}>Pump Station</label>
              <select className={select} value={query.pump} onChange={(e) => patch({ pump: e.target.value })}>
                <option>All Pumps</option>
                {(data?.filters.pumps ?? []).map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={label}>Resin Formula</label>
              <select className={select} value={query.resin} onChange={(e) => patch({ resin: e.target.value })}>
                <option>All Resins</option>
                {(data?.filters.resins ?? []).map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={label}>Operator</label>
              <select className={select} value={query.operator} onChange={(e) => patch({ operator: e.target.value })}>
                <option>All Operators</option>
                {(data?.filters.operators ?? []).map((o) => (
                  <option key={o}>{o}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={label}>Shift</label>
              <select className={select} value={query.shift} onChange={(e) => patch({ shift: e.target.value })}>
                <option>All Shifts</option>
                {(data?.filters.shifts ?? []).map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
        </details>

        {isLoading || !data ? (
          <>
            <Skeleton className="h-14 w-full" />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => <StatCardSkeleton key={i} />)}
            </div>
          </>
        ) : (
          <>
            <Drill f={base} block className="rounded-lg" title="Every log behind this total">
            <div className={card} style={{ borderLeft: `4px solid ${data.headline_is_live ? '#10B981' : '#64748B'}` }}>
              <p className="text-2xl font-bold text-white">
                <Odometer value={data.headline_liters} uid="hl" /> L
                {data.headline_is_live && (
                  <span className={data.headline_pace_variance_l >= 0 ? 'ml-2 text-emerald-400' : 'ml-2 text-amber-400'}>
                    <Odometer value={Math.abs(data.headline_pace_variance_l)} uid="hlp" /> L{' '}
                    {data.headline_pace_variance_l >= 0 ? 'ahead of' : 'behind'} pace
                  </span>
                )}
              </p>
            </div>
            </Drill>

            {data.pouring && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard label="Volume Output" value={<><Odometer value={data.pouring.liters_output} uid="vo" /> L</>}
                            sub={data.pouring.cart_type_counts.map((c) => `${c.units} ${c.cartridge_type}`).join(' | ') || 'No cartridges logged'}
                            flashKey={data.pouring.liters_output} drill={base} />
                  <StatCard label="Resin Mass Poured" value={<><Odometer value={data.pouring.resin_mass_kg} decimals={1} uid="rm" /> kg</>} flashKey={data.pouring.resin_mass_kg} drill={base} />
                  <StatCard label="Run Velocity" value={<><Odometer value={data.pouring.run_velocity_lh} decimals={1} uid="rv" /> L/h</>} sub={`Target: ${data.pouring.target_rate_lh.toFixed(0)} L/h`} flashKey={data.pouring.run_velocity_lh} drill={base} />
                  <StatCard label="Pouring Yield" value={<><Odometer value={data.pouring.yield_pct} decimals={1} uid="py" />%</>} sub={`${data.pouring.total_scrap} scrap units`} flashKey={data.pouring.yield_pct} drill={base} />
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {data.pouring.trajectory && (
                    <div className={`${card} sm:col-span-2`}>
                      <p className="text-xs font-semibold uppercase tracking-wide text-emerald-400">
                        ⏱️ Live Shift Trajectory — {data.pouring.trajectory.status_badge}
                      </p>
                      {data.pouring.trajectory.is_live ? (
                        <>
                          <p className="mt-1 text-lg font-semibold text-white">{data.pouring.trajectory.active_shift_name}</p>
                          <div className="mt-2 h-2 overflow-hidden rounded bg-[#0F172A]">
                            <div className="h-full bg-emerald-500" style={{ width: `${data.pouring.trajectory.shift_pct}%` }} />
                          </div>
                          <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                            <Metric label="Expected Now" value={data.pouring.trajectory.expected_display} />
                            <Metric label="Projected End" value={`${data.pouring.trajectory.projected_total.toLocaleString(undefined, { maximumFractionDigits: 0 })} L`} />
                            <Metric label="Pace Variance" value={`${data.pouring.trajectory.pace_variance_l >= 0 ? '+' : ''}${data.pouring.trajectory.pace_variance_l.toFixed(0)} L`} />
                            <Metric label="OEE" value={`${data.pouring.trajectory.oee_pct.toFixed(1)}%`} />
                          </div>
                        </>
                      ) : (
                        <p className={`mt-2 text-sm ${fl.muted}`}>
                          No shift is currently running.
                          {data.pouring.trajectory.next_shift_label && ` Next up: ${data.pouring.trajectory.next_shift_label}.`}
                        </p>
                      )}
                    </div>
                  )}
                  <div className={card}>
                    <p className={`mb-2 text-xs font-semibold uppercase tracking-wide ${fl.muted}`}>🔥 Pouring Leaderboard</p>
                    {data.pouring.leaderboard.length === 0 ? (
                      <p className={`text-sm ${fl.muted}`}>No pouring logged.</p>
                    ) : (
                      data.pouring.leaderboard.map((e, i) => (
                        <Drill key={e.operator} f={{ ...base, operator: e.operator }} block className="rounded">
                          <div className="flex justify-between border-b border-[#334155] py-1 text-sm text-[#CBD5E1] last:border-0">
                            <span>#{i + 1} <strong className="text-white">{e.operator}</strong></span>
                            <span className="font-semibold text-sky-400">{e.velocity_lh.toFixed(0)} L/h</span>
                          </div>
                        </Drill>
                      ))
                    )}
                  </div>
                </div>
              </>
            )}

            {data.packing && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard label="Total Units Packed" value={<Odometer value={data.packing.total_packed} uid="tp" />} flashKey={data.packing.total_packed} />
                  <StatCard label="Estimated Skids" value={<Odometer value={data.packing.total_skids_est} decimals={1} uid="es" />} flashKey={data.packing.total_skids_est} />
                  <StatCard label="Packing Velocity" value={<><Odometer value={data.packing.pack_velocity_uh} uid="pv" /> units/h</>} flashKey={data.packing.pack_velocity_uh} />
                  <StatCard label="Unpacked WIP" value={<Odometer value={data.packing.unpacked_wip} uid="uw" />} flashKey={data.packing.unpacked_wip} />
                </div>
                <div className={card}>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-violet-400">📦 Packed by Resin & Lot</p>
                  {data.packing.by_resin_lot.length === 0 ? (
                    <p className={`text-sm ${fl.muted}`}>No packing logged for this filter.</p>
                  ) : (
                    data.packing.by_resin_lot.map((r) => (
                      <div key={`${r.resin}-${r.lot_number}`} className="flex justify-between border-b border-[#334155] py-1 text-sm text-[#CBD5E1] last:border-0">
                        <span><strong className="text-white"><Drill f={{ resin: r.resin }}>{r.resin}</Drill></strong> <span className={fl.muted}>(<Drill f={{ lot: r.lot_number }}>{r.lot_number}</Drill>)</span></span>
                        <span><strong className="text-violet-400">{r.units.toLocaleString()} units</strong> <span className={fl.muted}>({r.skids.toFixed(1)} skids)</span></span>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}

            <div className={card}>
              <div className="mb-2 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-white">{data.log_stream_title}</p>
                  <p className={`text-xs ${fl.muted}`}>Showing {data.log_stream.length} matching records.</p>
                </div>
                <select className={select} value={query.sort} onChange={(e) => patch({ sort: e.target.value as ScadaQuery['sort'] })}>
                  <option value="newest">Newest First</option>
                  <option value="oldest">Oldest First</option>
                  <option value="units">Highest Bottle Count</option>
                  <option value="resin">Resin Name</option>
                </select>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className={fl.tableHead}>
                    <tr>
                      <th className="py-1 pr-2">Time</th>
                      <th className="py-1 pr-2">Type</th>
                      <th className="py-1 pr-2">Operator</th>
                      <th className="py-1 pr-2">Station</th>
                      <th className="py-1 pr-2">Format</th>
                      <th className="py-1 pr-2">Resin</th>
                      <th className="py-1 pr-2 text-right">Units</th>
                      <th className="py-1 pr-2 text-right">Scrap</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.log_stream.slice(0, 100).map((row, i) => (
                      <tr key={i} className={`${fl.tableRow} ${i === 0 && newestFlash ? 'fl-flash' : ''}`}>
                        <td className="py-1 pr-2 whitespace-nowrap text-[#CBD5E1]">{new Date(row.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</td>
                        <td className="py-1 pr-2 text-[#CBD5E1]">{row.log_type}</td>
                        <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ operator: row.operator_name, date_from: row.date, date_to: row.date }}>{row.operator_name}</Drill></td>
                        <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ pump: row.pump_station, date_from: row.date, date_to: row.date }}>{row.pump_station}</Drill></td>
                        <td className="py-1 pr-2 text-[#CBD5E1]">{row.cartridge_type}</td>
                        <td className="py-1 pr-2 text-[#CBD5E1]">
                          <Drill f={{ resin: row.resin_type }}>{row.resin_type}</Drill>
                          {row.lot_number && <> <span className={fl.muted}>·</span> <Drill f={{ lot: row.lot_number }} className={fl.muted}>{row.lot_number}</Drill></>}
                        </td>
                        <td className="py-1 pr-2 text-right text-[#CBD5E1]">{row.bottles_filled}</td>
                        <td className="py-1 pr-2 text-right text-[#CBD5E1]">{row.scrap_empty + row.scrap_filled}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {data.log_stream.length === 0 && (
                  <p className={`py-4 text-center text-sm ${fl.muted}`}>No records match the current filter selection.</p>
                )}
              </div>
            </div>
          </>
        )}
    </div>
  )
}

// flashKey is a plain comparable primitive (the raw number), separate from
// `value` (which is JSX - an Odometer plus a unit suffix) - useFlashOnChange
// needs something it can actually compare across renders.
function StatCard({ label, value, sub, flashKey, drill }: { label: string; value: ReactNode; sub?: string; flashKey?: number; drill?: DrillFilter }) {
  const flashing = useFlashOnChange(flashKey)
  const body = (
    <div className={`${fl.cardHover} ${flashing ? 'fl-flash' : ''}`}>
      <p className={`text-xs font-semibold uppercase tracking-wide ${fl.muted}`}>{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
      {sub && <p className={`text-xs ${fl.muted}`}>{sub}</p>}
    </div>
  )
  return drill ? <Drill f={drill} block className="rounded-lg" title="Every log behind this number">{body}</Drill> : body
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className={`text-xs ${fl.muted}`}>{label}</p>
      <p className="font-semibold text-white">{value}</p>
    </div>
  )
}
