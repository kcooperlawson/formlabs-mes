import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { assignedRunsApi, type AssignedRun } from '../api/assignedRuns'
import { referenceApi } from '../api/reference'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

const tile = fl.tile
const card = fl.card
const input = fl.input
const btn = fl.btn

const FORMATS: [string, string][] = [
  ['V2 (1L Cartridge)', 'V2'],
  ['V1 (1L Cartridge)', 'V1'],
  ['RPS (5L Bulk Jug)', 'RPS'],
  ['Pigment', 'Pigment'],
]

function todayLot(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `LOT-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-01`
}

function LayerBar({ pct, color = '#00D2FF' }: { pct: number; color?: string }) {
  const clamped = Math.max(0, Math.min(100, pct))
  return (
    <div className="h-4 w-full overflow-hidden rounded border border-[#1E2B45] bg-[#0B1220]">
      <div
        className="h-full transition-all"
        style={{
          width: `${clamped}%`,
          backgroundImage: `repeating-linear-gradient(to right, ${color} 0px, ${color} 6px, rgba(0,0,0,0.45) 6px, rgba(0,0,0,0.45) 7px)`,
        }}
      />
    </div>
  )
}

function DispatchForm() {
  const queryClient = useQueryClient()
  const optionsQuery = useQuery({ queryKey: ['assigned-runs', 'options'], queryFn: assignedRunsApi.options })
  const resinsQuery = useQuery({ queryKey: ['reference', 'resins'], queryFn: referenceApi.resins })
  const options = optionsQuery.data
  const allResins = resinsQuery.data ?? []

  const [runType, setRunType] = useState<'Pouring' | 'Packing'>('Pouring')
  const [reactorId, setReactorId] = useState('')
  const [lotNumber, setLotNumber] = useState(todayLot())
  const [formatLabel, setFormatLabel] = useState(FORMATS[0][0])
  const cartCode = FORMATS.find(([l]) => l === formatLabel)?.[1] ?? 'V2'
  const [resinType, setResinType] = useState('')
  const [targetUnits, setTargetUnits] = useState(1000)
  const [assignedPump, setAssignedPump] = useState('')
  const [assignedOp, setAssignedOp] = useState('')
  const [initialStatus, setInitialStatus] = useState<'Active' | 'Queued'>('Active')
  const [notes, setNotes] = useState('')

  const reactors = options?.reactors ?? []
  const reactor = reactors.find((r) => r.reactor_name === (reactorId || reactors[0]?.reactor_name))
  const reactorSizeVal = runType === 'Packing' ? 0 : reactor?.max_capacity_l ?? 5000
  const effectiveReactorId = runType === 'Packing' ? 'Floor WIP' : reactorId || reactors[0]?.reactor_name || 'No Reactors Configured'

  const resinsForFormat = allResins.filter((r) => r.cartridge_type.includes(cartCode))
  const resinList = (resinsForFormat.length > 0 ? resinsForFormat : allResins).map((r) => r.resin_name)
  const effectiveResin = resinType || resinList[0] || ''

  const personnelList = runType === 'Packing' ? options?.packers ?? [] : options?.operators ?? []
  const effectiveOp = assignedOp || personnelList[0] || ''
  const effectivePump = assignedPump || options?.pumps[0] || ''

  const createMutation = useMutation({
    mutationFn: () =>
      assignedRunsApi.create({
        run_type: runType, reactor_id: effectiveReactorId, reactor_size_l: reactorSizeVal,
        cartridge_type: cartCode, resin_type: effectiveResin, target_units: targetUnits,
        assigned_pump: effectivePump, assigned_operator: effectiveOp, lot_number: lotNumber,
        notes, status: initialStatus,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assigned-runs'] })
      setLotNumber(todayLot())
      setNotes('')
    },
  })

  return (
    <details className={card} open>
      <summary className="cursor-pointer text-sm font-medium text-white">➕ Create &amp; Assign New Work Order</summary>
      <div className="mt-3 flex flex-col gap-4">
        {options?.enable_packing ? (
          <div className="flex gap-4 text-sm text-[#CBD5E1]">
            {(['Pouring', 'Packing'] as const).map((t) => (
              <label key={t} className="flex items-center gap-1.5">
                <input type="radio" checked={runType === t} onChange={() => setRunType(t)} />
                {t}
              </label>
            ))}
          </div>
        ) : (
          <p className={`text-xs ${fl.muted}`}>📦 Packing Module is currently disabled in Plant Settings.</p>
        )}

        {runType === 'Pouring' ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <select className={input} value={effectiveReactorId} onChange={(e) => setReactorId(e.target.value)}>
              {reactors.length === 0
                ? <option>No Reactors Configured</option>
                : reactors.map((r) => <option key={r.reactor_name}>{r.reactor_name}</option>)}
            </select>
            <p className={`self-center text-xs ${fl.muted}`}>Capacity: {reactorSizeVal.toLocaleString()} L</p>
            <input className={input} placeholder="Batch Lot ID" value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_2fr]">
            <p className={`self-center text-xs ${fl.muted}`}>Source: Floor WIP (Unpacked Units)</p>
            <input className={input} placeholder="Batch Lot ID to Pack" value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} />
          </div>
        )}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <select className={input} value={formatLabel} onChange={(e) => setFormatLabel(e.target.value)}>
            {FORMATS.map(([label]) => <option key={label}>{label}</option>)}
          </select>
          <select className={input} value={effectiveResin} onChange={(e) => setResinType(e.target.value)}>
            {resinList.length === 0 ? <option>No Resins</option> : resinList.map((r) => <option key={r}>{r}</option>)}
          </select>
          <input
            className={input} type="number" min={1} max={50000} step={50}
            value={targetUnits} onChange={(e) => setTargetUnits(Number(e.target.value))}
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <select className={input} value={effectivePump} onChange={(e) => setAssignedPump(e.target.value)}>
            {(options?.pumps ?? []).map((p) => <option key={p}>{p}</option>)}
          </select>
          <select className={input} value={effectiveOp} onChange={(e) => setAssignedOp(e.target.value)}>
            {personnelList.length === 0 ? <option>No personnel</option> : personnelList.map((p) => <option key={p}>{p}</option>)}
          </select>
          <select className={input} value={initialStatus} onChange={(e) => setInitialStatus(e.target.value as 'Active' | 'Queued')}>
            <option value="Active">Active</option>
            <option value="Queued">Queued</option>
          </select>
        </div>

        <input className={input} placeholder="Special Process Instructions / Run Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />

        {createMutation.isError && (
          <p className="text-xs text-red-400">{(createMutation.error as Error).message}</p>
        )}
        <button className={btn} disabled={createMutation.isPending} onClick={() => createMutation.mutate()}>
          {runType === 'Pouring' ? '🚀 Dispatch Pouring Run' : '📦 Dispatch Packing Run'}
        </button>
      </div>
    </details>
  )
}

