import { useEffect, useState } from 'react'
import { fl } from '../theme'

interface UndoState {
  logId: number
  units: number
  expiresAt: number
}

interface Props {
  canSubmit: boolean
  blockers: string[]
  locked: boolean
  lockSecondsLeft: number
  isSubmitting: boolean
  onSubmit: () => void
  undo: UndoState | null
  onUndo: () => void
  isUndoing: boolean
}

const btn = `w-full ${fl.btn} py-4 text-base`

// The undo window's own fixed length (crud.py's UNDO_WINDOW_SECONDS) - not
// derived from undo.expiresAt because this component only ever sees the
// window already in progress, never its start time. Used purely to turn a
// seconds-left count into a fraction for the ring below.
const UNDO_WINDOW_SECONDS = 120

// A small ring that drains as the undo window closes, instead of making
// someone read "47s left" and do the math themselves - a glance at the
// button says how much runway is left, the same way a real countdown timer
// would, right where the thumb is about to tap.
function UndoRing({ secondsLeft }: { secondsLeft: number }) {
  const r = 9
  const c = 2 * Math.PI * r
  const fraction = Math.max(0, Math.min(1, secondsLeft / UNDO_WINDOW_SECONDS))
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" className="shrink-0 -rotate-90">
      <circle cx="11" cy="11" r={r} fill="none" stroke="var(--fl-border)" strokeWidth="2.5" />
      <circle
        cx="11" cy="11" r={r} fill="none" stroke="var(--fl-accent-2)" strokeWidth="2.5"
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - fraction)}
        style={{ transition: 'stroke-dashoffset 1s linear' }}
      />
    </svg>
  )
}

// The submit button itself, ported from pouring_tab.py lines ~657-803 and
// components.py's submit_gate/lock_submit for the post-submit lock. Also
// hosts the undo banner (UNDO_WINDOW_SECONDS=120, crud.undo_own_log) since
// it lives right next to the button that created the log, same as the
// original - the person who mistyped a number is standing right here.
export function SubmitBar({
  canSubmit, blockers, locked, lockSecondsLeft, isSubmitting, onSubmit, undo, onUndo, isUndoing,
}: Props) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    if (!undo) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [undo])

  const undoSecondsLeft = undo ? Math.max(0, Math.round((undo.expiresAt - now) / 1000)) : 0
  const showUndo = undo && undoSecondsLeft > 0

  if (locked) {
    return (
      <div className="rounded-lg border border-emerald-800 bg-emerald-950 px-4 py-4 text-center text-sm font-medium text-emerald-300">
        ✅ Logged — {lockSecondsLeft}s
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {showUndo && (
        <div className={`flex items-center justify-between gap-2 text-sm text-[#CBD5E1] ${fl.card}`}>
          <span>
            Last entry: <strong className="text-white">{undo.units.toLocaleString()} units</strong> ({undoSecondsLeft}s left to undo)
          </span>
          <button onClick={onUndo} disabled={isUndoing} className={`${fl.btnSecondary} flex items-center gap-1.5`}>
            <UndoRing secondsLeft={undoSecondsLeft} /> Undo last
          </button>
        </div>
      )}

      {blockers.length > 0 && (
        <p className={`text-xs ${fl.muted}`}>
          Before you can submit: {blockers.join('; ')}.
        </p>
      )}

      <button className={btn} disabled={!canSubmit || isSubmitting} onClick={onSubmit}>
        {isSubmitting ? 'Submitting…' : '🚀 SUBMIT POURING LOG'}
      </button>
    </div>
  )
}
