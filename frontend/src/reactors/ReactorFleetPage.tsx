import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { reactorsApi } from '../api/reactors'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'
import { BulkPourPanel } from './BulkPourPanel'
import { ManageFleetPanel } from './ManageFleetPanel'
import { MarkFilledPanel } from './MarkFilledPanel'
import { ReconcileControl } from './ReconcileControl'

const card = fl.card

// Live Reactor Fleet, ported from pages/Live_Reactors.py. The tank
// drawings are api/routers/reactors.py's own vessel_svg() output, embedded
// directly - see that router's docstring for why GET /fleet requires
// view_scada even though the original page's view itself had no explicit
// ability gate.
export function ReactorFleetPage() {
  const queryClient = useQueryClient()
  const fleetQuery = useQuery({ queryKey: ['reactors', 'fleet'], queryFn: reactorsApi.fleet, refetchInterval: 10_000 })

  const markEmptyMutation = useMutation({
    mutationFn: (id: number) => reactorsApi.markEmpty(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reactors', 'fleet'] }),
  })

  const fleet = fleetQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className={fl.heading}>🛢️ Real-Time Reactor Fleet</h1>
        <span className="rounded-full border border-emerald-500 bg-emerald-500/10 px-2 py-0.5 text-xs font-bold text-emerald-400">
          ● LIVE
        </span>
      </div>

      <ManageFleetPanel />
      <MarkFilledPanel reactors={fleet} />
      <BulkPourPanel />

      {fleet.length === 0 ? (
        <p className={`text-sm ${fl.muted}`}>
          No active physical reactors allocated by management. Add them above.
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {fleet.map((r) => (
            <div key={r.id} className="flex flex-col items-center gap-2">
              <p className="text-center text-sm font-bold text-white"><Drill f={{ reactor: r.reactor_name }} title="This vessel's batches and pours">{r.reactor_name}</Drill></p>
              <div
                className="w-full [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
                dangerouslySetInnerHTML={{ __html: r.svg }}
              />
              <div className={`${card} w-full text-center`}>
                <p className={`text-[0.6rem] font-bold uppercase tracking-wide ${fl.muted}`}>
                  Remaining in Tank
                </p>
                <p className="text-sm font-black text-white">
                  {r.remaining_l.toLocaleString(undefined, { maximumFractionDigits: 0 })} L{' '}
                  <span className={`text-xs font-normal ${fl.muted}`}>
                    ({r.remaining_kg.toLocaleString(undefined, { maximumFractionDigits: 0 })} kg)
                  </span>
                </p>
              </div>
              <div className={`${card} w-full text-center text-xs`}>
                {r.is_idle ? (
                  <>
                    <p className={`font-bold ${fl.muted}`}>IDLE / EMPTY</p>
                    <p className={fl.muted}>Available for Setup</p>
                  </>
                ) : (
                  <>
                    <p className="font-bold text-white"><Drill f={{ resin: r.current_resin ?? '' }}>{r.current_resin}</Drill></p>
                    <p className={fl.muted}>
                      Station: {r.assigned_pump ? <Drill f={{ pump: r.assigned_pump }}>{r.assigned_pump}</Drill> : 'Any'} | Lot: {r.lot ? <Drill f={{ lot: r.lot }}>{r.lot}</Drill> : '—'}
                    </p>
                  </>
                )}
              </div>
              {r.batch && (
                <p className={`text-center text-[0.7rem] ${fl.muted}`}>
                  {r.batch.hours_in_reactor == null
                    ? 'age unknown'
                    : r.batch.hours_in_reactor >= 1
                      ? `in the tank ${r.batch.hours_in_reactor.toFixed(0)}h`
                      : 'in the tank under an hour'}{' '}
                  ·{' '}
                  <span className="font-semibold text-[#CBD5E1]">
                    {r.batch.qc_result === 'pass'
                      ? 'QC passed'
                      : r.batch.qc_result === 'fail'
                        ? 'QC FAILED'
                        : r.batch.qc_result === 'hold'
                          ? 'on hold at QC'
                          : r.batch.qc_open
                            ? 'at QC'
                            : 'no QC recorded'}
                  </span>
                </p>
              )}
              {r.can_mark_empty && (
                <button
                  onClick={() => markEmptyMutation.mutate(r.id)}
                  disabled={markEmptyMutation.isPending}
                  className={`${fl.btnSecondary} w-full`}
                >
                  Mark {r.reactor_name} empty
                </button>
              )}
              <ReconcileControl reactor={r} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