function CompleteRunPanel({ run }: { run: AssignedRun }) {
  const queryClient = useQueryClient()
  const [finalUnits, setFinalUnits] = useState(run.current_units)
  const [touched, setTouched] = useState(false)

  // This panel mounts once with the card and stays mounted while +50/+100
  // keep changing run.current_units underneath it - so the field has to
  // keep tracking that live value (the same way the original page re-reads
  // it fresh on every rerun) until the manager actually types a correction,
  // or it would silently submit whatever current_units happened to be at
  // the moment the card first rendered instead of the real current total.
  useEffect(() => {
    if (!touched) setFinalUnits(run.current_units)
  }, [run.current_units, touched])

  const completeMutation = useMutation({
    mutationFn: () => assignedRunsApi.complete(run.id, finalUnits),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assigned-runs'] }),
  })
  return (
    <details className="mt-2">
      <summary className={`cursor-pointer text-xs ${fl.muted}`}>⚙️ Set Final Count &amp; Close Work Order #{run.id}</summary>
      <div className="mt-2 flex items-center gap-2">
        <input
          className={input} type="number" step={10} value={finalUnits}
          onChange={(e) => { setTouched(true); setFinalUnits(Number(e.target.value)) }}
        />
        <button className={`${btn} shrink-0`} disabled={completeMutation.isPending} onClick={() => completeMutation.mutate()}>
          💾 Save Final Count &amp; Archive Run
        </button>
      </div>
    </details>
  )
}

