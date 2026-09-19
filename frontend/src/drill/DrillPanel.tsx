import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { cleanlinessApi } from '../api/cleanliness'
import { drillApi, type DrillBreakdownRow, type DrillFilter, type DrillLog, type DrillOut } from '../api/drill'
import { lotVerificationApi } from '../api/lotVerification'
import { fl } from '../theme'
import { Drill, useDrill } from './DrillContext'

// The panel itself. Everything in it is read from /api/drill for the filter on
// top of the stack; every name in it is itself a Drill, so it is always one
// more click to go deeper and Back to come out.

const fmtTime = (iso: string | null) =>
  iso ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
const fmtNum = (n: number) => n.toLocaleString()

function title(f: DrillFilter, data?: DrillOut): string {
  if (f.run_id) return `Run #${f.run_id}${data?.run ? ` — ${data.run.resin_type}` : ''}`
  if (f.reactor) return `Vessel ${f.reactor}`
  if (f.lot) return `Lot ${f.lot}`
  if (f.pump) return f.pump
  if (f.operator) return f.operator
  if (f.resin) return f.resin
  if (f.date_from && f.date_from === f.date_to) return new Date(`${f.date_from}T12:00`).toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })
  if (f.date_from === ALL_TIME) return 'All time'
  if (f.date_from) return `Since ${new Date(`${f.date_from}T12:00`).toLocaleDateString([], { month: 'long', day: 'numeric' })}`
  return 'Everything behind this'
}

/** What an unfiltered "All Time" view sends, so the server knows it was asked on purpose. */
const ALL_TIME = '2000-01-01'

const CHIP_LABEL: Record<string, string> = {
  lot: 'Lot', run_id: 'Run', pump: 'Pump', operator: 'Operator', resin: 'Resin', reactor: 'Vessel',
  shift: 'Shift', date_from: 'From', date_to: 'To',
}

function Section({ label, count, children, open = true }: { label: string; count?: number; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} className={`${fl.card} group`}>
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-[var(--fl-ink)]">
        <span>{label}{count !== undefined && <span className={`ml-2 text-xs ${fl.muted}`}>{count}</span>}</span>
        <span className={`text-sm ${fl.muted} transition group-open:rotate-90`}>›</span>
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  )
}

function Tile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className={fl.tile}>
      <p className={fl.label}>{label}</p>
      <p className="text-xl font-extrabold tabular-nums text-[var(--fl-accent-2)]">{value}</p>
      {sub && <p className={`text-[0.7rem] ${fl.muted}`}>{sub}</p>}
    </div>
  )
}

/** One bar per operator / pump / lot / ... - clicking narrows the current
 *  view to that one, keeping everything else it was already filtered on. */
function Breakdown({ label, rows, narrow }: { label: string; rows: DrillBreakdownRow[]; narrow: (key: string) => DrillFilter }) {
  if (rows.length < 2) return null
  const max = Math.max(...rows.map((r) => r.units), 1)
  return (
    <div>
      <p className={`${fl.label} mb-1`}>By {label}</p>
      <div className="flex flex-col gap-1">
        {rows.slice(0, 12).map((row) => (
          <Drill key={row.key} f={narrow(row.key)} block className="rounded">
            <div className="relative overflow-hidden rounded border border-[var(--fl-border)] px-2 py-1 text-xs">
              <div className="absolute inset-y-0 left-0 bg-[var(--fl-accent)]/20" style={{ width: `${(row.units / max) * 100}%` }} />
              <div className="relative flex justify-between gap-2">
                <span className="truncate text-[var(--fl-ink)]">{row.key}</span>
                <span className="shrink-0 tabular-nums text-[var(--fl-body)]">
                  {fmtNum(row.units)} <span className={fl.muted}>· {row.logs} log{row.logs === 1 ? '' : 's'}</span>
                </span>
              </div>
            </div>
          </Drill>
        ))}
        {rows.length > 12 && <p className={`text-xs ${fl.muted}`}>…and {rows.length - 12} more</p>}
      </div>
    </div>
  )
}

