import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { reactorsApi, type ReactorCard } from '../api/reactors'
import { fl } from '../theme'

const input = fl.input
const btn = `${fl.btn} w-full`

// Management's own counterpart to each card's "Mark empty" button, ported
// from this session's fix for reactor.py's mark_reactor_filled(): filling
// has always been something the app INFERRED from an operator confirming a
// resin changeover at the pump, never something anyone could just say
// happened. That misses a vessel filled for the first time (nothing to
// change over FROM) and topping off with the same resin (not a change at
// all) - both leave a vessel holding product with no fill time on record.
// This is that missing, deliberate action - one shared panel with a vessel
// picker, the same shape as BulkPourPanel right below it, rather than a
// per-card form that would need a resin picker and a lot field jammed into
// an already-dense tile.
export function MarkFilledPanel({ reactors }: { reactors: ReactorCard[] }) {
  const queryClient = useQueryClient()
  const optionsQuery = useQuery({ queryKey: ['reactors', 'manage-options'], queryFn: reactorsApi.manageOptions, retry: false })

  const [vesselId, setVesselId] = useState<number | null>(null)
  const [resin, setResin] = useState('')
  const [lotNumber, setLotNumber] = useState('')
  const [filledAt, setFilledAt] = useState('')
  const [note, setNote] = useState('')
  const [result, setResult] = useState<string | null>(null)

  const markFilledMutation = useMutation({
    mutationFn: () =>
      reactorsApi.markFilled(vesselId as number, {
        resin_type: resin, lot_number: lotNumber,
        filled_at: filledAt ? new Date(filledAt).toISOString() : null, note,
      }),
    onSuccess: () => {
      setResult('Marked filled.')
      setLotNumber(''); setFilledAt(''); setNote('')
      queryClient.invalidateQueries({ queryKey: ['reactors', 'fleet'] })
    },
  })

  // manage-options is already gated to manage_reactors on the backend - a
  // 403 here means this account shouldn't see the panel at all, the same
  // way BulkPourPanel piggybacks on the same call rather than checking the
  // ability a second time.
  if (optionsQuery.isError) return null
  const resins = optionsQuery.data?.resins ?? []

  return (
    <details className={fl.card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🪣 Mark a reactor filled</summary>
      <div className="mt-3 flex flex-col gap-2">
        <p className={`text-xs ${fl.muted}`}>
          For a vessel filled directly rather than through an operator's changeover at the pump — a first fill, a
          top-up on the same resin, or catching up the record after the fact. Leave the time blank to use right now.
        </p>
        <select className={input} value={vesselId ?? ''} onChange={(e) => setVesselId(Number(e.target.value))}>
          <option value="">— pick a vessel —</option>
          {reactors.map((r) => (
            <option key={r.id} value={r.id}>
              {r.reactor_name}{r.current_resin ? ` (currently ${r.current_resin})` : ' (idle)'}
            </option>
          ))}
        </select>
        <select className={input} value={resin} onChange={(e) => setResin(e.target.value)}>
          <option value="">— pick a resin —</option>
          {resins.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <div className="grid grid-cols-2 gap-2">
          <input className={input} placeholder="Lot number" value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} />
          <input
            className={input} type="datetime-local" value={filledAt}
            onChange={(e) => setFilledAt(e.target.value)} title="Leave blank to use right now"
          />
        </div>
        <input className={input} placeholder="Note (optional)" maxLength={240} value={note} onChange={(e) => setNote(e.target.value)} />

        {result && <p className="text-sm text-emerald-400">{result}</p>}
        {markFilledMutation.isError && <p className="text-sm text-red-400">{(markFilledMutation.error as Error).message}</p>}

        <button className={btn} disabled={!vesselId || !resin || markFilledMutation.isPending} onClick={() => markFilledMutation.mutate()}>
          💾 Mark filled
        </button>
      </div>
    </details>
  )
}