function RunCard({ run }: { run: AssignedRun }) {
  const queryClient = useQueryClient()
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['assigned-runs'] })
  const progressMutation = useMutation({
    mutationFn: (delta: number) => assignedRunsApi.progress(run.id, delta),
    onSuccess: invalidate,
  })
  const statusMutation = useMutation({
    mutationFn: (status: string) => assignedRunsApi.setStatus(run.id, status),
    onSuccess: invalidate,
  })
  const deleteMutation = useMutation({
    mutationFn: () => assignedRunsApi.remove(run.id),
    onSuccess: invalidate,
  })

  const pct = run.target_units > 0 ? Math.min(100, (run.current_units / run.target_units) * 100) : 0
  const statusColor = ['Active', 'Pouring'].includes(run.status) ? '#10B981' : run.status === 'Queued' ? '#F59E0B' : '#64748B'

  return (
    <div className={card}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded px-2 py-0.5 text-xs font-extrabold text-white" style={{ backgroundColor: statusColor }}>
            ● {run.status.toUpperCase()}
          </span>
          <span
            className="rounded-full border px-2 py-0.5 text-sm font-semibold"
            style={{ backgroundColor: run.resin_color, borderColor: run.resin_color, color: '#111827' }}
          >
            <Drill f={{ resin: run.resin_type }}>{run.resin_type}</Drill>
          </span>
          <span className="text-xs font-bold text-[#F97316]">[{run.cartridge_type}]</span>
        </div>
        <div className={`text-xs ${fl.muted}`}>
          🛢️ <b className="text-[#CBD5E1]"><Drill f={{ reactor: run.reactor_id }}>{run.reactor_id}</Drill></b> ({run.reactor_size_l.toLocaleString()} L) &nbsp;|&nbsp; 🏷️ <b className="text-[#CBD5E1]"><Drill f={{ pump: run.pump_station }}>{run.pump_station}</Drill></b> &nbsp;|&nbsp; 👤 <b className="text-[#CBD5E1]"><Drill f={{ operator: run.assigned_operator }}>{run.assigned_operator}</Drill></b>
        </div>
      </div>

      <p className={`mb-1 text-xs ${fl.muted}`}>
        Output: <b className="text-[#F8FAFC]"><Drill f={{ run_id: run.id }} title="Every log counted toward this run">{run.current_units.toLocaleString()} / {run.target_units.toLocaleString()}</Drill></b> Units ({pct.toFixed(1)}%) &nbsp;|&nbsp; Lot: {run.lot_number ? <Drill f={{ lot: run.lot_number }}>{run.lot_number}</Drill> : 'N/A'}
      </p>
      <LayerBar pct={pct} />

      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button className={fl.btnSecondary} disabled={progressMutation.isPending} onClick={() => progressMutation.mutate(50)}>
          +50 Units
        </button>
        <button className={fl.btnSecondary} disabled={progressMutation.isPending} onClick={() => progressMutation.mutate(100)}>
          +100 Units
        </button>
        {run.status === 'Queued' ? (
          <button className={fl.btnSecondary} disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('Active')}>
            ▶️ Start
          </button>
        ) : (
          <button className={fl.btnSecondary} disabled={statusMutation.isPending} onClick={() => statusMutation.mutate('Queued')}>
            ⏸️ Queue
          </button>
        )}
        <button className={fl.btnSecondary} disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate()}>
          🗑️ Delete
        </button>
      </div>

      <CompleteRunPanel run={run} />
    </div>
  )
}

