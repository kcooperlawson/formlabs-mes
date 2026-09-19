import { useEffect, useState } from 'react'
import { flourishesDisabled } from './ThemeFlourish'

// The moment a pour actually lands. An operator does this dozens of times a
// shift, and until now it was a toast and a buzz - correct, and completely
// forgettable. This is the one place in the app worth spending a little
// theatre on, because it is the thing they repeat all day.
//
// Drawn in the current theme's own colours (the --fl-* tokens), so it reads
// as part of whichever theme they picked rather than a bolted-on party
// trick. Off entirely under prefers-reduced-motion or the app's own
// "background animations off" switch - the same two gates every other
// flourish here respects.

const EVENT = 'mes-celebrate'

export interface CelebrationDetail {
  /** How good this was FOR THIS PUMP: 1 is an ordinary hour there, 2 is
      twice its usual. Not a raw count - 100 bottles is a strong hour on an
      old pump and a slow one on a new one, so a burst sized by the number
      alone would tell an operator on the old pumps that they had done badly
      every single time. */
  strength?: number
  /** A line across the middle, for something worth naming. */
  label?: string
}

export function celebrate(detail: CelebrationDetail = {}) {
  window.dispatchEvent(new CustomEvent(EVENT, { detail }))
}

function reducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

interface Piece {
  id: number
  left: number
  delay: number
  duration: number
  size: number
  hue: string
  drift: number
  spin: number
}

const COLOURS = ['var(--fl-accent)', 'var(--fl-accent-2)', 'var(--fl-ink)', 'var(--fl-body)']

let nextId = 0

function makePieces(count: number): Piece[] {
  return Array.from({ length: count }, () => ({
    id: nextId++,
    left: Math.random() * 100,
    delay: Math.random() * 120,
    duration: 900 + Math.random() * 700,
    size: 6 + Math.random() * 7,
    hue: COLOURS[Math.floor(Math.random() * COLOURS.length)],
    drift: (Math.random() - 0.5) * 140,
    spin: (Math.random() - 0.5) * 720,
  }))
}

/** Mounted once, high in the tree. Listens for celebrate() and draws it. */
export function CelebrationLayer() {
  const [pieces, setPieces] = useState<Piece[]>([])
  const [label, setLabel] = useState<string | null>(null)

  useEffect(() => {
    const onCelebrate = (event: Event) => {
      if (reducedMotion() || flourishesDisabled()) return
      const detail = (event as CustomEvent<CelebrationDetail>).detail ?? {}
      // An ordinary hour for that pump is a decent burst; a record is the
      // full screen. Floors at a real celebration either way - every logged
      // pour is worth something.
      const strength = Math.max(0.35, Math.min(3, detail.strength ?? 1))
      const count = Math.round(16 + strength * 22)
      setPieces(makePieces(count))
      setLabel(detail.label ?? null)
      window.setTimeout(() => setPieces([]), 1800)
      window.setTimeout(() => setLabel(null), 1600)
    }
    window.addEventListener(EVENT, onCelebrate)
    return () => window.removeEventListener(EVENT, onCelebrate)
  }, [])

  if (pieces.length === 0 && !label) return null

  return (
    <div className="pointer-events-none fixed inset-0 z-[60] overflow-hidden" aria-hidden="true">
      {pieces.map((piece) => (
        <span
          key={piece.id}
          className="absolute top-0 block rounded-[2px]"
          style={{
            left: `${piece.left}%`,
            width: piece.size,
            height: piece.size * 1.6,
            background: piece.hue,
            opacity: 0.9,
            animation: `fl-confetti ${piece.duration}ms cubic-bezier(0.22,0.61,0.36,1) ${piece.delay}ms both`,
            ['--fl-drift' as string]: `${piece.drift}px`,
            ['--fl-spin' as string]: `${piece.spin}deg`,
          }}
        />
      ))}
      {label && (
        <div className="absolute inset-x-0 top-1/3 flex justify-center">
          <span
            className="rounded-full border border-[var(--fl-accent)] bg-[var(--fl-surface)]/95 px-4 py-2 text-lg font-extrabold text-[var(--fl-accent)] shadow-lg"
            style={{ animation: 'fl-milestone 1500ms cubic-bezier(0.22,0.61,0.36,1) both' }}
          >
            {label}
          </span>
        </div>
      )}
    </div>
  )
}
