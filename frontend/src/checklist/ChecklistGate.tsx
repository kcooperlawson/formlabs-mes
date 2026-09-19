import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ReactNode, useEffect, useState } from 'react'
import { checklistApi } from '../api/checklist'
import { referenceApi } from '../api/reference'
import { useToast } from '../toast/ToastProvider'
import { ScreenSweep } from '../tv/PrintBuild'
import { fl } from '../theme'

const input = `${fl.input} py-3 text-base font-normal text-[var(--fl-ink)]`
const btn = `${fl.btn} w-full py-3`
const panel = fl.card

interface Props {
  role: string
  shift: string
  station: string
  onStationChange: (s: string) => void
  children: ReactNode
}

// The hard gate, ported from pages/operator_form/checklist.py's
// render_checklist_gate(): st.stop() there becomes "don't render children"
// here. Only enforced for operators and packers, exactly like the original
// ("Only enforced for Operators and Packers, not Managers in Debug mode").
export function ChecklistGate({ role, shift, station, onStationChange, children }: Props) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const isPacker = role === 'packer'
  const effectiveStation = isPacker ? 'Pack-Out Station' : station
  const [showUnlock, setShowUnlock] = useState(false)

  useEffect(() => {
    if (!showUnlock) return
    const t = setTimeout(() => setShowUnlock(false), 2500)
    return () => clearTimeout(t)
  }, [showUnlock])

  const pumpsQuery = useQuery({
    queryKey: ['reference', 'pumps'],
    queryFn: referenceApi.pumps,
    enabled: !isPacker && role !== 'manager' && role !== 'admin',
  })
  const statusQuery = useQuery({
    queryKey: ['checklist', 'status', effectiveStation, shift],
    queryFn: () => checklistApi.status(effectiveStation, shift),
    enabled: !!effectiveStation && (role === 'operator' || role === 'packer'),
  })
  const vesselQuery = useQuery({
    queryKey: ['checklist', 'vessel-options', effectiveStation],
    queryFn: () => checklistApi.vesselOptions(effectiveStation),
    enabled: !!effectiveStation && !isPacker,
  })

  const [notes, setNotes] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [skipPhoto, setSkipPhoto] = useState(false)
  const [vesselPick, setVesselPick] = useState('')
  const [qrChecked, setQrChecked] = useState(false)
  const [materialsChecked, setMaterialsChecked] = useState(false)
  const [alreadyWho, setAlreadyWho] = useState('')
  // Reopened on purpose after it was already completed. The checklist screen
  // carries the pump startup form link, and an operator moving to a second
  // pump needs that link again - the screen itself won't come back on its
  // own, because as far as the shift is concerned the checklist is done.
  const [reopened, setReopened] = useState(false)

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['checklist', 'status', effectiveStation, shift] })
    queryClient.invalidateQueries({ queryKey: ['checklist', 'vessel-options', effectiveStation] })
  }

  const cleanlinessMutation = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.set('station', effectiveStation)
      fd.set('shift', shift)
      fd.set('notes', notes)
      fd.set('skip_photo', String(skipPhoto))
      if (photo) fd.set('photos', photo)
      return checklistApi.submitCleanliness(fd)
    },
    onSuccess: () => {
      invalidate()
      toast.show('Cleanliness report saved.')
    },
  })

  const submitMutation = useMutation({
    mutationFn: () =>
      checklistApi.submit({
        station: effectiveStation, shift, qr_checked: qrChecked, materials_checked: materialsChecked,
        vessel_reactor_name: vesselPick && !vesselPick.startsWith('—') ? vesselPick : null,
      }),
    onSuccess: () => {
      invalidate()
      setShowUnlock(true)
      toast.show('Terminal unlocked.')
    },
  })

  const overrideMutation = useMutation({
    mutationFn: () => checklistApi.markAlreadyDone({ station: effectiveStation, shift, already_who: alreadyWho }),
    onSuccess: () => {
      invalidate()
      setShowUnlock(true)
      toast.show('Terminal unlocked.')
    },
  })

  if (role !== 'operator' && role !== 'packer') return <>{children}</>
  if (!effectiveStation && !isPacker) {
    return (
      <div className={panel}>
        <label className={`mb-1 block ${fl.label}`}>Which pump station are you starting at?</label>
        <select className={input} value={station} onChange={(e) => onStationChange(e.target.value)}>
          <option value="">— choose —</option>
          {(pumpsQuery.data ?? []).map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>
    )
  }
  if (!statusQuery.data) return null
  if (statusQuery.data.checklist_done && !reopened) {
    return (
      <>
        {showUnlock && <ScreenSweep />}
        {/* Plays once, only for the terminal that just unlocked - a
            returning terminal whose checklist was already done stays a
            plain mount, so nobody sees a fade-in replay on every reload. */}
        <div style={showUnlock ? { animation: 'fl-fade-up 420ms cubic-bezier(0.22,0.61,0.36,1) both' } : undefined}>
          <div className="mb-2 flex justify-end">
            <button className={fl.btnSecondary} onClick={() => { setShowUnlock(false); setReopened(true) }}>
              📋 Startup checklist
            </button>
          </div>
          {children}
        </div>
      </>
    )
  }

  const cleanlinessDone = statusQuery.data.cleanliness_done_today

  return (
    <div className="flex flex-col gap-3">
      {reopened ? (
        <div className="flex items-center justify-between gap-2 rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3 text-sm">
          <p className="text-[var(--fl-body)]">
            📋 Startup checklist for <strong className="text-white">{effectiveStation}</strong> — already done this
            shift. Open it for the pump startup form, or to redo it after moving to another pump.
          </p>
          <button className={fl.btnSecondary} onClick={() => setReopened(false)}>← Back to the form</button>
        </div>
      ) : (
        <div className="rounded-lg border border-red-800 bg-red-950 p-3 text-sm text-red-300">
          <p className="font-semibold">🛑 TERMINAL LOCKED: PRE-SHIFT VALIDATION REQUIRED</p>
          <p>
            Complete the startup checklist for <strong>{effectiveStation}</strong> on{' '}
            <strong>{shift}</strong> before the production modules unlock.
          </p>
        </div>
      )}

      {!isPacker && (
        <div>
          <label className={`mb-1 block ${fl.label}`}>📍 Which pump station are you starting at?</label>
          <select className={input} value={station} onChange={(e) => onStationChange(e.target.value)}>
            {(pumpsQuery.data ?? []).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
      )}

      {!isPacker && vesselQuery.data && !vesselQuery.data.has_vessel && vesselQuery.data.options.length > 0 && (
        <div>
          <label className={`mb-1 block ${fl.label}`}>🛢️ Which vessel does this pump draw from?</label>
          <select className={input} value={vesselPick} onChange={(e) => setVesselPick(e.target.value)}>
            <option value="">— I don't know —</option>
            {vesselQuery.data.options.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      <details className="text-sm">
        <summary className={`cursor-pointer ${fl.muted}`}>
          🕒 Temporary: this pump was already checked today
        </summary>
        <div className="mt-2 flex flex-col gap-2">
          <input
            className={input}
            placeholder="Who actually completed the checklist? e.g. Maria"
            value={alreadyWho}
            onChange={(e) => setAlreadyWho(e.target.value)}
          />
          <button
            className={btn}
            disabled={!alreadyWho.trim() || overrideMutation.isPending}
            onClick={() => overrideMutation.mutate()}
          >
            ✅ Mark already done & unlock this terminal
          </button>
        </div>
      </details>

      <h3 className="text-sm font-semibold text-[var(--fl-ink)]">📋 Daily Startup Checklist</h3>

      {!cleanlinessDone || reopened ? (
        <div className={panel}>
          <p className="mb-2 text-sm font-medium text-[var(--fl-ink)]">Step 1: Morning Cleanliness Check</p>
          {cleanlinessDone && (
            <p className="mb-2 text-xs text-emerald-400">
              ✅ Already logged today — this logs a separate entry, e.g. for a second operator taking over this pump.
            </p>
          )}
          <textarea
            className={input}
            rows={2}
            placeholder="Station clean, ready for shift."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <label className="mt-2 flex items-center gap-2 text-sm text-[var(--fl-body)]">
            <input
              type="checkbox"
              checked={skipPhoto}
              onChange={(e) => { setSkipPhoto(e.target.checked); if (e.target.checked) setPhoto(null) }}
            />
            ✅ Station is clean — skip the photo
          </label>
          {!skipPhoto && (
            <input
              className="mt-2 block text-sm text-[var(--fl-body)]"
              type="file"
              accept="image/*"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            />
          )}
          <button
            className={`${btn} mt-2`}
            disabled={(!skipPhoto && !photo) || cleanlinessMutation.isPending}
            onClick={() => cleanlinessMutation.mutate()}
          >
            💾 Submit Cleanliness Report
          </button>
        </div>
      ) : (
        <p className="text-sm text-emerald-400">
          ✅ Step 1: Morning Cleanliness Check — LOGGED & COMPLETED
        </p>
      )}

      <div className={panel}>
        <p className="mb-2 text-sm font-medium text-[var(--fl-ink)]">Step 2: Final Verification</p>
        <label className="mb-2 flex items-center gap-2 text-sm text-[var(--fl-body)]">
          <input type="checkbox" checked={qrChecked} onChange={(e) => setQrChecked(e.target.checked)} />
          I have scanned the daily station QR code and submitted the external checksheet.
        </label>
        <label className="mb-2 flex items-center gap-2 text-sm text-[var(--fl-body)]">
          <input type="checkbox" checked={materialsChecked} onChange={(e) => setMaterialsChecked(e.target.checked)} />
          {isPacker
            ? 'I have verified all labels, boxes, and necessary materials are staged for my pack-out run.'
            : 'I have verified all bins of empty cartridges and receiving carts for filled bottles are staged for my run.'}
        </label>
        <button
          className={btn}
          disabled={!qrChecked || !materialsChecked || !cleanlinessDone || submitMutation.isPending}
          onClick={() => submitMutation.mutate()}
        >
          🔓 Submit Validation & Unlock Terminal
        </button>
        {submitMutation.isError && (
          <p className="mt-2 text-sm text-red-400">{(submitMutation.error as Error).message}</p>
        )}
      </div>
    </div>
  )
}
