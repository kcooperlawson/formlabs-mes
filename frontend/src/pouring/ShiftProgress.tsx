import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { summaryApi } from '../api/summary'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { celebrate } from '../shell/Celebrate'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

// What an operator has actually done so far, where they can see it without
// leaving the pouring form. Until now the number lived on the Summary tab,
// which means it only existed if somebody went looking for it - so nobody
// watched it, and there was nothing to push against.
//
// The ring fills toward the next badge - every MILESTONE bottles - rather
// than toward a plant target, because there isn't a per-shift bottle target
// to read and a made-up one would be worse than none. Crossing a badge
// pulses the ring and throws confetti, which is the point: a number that
// reacts is a number people chase.

const MILESTONE = 25

function useCountUp(value: number, ms = 650): number {
  const [shown, setShown] = useState(value)
  const fromRef = useRef(value)

  useEffect(() => {
    const from = fromRef.current
    if (from === value) return
    // Rolling up from the old number rather than snapping: the movement is
    // what makes it read as "that went up", which a replaced digit doesn't.
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      fromRef.current = value
      setShown(value)
      return
    }
    const started = performance.now()
    let frame = 0
    const step = (now: number) => {
      const progress = Math.min(1, (now - started) / ms)
      const eased = 1 - Math.pow(1 - progress, 3)
      setShown(Math.round(from + (value - from) * eased))
      if (progress < 1) frame = requestAnimationFrame(step)
      else fromRef.current = value
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [value, ms])

  return shown
}

export function ShiftProgress() {
  const asOperator = useDebugOperator()
  const query = useQuery({
    queryKey: ['summary', 'today', asOperator],
    queryFn: () => summaryApi.today(asOperator),
    staleTime: 10_000,
  })

  const units = query.data?.units ?? 0
  const shown = useCountUp(units)
  const [popped, setPopped] = useState(0)
  const lastMilestone = useRef<number | null>(null)

  useEffect(() => {
    const reached = Math.floor(units / MILESTONE) * MILESTONE
    if (lastMilestone.current === null) {
      // First load of the page is not an achievement - only movement during
      // this session is.
      lastMilestone.current = reached
      return
    }
    if (reached > lastMilestone.current && reached > 0) {
      lastMilestone.current = reached
      setPopped((n) => n + 1)
      celebrate({ strength: 1.4, label: `${reached} today 🎉` })
    }
  }, [units])

  if (!query.data || (!query.data.has_logs_today && units === 0)) return null

  const nextBadge = (Math.floor(units / MILESTONE) + 1) * MILESTONE
  const pct = ((units % MILESTONE) / MILESTONE) * 100
  const circumference = 2 * Math.PI * 26
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

  return (
    <Drill f={{ date_from: today, date_to: today }} block className="rounded-lg" title="Every log you've made today">
    <div className={`${fl.card} flex items-center gap-3`}>
      <div
        key={popped}
        className="relative shrink-0"
        style={popped ? { animation: 'fl-ring-pop 600ms cubic-bezier(0.22,0.61,0.36,1) both' } : undefined}
      >
        <svg width={64} height={64} viewBox="0 0 64 64" aria-hidden="true">
          <circle cx="32" cy="32" r="26" fill="none" stroke="var(--fl-border)" strokeWidth="6" />
          <circle
            cx="32" cy="32" r="26" fill="none" stroke="var(--fl-accent)" strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - pct / 100)}
            transform="rotate(-90 32 32)"
            style={{ transition: 'stroke-dashoffset 700ms cubic-bezier(0.22,0.61,0.36,1)' }}
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-lg font-extrabold text-[var(--fl-ink)]">
          {shown}
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[var(--fl-ink)]">{shown} logged today</p>
        <p className={`text-xs ${fl.muted}`}>
          {nextBadge - units} to the next badge ({nextBadge})
        </p>
      </div>
    </div>
    </Drill>
  )
}
