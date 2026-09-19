import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { DrillFilter } from '../api/drill'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { DrillPanel } from './DrillPanel'

// Click any lot, run, pump, operator, resin, vessel or total, anywhere, and a
// panel slides in with everything behind it. One panel for every screen, so a
// lot means the same thing wherever it was clicked from. Clicking inside the
// panel goes deeper and Back comes out again, like a browser.

interface DrillApi {
  open: (filter: DrillFilter) => void
  /** Deeper from inside the panel: keep the trail so Back works. */
  push: (filter: DrillFilter) => void
  back: () => void
  close: () => void
  current: DrillFilter | null
  depth: number
}

const DrillContext = createContext<DrillApi | null>(null)

export function DrillProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<DrillFilter[]>([])

  const open = useCallback((filter: DrillFilter) => setStack([filter]), [])
  const push = useCallback((filter: DrillFilter) => setStack((s) => [...s, filter]), [])
  const back = useCallback(() => setStack((s) => s.slice(0, -1)), [])
  const close = useCallback(() => setStack([]), [])

  useEffect(() => {
    if (!stack.length) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stack.length, close])

  const value = useMemo<DrillApi>(
    () => ({ open, push, back, close, current: stack[stack.length - 1] ?? null, depth: stack.length }),
    [open, push, back, close, stack],
  )

  return (
    <DrillContext.Provider value={value}>
      {children}
      {value.current && <DrillPanel />}
    </DrillContext.Provider>
  )
}

export function useDrill(): DrillApi | null {
  return useContext(DrillContext)
}

function clean(filter: DrillFilter): DrillFilter {
  const out: DrillFilter = {}
  for (const [key, value] of Object.entries(filter) as [keyof DrillFilter, unknown][]) {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      ;(out as Record<string, unknown>)[key] = typeof value === 'string' ? value.trim() : value
    }
  }
  return out
}

/** Something that can be clicked to see what's behind it. Inline by default
 *  (a lot number in a table); `block` makes a whole card the target. Renders
 *  its children untouched when there is nothing worth drilling into - a
 *  blank lot, or a screen with no DrillProvider above it. */
export function Drill({
  f,
  children,
  block = false,
  className = '',
  title,
}: {
  f: DrillFilter
  children: ReactNode
  block?: boolean
  className?: string
  title?: string
}) {
  const drill = useDrill()
  const asOperator = useDebugOperator()
  // Inside the panel there is no operator form above us, so a manager
  // standing in for an operator keeps standing in as they click deeper.
  const filter = clean({ ...f, as_operator: f.as_operator ?? asOperator ?? drill?.current?.as_operator })
  const meaningful = Object.keys(filter).some((k) => k !== 'as_operator' && k !== 'shift')
  const lotIsPlaceholder = filter.lot !== undefined && /^(n\/a|none|null|recon-adj|—|-)$/i.test(String(filter.lot))
  if (!drill || !meaningful || lotIsPlaceholder) return <>{children}</>

  const inPanel = drill.depth > 0
  const go = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (inPanel) drill.push(filter)
    else drill.open(filter)
  }

  if (block) {
    return (
      <div
        role="button"
        tabIndex={0}
        title={title ?? 'See everything behind this'}
        onClick={go}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') go(e)
        }}
        className={`cursor-pointer transition hover:ring-2 hover:ring-[var(--fl-accent)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--fl-accent)] ${className}`}
      >
        {children}
      </div>
    )
  }
  return (
    <button
      type="button"
      title={title ?? 'See everything behind this'}
      onClick={go}
      className={`cursor-pointer text-left underline decoration-dotted decoration-[var(--fl-muted)] underline-offset-2 transition hover:text-[var(--fl-accent-2)] hover:decoration-[var(--fl-accent)] ${className}`}
    >
      {children}
    </button>
  )
}
