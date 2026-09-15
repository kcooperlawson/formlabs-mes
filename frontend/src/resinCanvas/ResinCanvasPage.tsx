import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { resinCanvasApi, type ResinCanvasRow } from '../api/resinCanvas'
import { fl } from '../theme'

const card = fl.card
const input = fl.input
const btn = fl.btn

const FORMATS = [
  ['ALL', '🌐 ALL'],
  ['V1', '🔵 V1 (1L)'],
  ['V1/V2', '🟢 V1/V2 Dual'],
  ['V2', '🟠 V2 (1L)'],
  ['RPS', '🍏 RPS (5L Jugs)'],
  ['Pigment', '🔴 Pigments'],
  ['Amazon', '🟡 Amazon Formulations'],
] as const

function textColorFor(hex: string): string {
  const c = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16) / 255)
  const lin = (v: number) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  return lum < 0.45 ? '#FFFFFF' : '#111827'
}

function AddResinForm() {
  const queryClient = useQueryClient()
  const [cartType, setCartType] = useState('V2')
  const [sku, setSku] = useState('')
  const [resinName, setResinName] = useState('')
  const [resinCode, setResinCode] = useState('')
  const [target, setTarget] = useState(1110)
  const [min, setMin] = useState(1100)
  const [max, setMax] = useState(1125)
  const [autoColour, setAutoColour] = useState(true)
  const [pickedColour, setPickedColour] = useState('#EBF5FA')

  const addMutation = useMutation({
    mutationFn: () =>
      resinCanvasApi.add({
        cartridge_type: cartType, sku, resin_code: resinCode, resin_name: resinName,
        actual_spec_g: target, min_weight_g: min, max_weight_g: max,
        color_tag: autoColour ? null : pickedColour,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resin-canvas'] })
      setSku(''); setResinName(''); setResinCode('')
      setTarget(1110); setMin(1100); setMax(1125)
    },
  })

  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">➕ Add New Proprietary Resin Formulation</summary>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-2">
          <select className={input} value={cartType} onChange={(e) => setCartType(e.target.value)}>
            {['V2', 'V1', 'V1/V2', 'RPS', 'Pigment', 'Amazon'].map((f) => <option key={f}>{f}</option>)}
          </select>
          <input className={input} placeholder="SKU Code (e.g. RS-F2-CUST-01)" value={sku} onChange={(e) => setSku(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <input className={input} placeholder="Formulation Name (e.g. High-Temp Clear V3)" value={resinName} onChange={(e) => setResinName(e.target.value)} />
          <input className={input} placeholder="Internal Resin Code (e.g. FLCUST01)" value={resinCode} onChange={(e) => setResinCode(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <label className={fl.label}>Target Fill Weight (g)
            <input className={input} type="number" value={target} onChange={(e) => setTarget(Number(e.target.value))} />
          </label>
          <label className={fl.label}>Min Weight (g)
            <input className={input} type="number" value={min} onChange={(e) => setMin(Number(e.target.value))} />
          </label>
          <label className={fl.label}>Max Weight (g)
            <input className={input} type="number" value={max} onChange={(e) => setMax(Number(e.target.value))} />
          </label>
        </div>
      </div>
      <label className="mt-3 flex items-center gap-2 text-sm text-[#CBD5E1]">
        <input type="checkbox" checked={autoColour} onChange={(e) => setAutoColour(e.target.checked)} />
        Pick the label colour automatically from the name
      </label>
      {!autoColour && (
        <input type="color" className="mt-2 h-9 w-20" value={pickedColour} onChange={(e) => setPickedColour(e.target.value)} />
      )}
      {addMutation.isError && (
        <p className="mt-2 text-xs text-red-400">{(addMutation.error as Error).message}</p>
      )}
      <button
        className={`${btn} mt-3 w-full`}
        disabled={!resinName.trim() || addMutation.isPending}
        onClick={() => addMutation.mutate()}
      >
        💾 Save New Resin to Database
      </button>
    </details>
  )
}

function EditDeletePanel({ rows }: { rows: ResinCanvasRow[] }) {
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = rows.find((r) => r.id === selectedId) ?? null

  const [target, setTarget] = useState(0)
  const [min, setMin] = useState(0)
  const [max, setMax] = useState(0)
  const [colour, setColour] = useState('#EBF5FA')

  // rows loads asynchronously, so the initial selection can't be set from a
  // useState initializer (it would freeze on the empty pre-fetch value) -
  // fall back to the first row once data actually arrives, or whenever the
  // selected row disappears (e.g. it was just deleted).
  useEffect(() => {
    if (rows.length === 0) {
      if (selectedId !== null) setSelectedId(null)
    } else if (!rows.some((r) => r.id === selectedId)) {
      setSelectedId(rows[0].id)
    }
  }, [rows, selectedId])

  useEffect(() => {
    if (!selected) return
    setTarget(selected.actual_spec_g)
    setMin(selected.min_weight_g)
    setMax(selected.max_weight_g)
    setColour(selected.color)
  }, [selected?.id])

  const updateMutation = useMutation({
    mutationFn: () =>
      resinCanvasApi.update(selectedId as number, {
        actual_spec_g: target, min_weight_g: min, max_weight_g: max, color_tag: colour,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['resin-canvas'] }),
  })
  const deleteMutation = useMutation({
    mutationFn: () => resinCanvasApi.remove(selectedId as number),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['resin-canvas'] })
      setSelectedId(null)
    },
  })

  if (rows.length === 0) return null

  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">✏️ Edit or Delete Resin Specifications</summary>
      <div className="mt-3 flex flex-col gap-3">
        <select className={input} value={selectedId ?? ''} onChange={(e) => setSelectedId(Number(e.target.value))}>
          {rows.map((r) => <option key={r.id} value={r.id}>{r.resin_name}</option>)}
        </select>

        {selected && (
          <>
            <p className="text-sm text-[#F8FAFC]">
              Currently shown as{' '}
              <span
                className="inline-block rounded-full border px-2 py-0.5 text-sm font-semibold"
                style={{ backgroundColor: selected.color, color: textColorFor(selected.color), borderColor: selected.color }}
              >
                {selected.resin_name}
              </span>
            </p>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
              <div className="grid grid-cols-3 gap-2">
                <label className={fl.label}>Target Spec (g)
                  <input className={input} type="number" value={target} onChange={(e) => setTarget(Number(e.target.value))} />
                </label>
                <label className={fl.label}>Min Weight (g)
                  <input className={input} type="number" value={min} onChange={(e) => setMin(Number(e.target.value))} />
                </label>
                <label className={fl.label}>Max Weight (g)
                  <input className={input} type="number" value={max} onChange={(e) => setMax(Number(e.target.value))} />
                </label>
              </div>
              <label className={fl.label}>Label colour
                <input type="color" className="block h-9 w-20" value={colour} onChange={(e) => setColour(e.target.value)} />
              </label>
            </div>

            <div className="flex gap-2">
              <button className={`${btn} flex-1`} disabled={updateMutation.isPending} onClick={() => updateMutation.mutate()}>
                💾 Save Specification Update
              </button>
              <button
                className={`${fl.btnDanger} flex-1`}
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                🗑️ Delete {selected.resin_name}
              </button>
            </div>
          </>
        )}
      </div>
    </details>
  )
}

