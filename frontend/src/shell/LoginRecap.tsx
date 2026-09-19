import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { summaryApi } from '../api/summary'
import { useAuth } from '../auth/AuthProvider'
import { Odometer } from '../tv/PrintBuild'
import { fl } from '../theme'

// A "wrapped"-style card shown once, right after a real sign-in - never
// after a page reload, since justLoggedIn (AuthProvider) only ever flips
// true from the login mutation itself. Fetches lazily (enabled: justLoggedIn)
// so a returning session that never logs in again never even asks.
export function LoginRecap() {
  const { justLoggedIn, clearJustLoggedIn } = useAuth()
  const [displayUnits, setDisplayUnits] = useState(0)

  const query = useQuery({
    queryKey: ['summary', 'monthly'],
    queryFn: summaryApi.monthly,
    enabled: justLoggedIn,
  })

  const recap = query.data
  const show = justLoggedIn && !!recap?.has_data

  // A blank sign-in - nothing logged yet this month - closes the door
  // quietly rather than leaving justLoggedIn stuck true with nothing to show.
  useEffect(() => {
    if (justLoggedIn && query.isSuccess && !recap?.has_data) clearJustLoggedIn()
  }, [justLoggedIn, query.isSuccess, recap, clearJustLoggedIn])

  // Starts the odometer at zero and lets it roll up to the real total a
  // beat later - mounting straight at the final value gives Odometer
  // nothing to transition from, so it would just appear, not count up.
  useEffect(() => {
    if (!show || !recap) return
    setDisplayUnits(0)
    const t = setTimeout(() => setDisplayUnits(recap.units), 300)
    return () => clearTimeout(t)
  }, [show, recap])

  if (!show || !recap) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4"
      onClick={clearJustLoggedIn}
    >
      <div
        className="w-full max-w-sm rounded-2xl border border-[var(--fl-border)] bg-[var(--fl-surface)] p-6 text-center shadow-[0_24px_60px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <p className={`text-xs font-extrabold uppercase tracking-widest ${fl.muted}`}>
          {recap.month_label} so far
        </p>
        <p className="mt-3 text-5xl font-black text-[var(--fl-accent-2)]">
          <Odometer value={displayUnits} uid="recap-units" />
        </p>
        <p className={`mt-1 text-sm ${fl.muted}`}>units poured</p>

        <div className="mt-5 grid grid-cols-2 gap-3">
          {recap.best_day_ordinal && (
            <div className={fl.tile}>
              <p className="text-2xl font-extrabold text-[var(--fl-ink)]">{recap.best_day_ordinal}</p>
              <p className={`text-xs ${fl.muted}`}>best day — {recap.best_day_units.toLocaleString()} units</p>
            </div>
          )}
          <div className={fl.tile}>
            <p className={`text-2xl font-extrabold ${recap.mismatches === 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
              {recap.mismatches}
            </p>
            <p className={`text-xs ${fl.muted}`}>lot mismatch{recap.mismatches === 1 ? '' : 'es'} caught</p>
          </div>
        </div>

        <button className={`${fl.btn} mt-6 w-full`} onClick={clearJustLoggedIn}>
          Let's go
        </button>
      </div>
    </div>
  )
}
