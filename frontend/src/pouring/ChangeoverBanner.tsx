import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { pouringApi } from '../api/pouring'
import { useInvalidateReactorLookup, useReactorLookup } from '../hooks/useReactorLookup'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { fl } from '../theme'

interface Props {
  station: string
  resin: string
  shift: string
  /** Bumped by the parent on every successful submit, so the tank icon
   * below can "gulp" once right when a pour actually lands - see
   * PouringTab.tsx's pourTick. */
  pourTick?: number
}

const banner = 'rounded-lg border px-3 py-2 text-sm'
const warn = `${banner} border-amber-800 bg-amber-950 text-amber-200`
const info = `${banner} border-[#334155] bg-[#1E293B] text-[#CBD5E1]`
const btn = `mt-2 ${fl.btn}`

// The one genuinely tricky mechanic, ported from pouring_tab.py's inline
// vessel block (lines ~134-257). There, picking a station or resin fired a
// full-page Streamlit rerun to recompute this exact panel before anything
// else repainted. Here it's a plain onChange -> fetch (see
// useReactorLookup): only this component re-renders.
export function ChangeoverBanner({ station, resin, shift, pourTick }: Props) {
  const { data, isLoading } = useReactorLookup(station, resin)
  const invalidate = useInvalidateReactorLookup()
  const asOperator = useDebugOperator()
  const [vesselPick, setVesselPick] = useState('')

  const changeoverMutation = useMutation({
    mutationFn: (reactorName: string) => pouringApi.changeover(reactorName, resin, station, shift, asOperator),
    onSuccess: () => invalidate(station, resin),
  })
  const linkMutation = useMutation({
    mutationFn: (reactorName: string) => pouringApi.linkVessel(reactorName, station),
    onSuccess: () => {
      invalidate(station, resin)
      setVesselPick('')
    },
  })
  const markEmptyMutation = useMutation({
    mutationFn: (reactorName: string) => pouringApi.markEmpty(reactorName, asOperator),
    onSuccess: () => invalidate(station, resin),
  })

  if (isLoading || !data) return null

  if (data.status === 'blank') {
    return (
      <p className={info}>
        🛢️ {data.vessel!.tag} has no resin recorded yet. Logging this will record it as
        holding {resin}.
      </p>
    )
  }

  if (data.status === 'changeover') {
    const v = data.vessel!
    return (
      <div className={warn}>
        <p>
          <strong>
            {v.tag} is recorded as holding {data.current_resin}, and you have picked {resin}.
          </strong>
        </p>
        <button
          className={btn}
          disabled={changeoverMutation.isPending}
          onClick={() => changeoverMutation.mutate(v.reactor_name)}
        >
          ✅ Yes — {v.tag} was changed over to {resin}
        </button>
      </div>
    )
  }

  if (data.status === 'no_vessel') {
    return (
      <div className={warn}>
        <p>
          <strong>No vessel is linked to this station.</strong> Your log still records and
          still counts. It only means the tank level will not move until this is answered.
        </p>
        {data.options.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              className={fl.select}
              value={vesselPick}
              onChange={(e) => setVesselPick(e.target.value)}
            >
              <option value="">— pick one —</option>
              {data.options.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button
              className={btn.replace('mt-2', '')}
              disabled={!vesselPick || linkMutation.isPending}
              onClick={() => linkMutation.mutate(vesselPick)}
            >
              🔗 Link to {station}
            </button>
          </div>
        )}
      </div>
    )
  }

  if (data.status === 'ambiguous') {
    return (
      <p className={warn}>
        More than one vessel is set to this station and resin ({data.vessel_names.join(', ')}),
        so the level cannot tell which one this came out of. Your lead can fix that on the
        reactor page.
      </p>
    )
  }

  // status === 'matched'
  const v = data.vessel!
  const batch = data.batch
  return (
    <div className={info}>
      <p>
        <span key={pourTick || 0} className={pourTick ? 'fl-gulp' : ''}>🛢️</span> Drawing from <strong>{v.tag}</strong>
        {v.bay_marker ? ` · bay ${v.bay_marker}` : ''}
      </p>
      {batch?.qc_result === 'fail' && (
        <p className="mt-1 text-amber-400">
          ⚠️ This tank's batch failed QC. Your log still records. Check with your lead before
          you pour any more of it.
        </p>
      )}
      {batch?.qc_result === 'hold' && (
        <p className="mt-1 text-amber-400">
          ⚠️ This tank's batch is on hold at QC. Your log still records. Worth a word with your
          lead.
        </p>
      )}
      {batch && !batch.qc_result && batch.qc_open && (
        <p className="mt-1">🧪 A sample from this tank is out at QC. Nothing to do, it is just not back yet.</p>
      )}
      {batch && data.can_mark_empty && (
        <div className="mt-2 flex items-center justify-between gap-2">
          <span>
            {batch.hours_in_reactor != null &&
              (batch.hours_in_reactor >= 1
                ? `⏱️ In the tank ${batch.hours_in_reactor.toFixed(0)}h so far.`
                : '⏱️ In the tank under an hour.')}
          </span>
          <button
            className={btn.replace('mt-2', '')}
            disabled={markEmptyMutation.isPending}
            onClick={() => markEmptyMutation.mutate(v.reactor_name)}
          >
            🛢️ Mark empty
          </button>
        </div>
      )}
    </div>
  )
}