function CompletedTab({ runs }: { runs: AssignedRun[] }) {
  const queryClient = useQueryClient()
  const [typeFilter, setTypeFilter] = useState('All')
  const [opFilter, setOpFilter] = useState('All')
  const [lotFilter, setLotFilter] = useState('All')
  const [toDelete, setToDelete] = useState<number | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (id: number) => assignedRunsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assigned-runs'] })
      setToDelete(null)
    },
  })

  if (runs.length === 0) {
    return (
      <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
        ✅ Nothing completed yet. Work orders land here once they reach their target or are marked done, with
        the units actually poured against the units ordered.
      </p>
    )
  }

  const opts = (key: 'run_type' | 'assigned_operator' | 'lot_number') =>
    ['All', ...Array.from(new Set(runs.map((r) => String(r[key])))).sort()]

  const filtered = runs.filter((r) =>
    (typeFilter === 'All' || r.run_type === typeFilter) &&
    (opFilter === 'All' || r.assigned_operator === opFilter) &&
    (lotFilter === 'All' || r.lot_number === lotFilter))

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <select className={input} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          {opts('run_type').map((v) => <option key={v}>{v}</option>)}
        </select>
        <select className={input} value={opFilter} onChange={(e) => setOpFilter(e.target.value)}>
          {opts('assigned_operator').map((v) => <option key={v}>{v}</option>)}
        </select>
        <select className={input} value={lotFilter} onChange={(e) => setLotFilter(e.target.value)}>
          {opts('lot_number').map((v) => <option key={v}>{v}</option>)}
        </select>
      </div>

      {filtered.length === 0 ? (
        <p className={`text-sm ${fl.muted}`}>No completed orders match the current filters.</p>
      ) : (
        <div className={card}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className={fl.tableHead}>
                <tr>
                  <th className="py-1 pr-2">ID</th><th className="py-1 pr-2">When</th><th className="py-1 pr-2">Type</th>
                  <th className="py-1 pr-2">Resin</th><th className="py-1 pr-2">Format</th><th className="py-1 pr-2">Lot</th>
                  <th className="py-1 pr-2">Target</th><th className="py-1 pr-2">Actual</th>
                  <th className="py-1 pr-2">Operator</th><th className="py-1 pr-2">Station</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className={fl.tableRow}>
                    <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ run_id: r.id }}>#{r.id}</Drill></td>
                    <td className="py-1 pr-2 whitespace-nowrap text-[#CBD5E1]">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.run_type}</td>
                    <td className="py-1 pr-2" style={{ backgroundColor: r.resin_color, color: '#111827' }}>{r.resin_type}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.cartridge_type}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ lot: r.lot_number }}>{r.lot_number}</Drill></td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.target_units.toLocaleString()}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ run_id: r.id }}>{r.current_units.toLocaleString()}</Drill></td>
                    <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ operator: r.assigned_operator }}>{r.assigned_operator}</Drill></td>
                    <td className="py-1 pr-2 text-[#CBD5E1]"><Drill f={{ pump: r.pump_station }}>{r.pump_station}</Drill></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <details className={card}>
        <summary className="cursor-pointer text-sm font-medium text-white">🗑️ Delete a Completed Work Order</summary>
        <p className={`mt-2 text-xs ${fl.muted}`}>
          Permanently removes this archived Work Order. This does NOT delete the underlying production logs
          that were poured/packed against it.
        </p>
        <div className="mt-2 flex items-center gap-2">
          <select className={input} value={toDelete ?? ''} onChange={(e) => setToDelete(Number(e.target.value))}>
            <option value="">— choose —</option>
            {filtered.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} — {r.resin_type} [{r.cartridge_type}] · {r.pump_station} · {r.current_units.toLocaleString()} units
              </option>
            ))}
          </select>
          <button
            className={`${fl.btnDanger} shrink-0`}
            disabled={!toDelete || deleteMutation.isPending}
            onClick={() => toDelete && deleteMutation.mutate(toDelete)}
          >
            🗑️ Permanently Delete
          </button>
        </div>
      </details>
    </div>
  )
}

// Fleet Production Progress & Work Order Dispatch, ported from
// pages/Mgr_Assigned_Runs.py.
export function AssignedRunsPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<'active' | 'completed'>('active')
  const query = useQuery({ queryKey: ['assigned-runs'], queryFn: assignedRunsApi.list })
  const data = query.data

  const syncMutation = useMutation({
    mutationFn: assignedRunsApi.sync,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assigned-runs'] }),
  })

  const activeRuns = data?.runs.filter((r) => r.status !== 'Done') ?? []
  const doneRuns = data?.runs.filter((r) => r.status === 'Done') ?? []

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>🎯 Fleet Production Progress &amp; Work Order Dispatch</h1>

      {data && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.total_actual.toLocaleString()} / {data.totals.total_target.toLocaleString()}</p>
            <p className={`text-xs ${fl.muted}`}>Fleet Progress ({data.totals.fleet_pct.toFixed(1)}%)</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.active_count} Active</p>
            <p className={`text-xs ${fl.muted}`}>{data.totals.queued_count} Queued | {data.totals.done_count} Done</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.pumps_configured} Configured</p>
            <p className={`text-xs ${fl.muted}`}>{data.totals.pumps_in_use} In Use</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{data.totals.active_operators_count} Ready</p>
            <p className={`text-xs ${fl.muted}`}>Active Operators</p>
          </div>
        </div>
      )}

      <DispatchForm />

      <div className={fl.tabStrip}>
        {([['active', '🚀 Active & Queued Runs'], ['completed', '✅ Completed Work Orders']] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={tab === key ? fl.tabActive : fl.tabInactive}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'active' && (
        <div className="flex flex-col gap-3">
          <button className={`self-end ${fl.btnSecondary}`} disabled={syncMutation.isPending} onClick={() => syncMutation.mutate()}>
            🔄 Sync Progress with Logs
          </button>
          {activeRuns.length === 0 ? (
            <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
              🎯 No runs dispatched yet. A work order tells an operator which resin, container format and lot to
              pour at which station. Use "Create &amp; Assign New Work Order" above.
            </p>
          ) : (
            activeRuns.map((r) => <RunCard key={r.id} run={r} />)
          )}
        </div>
      )}

      {tab === 'completed' && <CompletedTab runs={doneRuns} />}
    </div>
  )
}
