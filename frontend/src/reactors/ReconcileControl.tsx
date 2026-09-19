import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { reactorsApi, type ReactorCard } from '../api/reactors'
import { fl } from '../theme'

const input = `${fl.input} py-1.5 text-sm`

// The Streamlit-era app let a manager (or an operator) read a tank's sight
// glass and correct the record to match - CHANGELOG 3.x's "Real tank
// reconciliation". That never got carried into this rewrite, so a level
// that drifted for any reason (a mis-logged pour, a resin swap nobody
// confirmed) had no fix short of a developer editing the database. This is
// that control, restored: per-card rather than a shared panel, since
// unlike marking a tank filled or empty, reconciling only makes sense
// against a specific number somebody is looking at on a specific tank.
export function ReconcileControl({ reactor }: { reactor: ReactorCard }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'percent' | 'liters'>('percent')
  const [value, setValue] = useState('')
  const [notes, setNotes] = useState('')

  const mutation = useMutation({
    mutationFn: () => reactorsApi.reconcile(reactor.id, { mode, value: Number(value), notes }),
    onSuccess: () => {
      setOpen(false)
      setValue('')
      setNotes('')
      queryClient.invalidateQueries({ queryKey: ['reactors', 'fleet'] })
    },
  })

  if (reactor.is_idle || !reactor.can_manage) return null

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className={`${fl.btnSecondary} w-full`}>
        🎯 Reconcile level
      </button>
    )
  }

  return (
    <div className={`${fl.card} w-full text-left`}>
      <p className={`text-xs ${fl.muted}`}>
        What does the sight glass on {reactor.reactor_name} actually show right now?
      </p>
      <div className="mt-2 flex gap-1">
        <select className={input} value={mode} onChange={(e) => setMode(e.target.value as 'percent' | 'liters')}>
          <option value="percent">% full</option>
          <option value="liters">Litres remaining</option>
        </select>
        <input
          className={input} type="number" min={0} max={mode === 'percent' ? 100 : undefined}
          placeholder={mode === 'percent' ? '0-100' : 'L'} value={value}
          onChange={(e) => setValue(e.target.value)}
        />
      </div>
      <input
        className={`${input} mt-1 w-full`} placeholder="Note (optional)" maxLength={240}
        value={notes} onChange={(e) => setNotes(e.target.value)}
      />
      {mutation.isError && <p className="mt-1 text-xs text-red-400">{(mutation.error as Error).message}</p>}
      <div className="mt-2 flex gap-1">
        <button
          className={`${fl.btn} flex-1 py-1.5 text-xs`} disabled={!value || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          Save
        </button>
        <button className={`${fl.btnSecondary} flex-1`} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </div>
  )
}
