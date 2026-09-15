import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { reactorsApi } from '../api/reactors'
import { fl } from '../theme'

const input = fl.input
const btn = `${fl.btn} w-full`

// "Log a bulk pour (drum, tote, pail)" from the reactor page, ported from
// Live_Reactors.py - the manager's version of the same bulk-pour mechanic
// the operator form carries under the same enable_bulk_pour switch, for
// the times nobody with a manager login is on the floor. Attributed to
// whichever manager is signed in (api/routers/reactors.py's /bulk-pour),
// not to an operator.
export function BulkPourPanel() {
  const queryClient = useQueryClient()
  const optionsQuery = useQuery({ queryKey: ['reactors', 'manage-options'], queryFn: reactorsApi.manageOptions, retry: false })
  const candidatesQuery = useQuery({
    queryKey: ['reactors', 'bulk-candidates'], queryFn: reactorsApi.bulkCandidates, retry: false,
    enabled: !!optionsQuery.data?.bulk_enabled,
  })

  const [vesselId, setVesselId] = useState<number | null>(null)
  const [containers, setContainers] = useState(1);
  const [amountEach, setAmountEach] = useState(0)
  const [unit, setUnit] = useState<'L' | 'kg'>('L')
  const [note, setNote] = useState('')
  const [result, setResult] = useState<string | null>(null)

  const drawInfoQuery = useQuery({
    queryKey: ['reactors', 'draw-info', vesselId], queryFn: () => reactorsApi.drawInfo(vesselId as number),
    enabled: vesselId !== null,
  })

  const pourMutation = useMutation({
    mutationFn: () => reactorsApi.bulkPour(vesselId as number, { containers, amount_each: amountEach, unit, note }),
    onSuccess: (resp) => {
      setResult(`Recorded ${resp.litres.toLocaleString(undefined, { maximumFractionDigits: 1 })} L.`)
      queryClient.invalidateQueries({ queryKey: ['reactors', 'fleet'] })
      queryClient.invalidateQueries({ queryKey: ['reactors', 'draw-info', vesselId] })
    },
  })

  if (optionsQuery.isError || !optionsQuery.data?.bulk_enabled) return null
  const candidates = candidatesQuery.data ?? []

  return (
    <details className={fl.card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🛢️ Log a bulk pour (drum, tote, pail)</summary>
      <div className="mt-3 flex flex-col gap-2">
        {candidates.length === 0 ? (
          <p className={`text-sm ${fl.muted}`}>No reactor has a resin assigned yet.</p>
        ) : (
          <>
            <select className={input} value={vesselId ?? ''} onChange={(e) => setVesselId(Number(e.target.value))}>
              <option value="">— pick a vessel —</option>
              {candidates.map((c) => (
                <option key={c.id} value={c.id}>{c.label}</option>
              ))}
            </select>

            {drawInfoQuery.data && (
              <p className={`text-xs ${fl.muted}`}>
                Record says <strong className="text-[#CBD5E1]">{drawInfoQuery.data.remaining_l.toLocaleString(undefined, { maximumFractionDigits: 0 })} L</strong>{' '}
                left of {drawInfoQuery.data.capacity_l.toLocaleString()} L
                {drawInfoQuery.data.lot && ` · lot ${drawInfoQuery.data.lot}`} · {drawInfoQuery.data.density_kg_l.toFixed(3)} kg/L
              </p>
            )}

            <div className="grid grid-cols-3 gap-2">
              <input className={input} type="number" min={1} max={99} value={containers} onChange={(e) => setContainers(Number(e.target.value))} placeholder="Containers" />
              <input className={input} type="number" min={0} step="0.01" value={amountEach || ''} onChange={(e) => setAmountEach(Number(e.target.value))} placeholder="Amount each" />
              <select className={input} value={unit} onChange={(e) => setUnit(e.target.value as 'L' | 'kg')}>
                <option value="L">L</option>
                <option value="kg">kg</option>
              </select>
            </div>
            <input className={input} placeholder="Poured into (55 gal drum, blue tote, pail)" maxLength={60} value={note} onChange={(e) => setNote(e.target.value)} />

            {result && <p className="text-sm text-emerald-400">{result}</p>}
            {pourMutation.isError && <p className="text-sm text-red-400">{(pourMutation.error as Error).message}</p>}

            <button className={btn} disabled={!vesselId || amountEach <= 0 || pourMutation.isPending} onClick={() => pourMutation.mutate()}>
              💾 Record this pour
            </button>
          </>
        )}
      </div>
    </details>
  )
}
