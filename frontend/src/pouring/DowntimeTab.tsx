import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { downtimeApi } from '../api/downtime'
import { referenceApi } from '../api/reference'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
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

  const submitMutation = useMutation({
    mutationFn: () => downtimeApi.submit({ station, reason, duration_min: duration, notes, as_operator: asOperator }),
    onSuccess: (resp) => {
      setNotes('')
      toast.show(resp.message)
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
        <div>
          <label className={label}>Downtime Duration (Minutes)</label>
          <input
            className={input}
            type="number"
            min={1}
            max={240}
            step={5}
            value={duration}
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
