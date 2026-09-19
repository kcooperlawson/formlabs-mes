import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { downtimeApi } from '../api/downtime'
import { referenceApi } from '../api/reference'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { enqueue, isConnectivityError } from '../offline/queue'
import { playLogged } from '../sound/chimes'
import { useToast } from '../toast/ToastProvider'
import { fl } from '../theme'

const input = `${fl.input} py-3 text-base font-normal text-[#F8FAFC]`
const label = `mb-1 block ${fl.label}`
const btn = `w-full ${fl.btn} py-3`

// Ported from pages/operator_form/downtime_tab.py - already the simplest
// tab in the original (a plain st.form, nothing reads another field's live
// value), so there's no live cross-field logic to reproduce here.
export function DowntimeTab({ myStation }: { myStation: string }) {
  const asOperator = useDebugOperator()
  const toast = useToast()
  const pumpsQuery = useQuery({ queryKey: ['reference', 'pumps'], queryFn: referenceApi.pumps })
  const reasonsQuery = useQuery({
    queryKey: ['reference', 'downtime-reasons'],
    queryFn: referenceApi.downtimeReasons,
  })

  const [station, setStation] = useState(myStation)
  const [reason, setReason] = useState('')
  const [duration, setDuration] = useState(15)
  const [notes, setNotes] = useState('')
  // A running downtime. Kept as the moment it started rather than as a
  // counter, so the number stays right if the screen sleeps, the tab is
  // backgrounded, or the phone is in a pocket for twenty minutes - which is
  // exactly when downtime happens.
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const [, forceTick] = useState(0)

  useEffect(() => {
    if (startedAt === null) return
    const id = window.setInterval(() => forceTick((n) => n + 1), 1000)
    return () => window.clearInterval(id)
  }, [startedAt])

  const runningSeconds = startedAt === null ? 0 : Math.floor((Date.now() - startedAt) / 1000)
  const runningLabel = `${String(Math.floor(runningSeconds / 60)).padStart(2, '0')}:${String(runningSeconds % 60).padStart(2, '0')}`

  const submitMutation = useMutation({
    mutationFn: () => downtimeApi.submit({ station, reason, duration_min: duration, notes, as_operator: asOperator }),
    onSuccess: (resp) => {
      setNotes('')
      toast.show(resp.message)
      playLogged()
    },
    onError: (err) => {
      if (!isConnectivityError(err)) return
      void enqueue('downtime', Object.entries({
        station, reason, duration_min: String(duration), notes, as_operator: asOperator ?? '',
      }))
      setNotes('')
      toast.show('Recorded offline — queued to send.')
      submitMutation.reset()
      setStartedAt(null)
    },
  })

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-[var(--fl-body)]">
        Station Downtime Event Logger
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={label}>Downtime Station</label>
          <select className={input} value={station} onChange={(e) => setStation(e.target.value)}>
            <option value="">— choose —</option>
            {(pumpsQuery.data ?? []).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={label}>Reason for Downtime</label>
          <select className={input} value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">— choose —</option>
            {(reasonsQuery.data ?? []).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
        <div className="sm:col-span-2">
          <label className={label}>Time it as it happens</label>
          {startedAt === null ? (
            <button
              className={`${fl.btnSecondary} mt-1 w-full`}
              disabled={!station || !reason}
              onClick={() => setStartedAt(Date.now())}
            >
              ▶️ Start timing {reason ? `“${reason}”` : '(pick a reason first)'}
            </button>
          ) : (
            <div className="mt-1 flex items-center gap-2">
              <span className="flex-1 rounded border border-[var(--fl-accent)] bg-[var(--fl-surface)] px-3 py-2 text-lg font-extrabold tabular-nums text-[var(--fl-accent)]">
                ⏱️ {runningLabel}
              </span>
              <button
                className={fl.btn}
                onClick={() => {
                  // Always at least a minute: a stop two seconds after a
                  // start is a mis-tap, and a zero would quietly buy back
                  // pace credit for time that was really lost.
                  setDuration(Math.max(1, Math.round(runningSeconds / 60)))
                  setStartedAt(null)
                }}
              >
                ⏹️ Stop
              </button>
              <button className={fl.btnSecondary} onClick={() => setStartedAt(null)}>✕</button>
            </div>
          )}
          <p className={`mt-1 text-xs ${fl.muted}`}>
            Or just type the minutes below. The timer only fills that box in — nothing is recorded until you submit.
          </p>
        </div>

        <div>
          <label className={label}>Downtime Duration (Minutes)</label>
          <input
            className={input}
            type="number"
            min={1}
            max={240}
            step={5}
            value={duration || ''}
            onChange={(e) => setDuration(Number(e.target.value))}
          />
        </div>
        <div>
          <label className={label}>Corrective Action Taken</label>
          <input
            className={input}
            placeholder="Cleaned dispensing valve nozzle."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>

      <button
        className={btn}
        disabled={!station || !reason || submitMutation.isPending}
        onClick={() => submitMutation.mutate()}
      >
        ⚠️ Record Downtime Event
      </button>
    </div>
  )
}
