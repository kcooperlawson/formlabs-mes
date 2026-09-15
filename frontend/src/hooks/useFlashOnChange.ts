import { useEffect, useRef, useState } from 'react'

// True for a brief moment whenever `value` changes from what it was last
// render - the visible half of the real-time push (useRealtimeInvalidate
// makes the number update instantly; this is what makes that update
// noticeable instead of just correct). Skips the very first render (a page
// that just loaded didn't "change," it arrived) and respects
// prefers-reduced-motion by never flashing at all for anyone who's asked
// for less motion.
export function useFlashOnChange(value: unknown, durationMs = 900): boolean {
  const [flashing, setFlashing] = useState(false)
  const prev = useRef(value)
  const mounted = useRef(false)

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true
      prev.current = value
      return
    }
    if (value === prev.current) return
    prev.current = value
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    setFlashing(true)
    const t = setTimeout(() => setFlashing(false), durationMs)
    return () => clearTimeout(t)
  }, [value, durationMs])

  return flashing
}
