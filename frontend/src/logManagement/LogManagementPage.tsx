import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { logManagementApi } from '../api/logManagement'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

const card = fl.card
const input = fl.input

function fmt(iso: string): string {
  return new Date(iso).toLocaleString()
}

function BulkDeletePanel({ matchCount, onConfirm, pending }: { matchCount: number; onConfirm: () => void; pending: boolean }) {
  const [text, setText] = useState('')
  const armed = text.trim() === 'DELETE'
  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">☢️ Bulk Delete — every record matching the filters above</summary>
      <p className={`mt-2 text-xs ${fl.muted}`}>
        This will permanently delete all <b>{matchCount}</b> record(s) currently matched by the filters above,
        not just the ones visible on screen.
      </p>
      <input
        className={`${input} mt-2 w-full`}
        placeholder="DELETE"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button className={`${fl.btnDanger} mt-2 w-full`} disabled={!armed || pending} onClick={onConfirm}>
        ☢️ Permanently Delete All {matchCount} Matching Record(s)
      </button>
    </details>
  )
}

function ProductionLogsTab() {
  const queryClient = useQueryClient()
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [logType, setLogType] = useState('All Types')
  const [pump, setPump] = useState('All Pumps')
  const [operator, setOperator] = useState('All Operators')
  const [showN, setShowN] = useState(100)

  const query = useQuery({
    queryKey: ['log-management', 'production', startDate, endDate, logType, pump, operator, showN],
    queryFn: () => logManagementApi.production({
      start_date: startDate || undefined, end_date: endDate || undefined,
      log_type: logType, pump_station: pump, operator, limit: showN,
    }),
  })
  const data = query.data
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['log-management', 'production'] })

  const deleteMutation = useMutation({ mutationFn: (id: number) => logManagementApi.deleteProduction(id), onSuccess: invalidate })
  const bulkMutation = useMutation({
    mutationFn: () => logManagementApi.bulkDeleteProduction({
      start_date: startDate || undefined, end_date: endDate || undefined,
      log_type: logType, pump_station: pump, operator,
    }),
    onSuccess: invalidate,
  })

  if (!data) return null
  if (data.filters.log_types.length === 0 && data.total_matches === 0 && !startDate && !endDate) {
    return (
      <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
        🗑️ No production logs yet. This page is for finding and removing bad or test entries. Nothing has been
        logged, so there is nothing to clean up.
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-5">
        <input className={input} type="date" min={data.filters.min_date ?? undefined} max={data.filters.max_date ?? undefined}
              value={startDate} placeholder="From date" onChange={(e) => setStartDate(e.target.value)} />
        <input className={input} type="date" min={data.filters.min_date ?? undefined} max={data.filters.max_date ?? undefined}
              value={endDate} placeholder="To date" onChange={(e) => setEndDate(e.target.value)} />
        <select className={input} value={logType} onChange={(e) => setLogType(e.target.value)}>
          <option>All Types</option>
          {data.filters.log_types.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select className={input} value={pump} onChange={(e) => setPump(e.target.value)}>
          <option>All Pumps</option>
          {data.filters.pumps.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select className={input} value={operator} onChange={(e) => setOperator(e.target.value)}>
          <option>All Operators</option>
          {data.filters.operators.map((o) => <option key={o}>{o}</option>)}
        </select>
      </div>

      <p className={`text-sm ${fl.muted}`}><b className="text-white">{data.total_matches}</b> record(s) match the current filters.</p>

      {data.total_matches === 0 ? (
        <p className={`text-sm ${fl.muted}`}>No records match the current filters.</p>
      ) : (
        <>
          <label className={`flex items-center gap-2 text-xs ${fl.muted}`}>
            Rows to display
            <input className={`${input} w-24`} type="number" min={10} max={1000} step={10}
                  value={showN} onChange={(e) => setShowN(Number(e.target.value))} />
          </label>

          <div className={card}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className={fl.tableHead}>
                  <tr>
                    <th className="py-1 pr-2">Timestamp</th><th className="py-1 pr-2">Type</th>
                    <th className="py-1 pr-2">Station</th><th className="py-1 pr-2">Resin</th>
                    <th className="py-1 pr-2">Operator</th><th className="py-1 pr-2 text-right">Qty</th>
                    <th className="py-1 pr-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.id} className={fl.tableRow}>
                      <td className="py-1 pr-2 whitespace-nowrap text-[#CBD5E1]">{fmt(r.timestamp)}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{r.log_type}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ pump: r.pump_station }}>{r.pump_station}</Drill></td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">
                        {r.resin_type && (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: r.resin_color ?? '#9AA3AE' }} />
                            <Drill f={{ resin: r.resin_type }}>{r.resin_type}</Drill>
                          </span>
                        )}
                      </td>
                      <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ operator: r.operator_name }}>{r.operator_name}</Drill></td>
                      <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.bottles_filled.toLocaleString()}</td>
                      <td className="py-1 pr-2">
                        <button
                          className={fl.btnSecondary}
                          disabled={deleteMutation.isPending}
                          onClick={() => deleteMutation.mutate(r.id)}
                          title={`Delete log #${r.id}`}
                        >
                          🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.total_matches > data.rows.length && (
              <p className={`mt-2 text-xs ${fl.muted}`}>
                Showing {data.rows.length} of {data.total_matches} — increase "Rows to display" above to see more.
              </p>
            )}
          </div>

          <BulkDeletePanel matchCount={data.total_matches} pending={bulkMutation.isPending} onConfirm={() => bulkMutation.mutate()} />
        </>
      )}
    </div>
  )
}