function downloadCsv(logs: DrillLog[], name: string) {
  const cols: (keyof DrillLog)[] = ['timestamp', 'operator_name', 'pump_station', 'shift', 'resin_type', 'cartridge_type',
    'lot_number', 'bottles', 'litres', 'scrap_empty', 'scrap_filled', 'weight_status', 'check_weight_g', 'verify_status', 'notes']
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const csv = [cols.join(','), ...logs.map((l) => cols.map((c) => esc(l[c])).join(','))].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `${name.replace(/[^\w.-]+/g, '_')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const WEIGHT_TONE: Record<string, string> = { in: 'text-emerald-400', under: 'text-amber-400', over: 'text-amber-400' }
const VERIFY_TONE: Record<string, string> = { verified: 'text-emerald-400', fast_path: 'text-emerald-400', mismatch: 'text-red-400', expired: 'text-red-400' }

export function DrillPanel() {
  const drill = useDrill()!
  const f = drill.current!
  const [showAll, setShowAll] = useState(false)
  const query = useQuery({ queryKey: ['drill', f], queryFn: () => drillApi.get(f), staleTime: 15_000 })
  const data = query.data
  const s = data?.summary
  const everyone = data?.scope === 'everyone'

  const narrow = (key: 'operator' | 'pump' | 'resin' | 'lot' | 'shift') => (value: string) => ({ ...f, [key]: value })
  const narrowDay = (value: string) => ({ ...f, date_from: value, date_to: value })
  const withoutKey = (key: string) => {
    const next = { ...f } as Record<string, unknown>
    delete next[key]
    if (key === 'date_from' || key === 'date_to') {
      delete next.date_from
      delete next.date_to
    }
    return next as DrillFilter
  }
  const chips = Object.entries(f).filter(([k, v]) => k !== 'as_operator' && !(k === 'date_to' && f.date_to === f.date_from) && !(k === 'date_from' && v === ALL_TIME))
  const logs = data?.logs ?? []
  const shownLogs = showAll ? logs : logs.slice(0, 50)

  return (
    <div className="fixed inset-0 z-[60] flex justify-end" role="dialog" aria-modal="true" aria-label={title(f, data)}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={drill.close} />
      <aside
        className="relative flex h-full w-full max-w-2xl flex-col border-l border-[var(--fl-border)] bg-[var(--fl-ground)] shadow-2xl"
        style={{ animation: 'fl-drill-in 220ms cubic-bezier(0.22,0.61,0.36,1) both' }}
      >
        <style>{'@keyframes fl-drill-in{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}'}</style>

        {/* ---- header ---- */}
        <div className="flex items-start gap-2 border-b border-[var(--fl-border)] p-3">
          {drill.depth > 1 && (
            <button className={fl.btnSecondary} onClick={drill.back} title="Back">← Back</button>
          )}
          <div className="min-w-0 flex-1">
            <p className={fl.label}>🔎 Everything behind</p>
            <h2 className="truncate text-lg font-extrabold text-[var(--fl-ink)]">{title(f, data)}</h2>
            <div className="mt-1 flex flex-wrap gap-1">
              {chips.map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1 rounded-full border border-[var(--fl-border)] px-2 py-0.5 text-[0.7rem] text-[var(--fl-body)]">
                  {k === 'date_from' && f.date_to === f.date_from ? 'Day' : CHIP_LABEL[k] ?? k}: <strong className="text-[var(--fl-ink)]">{k === 'date_from' && f.date_to === f.date_from ? `${v}` : String(v)}</strong>
                  {chips.length > 1 && (
                    <button className="ml-0.5 text-[var(--fl-muted)] hover:text-[var(--fl-accent-2)]" title="Widen - drop this filter" onClick={() => drill.push(withoutKey(k))}>
                      ×
                    </button>
                  )}
                </span>
              ))}
              {data?.scope === 'self' && <span className="rounded-full bg-[var(--fl-overlay-weak)] px-2 py-0.5 text-[0.7rem] text-[var(--fl-muted)]">your entries only</span>}
            </div>
          </div>
          <button className={fl.btnSecondary} onClick={drill.close} title="Close (Esc)">✕</button>
        </div>

        {/* ---- body ---- */}
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
          {query.isLoading && <p className={`text-sm ${fl.muted}`}>Gathering everything…</p>}
          {query.isError && <p className="text-sm text-red-400">{(query.error as Error).message}</p>}

          {data && s && (
            <>
              {data.run && (
                <div className={fl.card}>
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-[var(--fl-ink)]">
                      Run #{data.run.id} · <Drill f={{ resin: data.run.resin_type }}>{data.run.resin_type}</Drill>
                      {data.run.cartridge_type && <span className={fl.muted}> ({data.run.cartridge_type})</span>}
                    </p>
                    <span className={fl.badge}>{data.run.status}</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--fl-overlay-weak)]">
                    <div className="h-full bg-[var(--fl-accent)]" style={{ width: `${Math.min(100, (data.run.current_units / Math.max(1, data.run.target_units)) * 100)}%` }} />
                  </div>
                  <p className={`mt-1 text-xs ${fl.muted}`}>
                    {fmtNum(data.run.current_units)} of {fmtNum(data.run.target_units)} ·{' '}
                    <Drill f={{ pump: data.run.pump_station }}>{data.run.pump_station}</Drill> ·{' '}
                    <Drill f={{ operator: data.run.assigned_operator }}>{data.run.assigned_operator}</Drill>
                    {data.run.lot_number && <> · lot <Drill f={{ lot: data.run.lot_number }}>{data.run.lot_number}</Drill></>}
                    {data.run.reactor_id && <> · from <Drill f={{ reactor: data.run.reactor_id }}>{data.run.reactor_id}</Drill></>}
                    {' '}· started {fmtTime(data.run.created_at)}
                  </p>
                  {data.run.notes && <p className="mt-1 text-xs text-[var(--fl-body)]">📝 {data.run.notes}</p>}
                </div>
              )}

              {data.reactor && (
                <div className={fl.card}>
                  <p className="text-sm font-semibold text-[var(--fl-ink)]">
                    🛢️ {data.reactor.name}
                    {data.reactor.asset_tag && <span className={fl.muted}> · {data.reactor.asset_tag}</span>}
                    {data.reactor.bay_marker && <span className={fl.muted}> · bay {data.reactor.bay_marker}</span>}
                  </p>
                  <p className={`text-xs ${fl.muted}`}>
                    {fmtNum(data.reactor.capacity_l)} L · {data.reactor.status}
                    {data.reactor.current_resin && <> · holds <Drill f={{ resin: data.reactor.current_resin }}>{data.reactor.current_resin}</Drill></>}
                    {data.reactor.assigned_pump && <> · feeds <Drill f={{ pump: data.reactor.assigned_pump }}>{data.reactor.assigned_pump}</Drill></>}
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Tile label="Units" value={fmtNum(s.units)} sub={`${s.logs} log${s.logs === 1 ? '' : 's'}`} />
                <Tile label="Litres" value={fmtNum(s.litres)} />
                <Tile label="Scrap" value={fmtNum(s.scrap_empty + s.scrap_filled)} sub={`${s.scrap_empty} empty · ${s.scrap_filled} filled`} />
                {data.downtime.length > 0
                  ? <Tile label="Downtime" value={`${fmtNum(data.downtime_min)}m`} sub={`${data.downtime.length} stop${data.downtime.length === 1 ? '' : 's'}`} />
                  : <Tile label="Span" value={s.first_at ? new Date(s.first_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '—'} sub={s.last_at ? `to ${fmtTime(s.last_at)}` : undefined} />}
              </div>

              {(Object.keys(s.weight).length > 0 || Object.keys(s.verify).length > 0) && (
                <div className="flex flex-wrap gap-2 text-xs">
                  {Object.entries(s.weight).map(([k, n]) => (
                    <span key={`w${k}`} className={`rounded border border-[var(--fl-border)] px-2 py-0.5 ${WEIGHT_TONE[k] ?? fl.muted}`}>⚖️ {k}: {n}</span>
                  ))}
                  {Object.entries(s.verify).map(([k, n]) => (
                    <span key={`v${k}`} className={`rounded border border-[var(--fl-border)] px-2 py-0.5 ${VERIFY_TONE[k] ?? fl.muted}`}>🔖 {k.replace('_', ' ')}: {n}</span>
                  ))}
                </div>
              )}

              {s.logs === 0 && data.runs.length === 0 && data.batches.length === 0 && data.downtime.length === 0 && (
                <p className={`text-sm ${fl.muted}`}>Nothing on record for this yet.</p>
              )}

              {s.logs > 0 && (
                <Section label="Breakdown">
                  <div className="grid gap-3 sm:grid-cols-2">
                    {everyone && <Breakdown label="operator" rows={s.breakdown.operator} narrow={narrow('operator')} />}
                    <Breakdown label="pump" rows={s.breakdown.pump} narrow={narrow('pump')} />
                    <Breakdown label="lot" rows={s.breakdown.lot} narrow={narrow('lot')} />
                    <Breakdown label="resin" rows={s.breakdown.resin} narrow={narrow('resin')} />
                    <Breakdown label="day" rows={s.breakdown.day} narrow={narrowDay} />
                    <Breakdown label="shift" rows={s.breakdown.shift} narrow={narrow('shift')} />
                  </div>
                  {[s.breakdown.operator, s.breakdown.pump, s.breakdown.lot, s.breakdown.resin, s.breakdown.day, s.breakdown.shift].every((r) => r.length < 2) && (
                    <p className={`text-xs ${fl.muted}`}>All of it is one operator, one pump, one lot, one resin, on one day.</p>
                  )}
                </Section>
              )}

              {logs.length > 0 && (
                <Section label="Every log" count={s.logs}>
                  <div className="mb-2 flex justify-end">
                    <button className={fl.btnSecondary} onClick={() => downloadCsv(logs, title(f, data))}>⬇ CSV</button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className={fl.tableHead}>
                        <tr>
                          <th className="py-1 pr-2">When</th>
                          {everyone && <th className="py-1 pr-2">Operator</th>}
                          <th className="py-1 pr-2">Pump</th>
                          <th className="py-1 pr-2">Resin</th>
                          <th className="py-1 pr-2">Lot</th>
                          <th className="py-1 pr-2 text-right">Count</th>
                          <th className="py-1 pr-2">Checks</th>
                        </tr>
                      </thead>
                      <tbody>
                        {shownLogs.map((l) => (
                          <tr key={l.id} className={fl.tableRow} title={[l.notes, l.pour_note].filter(Boolean).join(' · ') || undefined}>
                            <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{fmtTime(l.timestamp)}</td>
                            {everyone && <td className="py-1 pr-2 whitespace-nowrap"><Drill f={{ operator: l.operator_name }}>{l.operator_name}</Drill></td>}
                            <td className="py-1 pr-2 whitespace-nowrap"><Drill f={{ pump: l.pump_station }}>{l.pump_station}</Drill></td>
                            <td className="py-1 pr-2 whitespace-nowrap"><Drill f={{ resin: l.resin_type }}>{l.resin_type}</Drill></td>
                            <td className="py-1 pr-2 whitespace-nowrap"><Drill f={{ lot: l.lot_number }}>{l.lot_number || '—'}</Drill></td>
                            <td className="py-1 pr-2 text-right tabular-nums text-[var(--fl-ink)]">
                              {fmtNum(l.bottles)}
                              {(l.scrap_empty + l.scrap_filled) > 0 && <span className="ml-1 text-amber-400">−{l.scrap_empty + l.scrap_filled}</span>}
                            </td>
                            <td className="py-1 pr-2 whitespace-nowrap">
                              {l.weight_status && <span className={WEIGHT_TONE[l.weight_status] ?? fl.muted}>⚖️{l.check_weight_g ? ` ${l.check_weight_g}g` : ''} </span>}
                              {l.verify_status && <span className={VERIFY_TONE[l.verify_status] ?? fl.muted}>🔖 {l.verify_status.replace('_', ' ')}</span>}
                              {l.log_type !== 'Hourly Bottle Count' && <span className={fl.muted}> {l.log_type}</span>}
                              {(l.notes || l.pour_note) && <span className={fl.muted}> 📝</span>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {logs.length > shownLogs.length && (
                    <button className={`${fl.btnSecondary} mt-2`} onClick={() => setShowAll(true)}>Show all {logs.length}</button>
                  )}
                  {data.truncated && <p className={`mt-1 text-xs ${fl.muted}`}>Showing the newest {logs.length}; the totals above count all {s.logs}. The CSV has the same {logs.length}.</p>}
                </Section>
              )}

              {data.runs.length > 0 && !data.run && (
                <Section label="Runs" count={data.runs.length}>
                  <div className="flex flex-col gap-1">
                    {data.runs.map((r) => (
                      <Drill key={r.id} f={{ run_id: r.id }} block className="rounded">
                        <div className="rounded border border-[var(--fl-border)] px-2 py-1.5 text-xs">
                          <div className="flex justify-between gap-2">
                            <span className="text-[var(--fl-ink)]">#{r.id} · {r.resin_type} · {r.pump_station}{r.lot_number && ` · ${r.lot_number}`}</span>
                            <span className={fl.muted}>{r.status}</span>
                          </div>
                          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--fl-overlay-weak)]">
                            <div className="h-full bg-[var(--fl-accent)]" style={{ width: `${Math.min(100, (r.current_units / Math.max(1, r.target_units)) * 100)}%` }} />
                          </div>
                          <p className={`mt-0.5 ${fl.muted}`}>{fmtNum(r.current_units)} / {fmtNum(r.target_units)} · {r.assigned_operator} · {fmtTime(r.created_at)}</p>
                        </div>
                      </Drill>
                    ))}
                  </div>
                </Section>
              )}

              {data.batches.length > 0 && (
                <Section label="Vessel batches" count={data.batches.length} open={!!(f.lot || f.reactor)}>
                  <table className="w-full text-left text-xs">
                    <thead className={fl.tableHead}>
                      <tr><th className="py-1 pr-2">Vessel</th><th className="py-1 pr-2">Resin / lot</th><th className="py-1 pr-2">Filled</th><th className="py-1 pr-2">Emptied</th><th className="py-1 pr-2">QC</th></tr>
                    </thead>
                    <tbody>
                      {data.batches.map((b) => (
                        <tr key={b.id} className={fl.tableRow} title={b.qc_note || undefined}>
                          <td className="py-1 pr-2 whitespace-nowrap"><Drill f={{ reactor: b.reactor_name }}>{b.reactor_name}</Drill></td>
                          <td className="py-1 pr-2">{b.resin_type}{b.lot_number && <> · <Drill f={{ lot: b.lot_number }}>{b.lot_number}</Drill></>}</td>
                          <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{fmtTime(b.filled_at)}</td>
                          <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{b.emptied_at ? fmtTime(b.emptied_at) : 'in use'}</td>
                          <td className={`py-1 pr-2 ${b.qc_result === 'pass' ? 'text-emerald-400' : b.qc_result ? 'text-amber-400' : fl.muted}`}>{b.qc_result || (b.qc_sent_at ? 'waiting' : '—')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}

              {data.verifications.length > 0 && (
                <Section label="Cartridge lot checks" count={data.verifications.length} open={!!f.lot}>
                  <table className="w-full text-left text-xs">
                    <thead className={fl.tableHead}>
                      <tr><th className="py-1 pr-2">When</th><th className="py-1 pr-2">Who</th><th className="py-1 pr-2">Typed</th><th className="py-1 pr-2">Result</th><th className="py-1 pr-2" /></tr>
                    </thead>
                    <tbody>
                      {data.verifications.map((v) => (
                        <tr key={v.id} className={fl.tableRow} title={v.reason || undefined}>
                          <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{fmtTime(v.timestamp)}</td>
                          <td className="py-1 pr-2 whitespace-nowrap">{v.operator_name} · {v.pump_station}</td>
                          <td className="py-1 pr-2">{v.entered_lot || '—'}{v.expected_lot && v.expected_lot !== v.entered_lot && <span className={fl.muted}> (run: {v.expected_lot})</span>}</td>
                          <td className={`py-1 pr-2 ${VERIFY_TONE[v.result] ?? fl.muted}`}>{v.result}{v.reason && ' 📝'}</td>
                          <td className="py-1 pr-2">
                            {everyone && v.photo_filename && (
                              <a className="text-[var(--fl-accent-2)] underline" href={lotVerificationApi.photoUrl(v.photo_filename)} target="_blank" rel="noreferrer">📷</a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}

              {data.downtime.length > 0 && (
                <Section label="Downtime" count={data.downtime.length}>
                  <table className="w-full text-left text-xs">
                    <thead className={fl.tableHead}>
                      <tr><th className="py-1 pr-2">When</th><th className="py-1 pr-2">Where</th><th className="py-1 pr-2">Why</th><th className="py-1 pr-2 text-right">Min</th></tr>
                    </thead>
                    <tbody>
                      {data.downtime.map((d) => (
                        <tr key={d.id} className={fl.tableRow} title={d.notes || undefined}>
                          <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{fmtTime(d.timestamp)}</td>
                          <td className="py-1 pr-2 whitespace-nowrap">{everyone && `${d.operator_name} · `}{d.pump_station}</td>
                          <td className="py-1 pr-2">{d.reason}{d.notes && ' 📝'}</td>
                          <td className="py-1 pr-2 text-right tabular-nums">{d.duration_min}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}

              {data.audits.length > 0 && (
                <Section label="Photo audits" count={data.audits.length} open={false}>
                  <table className="w-full text-left text-xs">
                    <tbody>
                      {data.audits.map((a) => (
                        <tr key={a.id} className={fl.tableRow} title={a.notes || undefined}>
                          <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{fmtTime(a.timestamp)}</td>
                          <td className="py-1 pr-2 whitespace-nowrap">{everyone && `${a.operator_name} · `}{a.pump_station}</td>
                          <td className="py-1 pr-2">{a.is_spill && '⚠️ '}{a.audit_type}</td>
                          <td className="py-1 pr-2">
                            {everyone && a.image_filename && (
                              <a className="text-[var(--fl-accent-2)] underline" href={cleanlinessApi.photoUrl(a.image_filename)} target="_blank" rel="noreferrer">📷</a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  )
}
