import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { batchHistoryApi, type BatchRow } from '../api/batchHistory'
import { fl } from '../theme'

const tile = fl.tile
const card = fl.card
const input = fl.input
const btn = fl.btn
const WINDOWS = [7, 14, 30, 90, 365] as const

const C_DWELL = '#00D2FF'
const C_QC = '#38BDF8'
const C_WARN = '#F59E0B'
const C_BAD = '#EF4444'

function fmt(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

// Round-trips a Date/ISO string through the value <input type="datetime-local">
// wants ("YYYY-MM-DDTHH:mm") and back to a full ISO string the API can parse -
// the original split this into separate date_input/time_input widgets purely
// because that's what Streamlit offered, not because the data needs two
// fields; one native picker is simpler for the same result.
function toLocalInput(iso: string | null | undefined): string {
  const d = iso ? new Date(iso) : new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fromLocalInput(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}

function downloadCsv(batches: BatchRow[]) {
  const header = ['Vessel', 'Resin', 'Filled', 'Emptied', 'In vessel (h)', 'Sent to QC',
    'Back from QC', 'At QC (h)', 'Result', 'Recorded by']
  const rows = batches.map((b) => [
    b.reactor_name, b.resin_type, fmt(b.filled_at), fmt(b.emptied_at),
    b.hours_in_reactor ?? '', fmt(b.qc_sent_at), fmt(b.qc_result_at), b.hours_at_qc ?? '',
    b.qc_result || '—', b.qc_by,
  ])
  const csv = [header, ...rows].map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `batch_history_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function QcEntryForm({ batches, days }: { batches: BatchRow[]; days: number }) {
  const queryClient = useQueryClient()
  const sorted = [...batches].sort((a, b) => (b.filled_at ?? '').localeCompare(a.filled_at ?? ''))
  const [batchId, setBatchId] = useState<number | null>(sorted[0]?.id ?? null)
  const current = batches.find((b) => b.id === batchId) ?? null

  const [sentAt, setSentAt] = useState('')
  const [hasResult, setHasResult] = useState(false)
  const [resultAt, setResultAt] = useState('')
  const [result, setResult] = useState<'pass' | 'hold' | 'fail'>('pass')
  const [note, setNote] = useState('')

  useEffect(() => {
    if (!current) return
    setSentAt(toLocalInput(current.qc_sent_at))
    setHasResult(Boolean(current.qc_result_at))
    setResultAt(toLocalInput(current.qc_result_at))
    setResult((current.qc_result as 'pass' | 'hold' | 'fail') || 'pass')
    setNote(current.qc_note || '')
  }, [current?.id])

  const saveMutation = useMutation({
    mutationFn: () =>
      batchHistoryApi.saveQc(batchId as number, {
        sent_at: fromLocalInput(sentAt),
        result_at: hasResult ? fromLocalInput(resultAt) : null,
        result: hasResult ? result : '',
        note,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['batch-history', days] }),
  })

  if (!current) return null

  const label = (b: BatchRow) => {
    const stamp = b.filled_at ? fmt(b.filled_at) : 'unknown start'
    const flag = !b.qc_sent_at && !b.qc_result ? ' · no QC yet' : b.qc_open ? ' · at QC' : ''
    return `${b.reactor_name} — ${b.resin_type || 'resin not recorded'} (${stamp})${flag}`
  }

  return (
    <div className={card}>
      <p className="mb-2 text-sm font-semibold text-white">💾 Record QC</p>
      <select className={`${input} mb-3`} value={batchId ?? ''} onChange={(e) => setBatchId(Number(e.target.value))}>
        {sorted.map((b) => (
          <option key={b.id} value={b.id}>{label(b)}</option>
        ))}
      </select>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={`mb-1 block ${fl.label}`}>Sample sent</label>
          <input type="datetime-local" className={input} value={sentAt} onChange={(e) => setSentAt(e.target.value)} />
        </div>
        <div>
          <label className={`mb-1 flex items-center gap-2 ${fl.label}`}>
            <input type="checkbox" checked={hasResult} onChange={(e) => setHasResult(e.target.checked)} />
            The result has come back
          </label>
          {hasResult && (
            <input type="datetime-local" className={input} value={resultAt} onChange={(e) => setResultAt(e.target.value)} />
          )}
        </div>
      </div>

      {hasResult && (
        <div className="mt-3 flex gap-4 text-sm">
          {(['pass', 'hold', 'fail'] as const).map((r) => (
            <label key={r} className="flex items-center gap-1.5">
              <input type="radio" name="qc-result" checked={result === r} onChange={() => setResult(r)} />
              {r}
            </label>
          ))}
        </div>
      )}

      <input
        className={`${input} mt-3`}
        placeholder="Note (optional)"
        maxLength={200}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <p className={`mt-1 text-xs ${fl.muted}`}>
        Times are typed rather than stamped, because the result usually arrives before anybody is at a screen.
        Put in when it actually happened.
      </p>
      {saveMutation.isError && (
        <p className="mt-2 text-xs text-red-400">{(saveMutation.error as Error).message}</p>
      )}
      <button
        className={`${btn} mt-3 w-full`}
        disabled={saveMutation.isPending}
        onClick={() => saveMutation.mutate()}
      >
        💾 Save QC
      </button>
      {current.qc_by && <p className={`mt-1 text-xs ${fl.muted}`}>Last recorded by {current.qc_by}.</p>}
    </div>
  )
}

// Batch History, ported from pages/Mgr_Batch_History.py - reactor dwell time
// and QC turnaround, plus the QC-entry form moved here from the reactor page.
export function BatchHistoryPage() {
  const [days, setDays] = useState<(typeof WINDOWS)[number]>(30)
  const query = useQuery({ queryKey: ['batch-history', days], queryFn: () => batchHistoryApi.get(days) })
  const data = query.data

  const maxDwell = Math.max(...(data?.dwell_by_vessel.map((d) => d.avg_hours) ?? [1]), 1)
  const maxTrend = Math.max(...(data?.qc_trend.map((t) => t.avg_hours) ?? [1]), 1)

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>🧪 Batch History — reactor dwell and QC turnaround</h1>

      <select
        className={`${fl.select} w-56`}
        value={days}
        onChange={(e) => setDays(Number(e.target.value) as (typeof WINDOWS)[number])}
      >
        {WINDOWS.map((w) => (
          <option key={w} value={w}>Fillings started in the last {w} days</option>
        ))}
      </select>

      {!data || data.totals.fillings_in_window === 0 ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
          🧪 No batches recorded yet. A filling is opened when a vessel is changed over to a resin, so the first
          one appears here after the next changeover is confirmed at a pump.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className={tile} style={{ borderColor: C_DWELL }}>
              <p className="text-lg font-semibold text-white">{data.totals.fillings_in_window.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Fillings in window</p>
            </div>
            <div className={tile} style={{ borderColor: C_DWELL }}>
              <p className="text-lg font-semibold text-white">{data.totals.sitting_now.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Sitting in a vessel now</p>
            </div>
            <div className={tile} style={{ borderColor: C_QC }}>
              <p className="text-lg font-semibold text-white">{data.totals.waiting_qc.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Waiting on QC</p>
            </div>
            <div className={tile} style={{ borderColor: C_QC }}>
              <p className="text-lg font-semibold text-white">
                {data.totals.avg_qc_turnaround_h !== null ? `${data.totals.avg_qc_turnaround_h} h` : '—'}
              </p>
              <p className={`text-xs ${fl.muted}`}>Avg QC turnaround</p>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <div className={tile}>
              <p className="text-lg font-semibold text-white">
                {data.totals.avg_time_in_vessel_h !== null ? `${data.totals.avg_time_in_vessel_h} h` : '—'}
              </p>
              <p className={`text-xs ${fl.muted}`}>Avg time in a vessel</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">
                {data.totals.longest_sitting_h !== null ? `${data.totals.longest_sitting_h} h` : '—'}
              </p>
              <p className={`text-xs ${fl.muted}`}>Longest still sitting</p>
            </div>
            <div className={tile} style={{ borderColor: C_QC }}>
              <p className="text-lg font-semibold text-white">
                {data.totals.longest_qc_wait_h !== null ? `${data.totals.longest_qc_wait_h} h` : '—'}
              </p>
              <p className={`text-xs ${fl.muted}`}>Longest wait on QC</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className={card}>
              <p className="mb-2 text-sm font-semibold text-white">⏱️ Average dwell by vessel</p>
              {data.dwell_by_vessel.length === 0 ? (
                <p className={`text-sm ${fl.muted}`}>No emptied fillings in this window yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.dwell_by_vessel.map((d) => (
                    <div key={d.reactor_name} className="flex items-center gap-2 text-xs">
                      <span className="w-24 shrink-0 truncate text-[#CBD5E1]">{d.reactor_name}</span>
                      <div className="h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
                        <div className="h-full rounded" style={{ width: `${(d.avg_hours / maxDwell) * 100}%`, backgroundColor: C_DWELL }} />
                      </div>
                      <span className="w-14 shrink-0 text-right font-medium text-white">{d.avg_hours} h</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className={card}>
              <p className="mb-2 text-sm font-semibold text-white">🧪 QC turnaround trend</p>
              {data.qc_trend.length === 0 ? (
                <p className={`text-sm ${fl.muted}`}>No completed QC round trips in this window yet.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {data.qc_trend.map((t) => (
                    <div key={t.day} className="flex items-center gap-2 text-xs">
                      <span className="w-20 shrink-0 text-[#CBD5E1]">{t.day}</span>
                      <div className="h-4 flex-1 overflow-hidden rounded bg-[#0F172A]">
                        <div className="h-full rounded" style={{ width: `${(t.avg_hours / maxTrend) * 100}%`, backgroundColor: C_QC }} />
                      </div>
                      <span className="w-14 shrink-0 text-right font-medium text-white">{t.avg_hours} h</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {data.out_at_qc.length > 0 && (
            <div className={card}>
              <p className="mb-2 text-sm font-semibold text-white">🧪 Out at QC now</p>
              <div className="flex flex-col gap-2">
                {data.out_at_qc.map((o) => {
                  const tone = o.hours_at_qc > 48 ? C_BAD : o.hours_at_qc > 24 ? C_WARN : C_QC
                  return (
                    <div key={o.id} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm" style={{ borderLeft: `4px solid ${tone}` }}>
                      <span className="text-[#F8FAFC]"><b>{o.reactor_name}</b> <span className={fl.muted}>· {o.resin_type}</span></span>
                      <span style={{ color: tone }} className="font-bold">{o.hours_at_qc} h at QC</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {data.totals.no_qc_recorded > 0 && (
            <p className="text-xs text-amber-400">
              ⚠️ {data.totals.no_qc_recorded} filling(s) in a vessel with no QC recorded at all. That is a blank, not a pass.
            </p>
          )}

          {data.can_manage_qc && <QcEntryForm batches={data.batches} days={days} />}

          <div className={card}>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-white">Every filling</p>
              <button onClick={() => downloadCsv(data.batches)} className={fl.btnSecondary}>
                ⬇️ Download as CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className={fl.tableHead}>
                  <tr>
                    <th className="py-1 pr-2">Vessel</th><th className="py-1 pr-2">Resin</th>
                    <th className="py-1 pr-2">Filled</th><th className="py-1 pr-2">Emptied</th>
                    <th className="py-1 pr-2">In vessel (h)</th><th className="py-1 pr-2">Sent to QC</th>
                    <th className="py-1 pr-2">Back from QC</th><th className="py-1 pr-2">At QC (h)</th>
                    <th className="py-1 pr-2">Result</th><th className="py-1 pr-2">Recorded by</th>
                  </tr>
                </thead>
                <tbody>
                  {data.batches.map((b) => (
                    <tr key={b.id} className={fl.tableRow}>
                      <td className="py-1 pr-2">{b.reactor_name}</td>
                      <td className="py-1 pr-2">{b.resin_type}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">{fmt(b.filled_at)}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">{b.emptied_at ? fmt(b.emptied_at) : 'still in use'}</td>
                      <td className="py-1 pr-2">{b.hours_in_reactor ?? ''}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">{fmt(b.qc_sent_at)}</td>
                      <td className="py-1 pr-2 whitespace-nowrap">{fmt(b.qc_result_at)}</td>
                      <td className="py-1 pr-2">{b.hours_at_qc ?? ''}</td>
                      <td className="py-1 pr-2">{b.qc_result === 'fail' ? 'FAIL' : b.qc_result === 'hold' ? 'on hold' : b.qc_result || '—'}</td>
                      <td className="py-1 pr-2">{b.qc_by}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className={`text-xs ${fl.muted}`}>
            Times in a vessel come from an operator marking the tank empty, or from the next changeover confirmed
            at the pump if nobody did — whichever happens first. QC times are entered above, so they are only as
            good as when somebody enters them — which is worth saying before anybody averages them.
          </p>
        </>
      )}
    </div>
  )
}