// Formlabs Master Resin Specification Lookup Table, ported from
// pages/Mgr_Resin_Canvas.py - the manager-only table with SKU/resin code,
// plus add/edit/delete.
export function ResinCanvasPage() {
  const [format, setFormat] = useState('ALL')
  const [search, setSearch] = useState('')
  const query = useQuery({ queryKey: ['resin-canvas', format, search], queryFn: () => resinCanvasApi.list(format, search) })
  const rows = query.data ?? []

  // The edit/delete picker always offers every formulation, independent of
  // the table's own format/search filters above - same as the original
  // page, whose edit expander reads get_all_resin_specs_df("ALL") on its
  // own rather than reusing the filtered table just above it.
  const allQuery = useQuery({ queryKey: ['resin-canvas', 'ALL', ''], queryFn: () => resinCanvasApi.list('ALL', '') })
  const allRows = allQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>⚖️ Formlabs Master Resin Specification Lookup Table</h1>

      <AddResinForm />

      <div className="flex flex-wrap gap-1">
        {FORMATS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFormat(key)}
            className={`rounded-lg border px-2 py-1.5 text-xs font-medium ${
              format === key
                ? 'border-[#EA580C] bg-[#EA580C]/15 text-[#F97316]'
                : 'border-[#475569] text-[#94A3B8] hover:border-[#EA580C] hover:text-[#F97316]'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-3">
        <input
          className={input}
          placeholder="🔍 Quick Search by SKU, Resin Name, or Code"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="shrink-0 whitespace-nowrap text-sm font-bold text-[#F97316]">
          Showing: {format} ({rows.length} Resins)
        </span>
      </div>

      {rows.length === 0 ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
          ⚖️ No resins in this container format. The master table holds the target fill weight and tolerance
          window every pour is checked against, per resin and per format. Try "ALL" above, or add one under
          "Add New Proprietary Resin Formulation".
        </p>
      ) : (
        <div className={card}>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className={fl.tableHead}>
                <tr>
                  <th className="py-1 pr-2">ID</th><th className="py-1 pr-2">Format</th>
                  <th className="py-1 pr-2">SKU</th><th className="py-1 pr-2">Code</th>
                  <th className="py-1 pr-2">Resin Name</th><th className="py-1 pr-2 text-right">Target (g)</th>
                  <th className="py-1 pr-2 text-right">Min (g)</th><th className="py-1 pr-2 text-right">Max (g)</th>
                  <th className="py-1 pr-2 text-right">Target (kg)</th><th className="py-1 pr-2 text-right">Multiplier</th>
                  <th className="py-1 pr-2 text-right">Lifetime</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className={fl.tableRow}>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.id}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.cartridge_type}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.sku}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{r.resin_code}</td>
                    <td className="py-1 pr-2 font-semibold" style={{ backgroundColor: r.color, color: textColorFor(r.color) }}>
                      {r.resin_name}
                    </td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.actual_spec_g}</td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.min_weight_g}</td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.max_weight_g}</td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.target_kg}</td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.multiplier}</td>
                    <td className="py-1 pr-2 text-right text-[#CBD5E1]">{r.lifetime_months}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <EditDeletePanel rows={allRows} />
    </div>
  )
}