function DowntimeLogsTab() {
  const queryClient = useQueryClient()
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [pump, setPump] = useState('All Pumps')
  const [reason, setReason] = useState('All Reasons')
  const [showN, setShowN] = useState(100)

  const query = useQuery({
    queryKey: ['log-management', 'downtime', startDate, endDate, pump, reason, showN],
    queryFn: () => logManagementApi.downtime({
      start_date: startDate || undefined, end_date: endDate || undefined,
      pump_station: pump, reason, limit: showN,
    }),
  })
  const data = query.data
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['log-management', 'downtime'] })

  const deleteMutation = useMutation({ mutationFn: (id: number) => logManagementApi.deleteDowntime(id), onSuccess: invalidate })
  const bulkMutation = useMutation({
    mutationFn: () => logManagementApi.bulkDeleteDowntime({
      start_date: startDate || undefined, end_date: endDate || undefined, pump_station: pump, reason,
    }),
    onSuccess: invalidate,
  })

  if (!data) return null
  if (data.filters.pumps.length === 0 && data.total_matches === 0 && !startDate && !endDate) {
    return <p className={`text-sm ${fl.muted}`}>No downtime logs exist yet.</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-4">
        <input className={input} type="date" min={data.filters.min_date ?? undefined} max={data.filters.max_date ?? undefined}
              value={startDate} placeholder="From date" onChange={(e) => setStartDate(e.target.value)} />
        <input className={input} type="date" min={data.filters.min_date ?? undefined} max={data.filters.max_date ?? undefined}
              value={endDate} placeholder="To date" onChange={(e) => setEndDate(e.target.value)} />
        <select className={input} value={pump} onChange={(e) => setPump(e.target.value)}>
          <option>All Pumps</option>
          {data.filters.pumps.map((p) => <option key={p}>{p}</option>)}
        </select>
        <select className={input} value={reason} onChange={(e) => setReason(e.target.value)}>
          <option>All Reasons</option>
          {data.filters.reasons.map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>

      <p className={`text-sm ${fl.muted}`}><b className="text-white">{data.total_matches}</b> record(s) match the current filters.</p>

      {data.total_matches === 0 ? (
        <p className={`text-sm ${fl.muted}`}>No records match the current filters.</p>
      ) : (
        <>
          <label className={`flex items-center gap-2 text-xs ${fl.muted}`}>
            Rows to display
            <input className={`${input} w-24`} type="number" min={10} max={1000} step={10}
                  value={showN} onChange={(e) => setShowN(Number(e.target.value))} />
          </label>

          <div className={card}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className={fl.tableHead}>
                  <tr>
                    <th className="py-1 pr-2">Timestamp</th><th className="py-1 pr-2">Station</th>
                    <th className="py-1 pr-2">Reason</th><th className="py-1 pr-2 text-right">Minutes</th>
                    <th className="py-1 pr-2">Operator</th><th className="py-1 pr-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((r) => (
                    <tr key={r.id} className={fl.tableRow}>
                      <td className="py-1 pr-2 whitespace-nowrap text-[#CBD5E1]">{fmt(r.timestamp)}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ pump: r.pump_station }}>{r.pump_station}</Drill></td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{r.reason}</td>
                      <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.duration_min}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ operator: r.operator_name }}>{r.operator_name}</Drill></td>
                      <td className="py-1 pr-2">
                        <button
                          className={fl.btnSecondary}
                          disabled={deleteMutation.isPending}
                          onClick={() => deleteMutation.mutate(r.id)}
                          title={`Delete downtime log #${r.id}`}
                        >
                          🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.total_matches > data.rows.length && (
              <p className={`mt-2 text-xs ${fl.muted}`}>
                Showing {data.rows.length} of {data.total_matches} — increase "Rows to display" above to see more.
              </p>
            )}
          </div>

          <BulkDeletePanel matchCount={data.total_matches} pending={bulkMutation.isPending} onConfirm={() => bulkMutation.mutate()} />
        </>
      )}
    </div>
  )
}

// Log Management & Data Cleanup, ported from pages/Mgr_Log_Management.py -
// finding and permanently removing bad or test log entries.
export function LogManagementPage() {
  const [tab, setTab] = useState<'production' | 'downtime'>('production')
  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>🗑️ Log Management &amp; Data Cleanup</h1>
      <p className="rounded-lg border border-amber-800 bg-amber-950 px-3 py-2 text-sm text-amber-200">
        ⚠️ Deletions here are <b>permanent</b> and cannot be undone. Deleting a production log automatically
        re-syncs the progress of whatever Work Order it was counted against, so totals stay accurate after
        cleanup.
      </p>

      <div className={fl.tabStrip}>
        {([['production', '💧 Production Logs (Pouring / Packing)'], ['downtime', '⛔ Downtime Logs']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={tab === key ? fl.tabActive : fl.tabInactive}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'production' ? <ProductionLogsTab /> : <DowntimeLogsTab />}
    </div>
  )
}
