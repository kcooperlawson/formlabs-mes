import { useEffect, useState } from 'react'

// Replaces components.py's submit_gate/lock_submit: an
// @st.fragment(run_every="1s") countdown that self-refreshed and, on
// expiry, forced a full-page st.rerun(scope="app") to bring the submit
// button back. Here it's a plain timer with no server round trip at all -
// the whole point of the pilot for this exact mechanic.
const LOCK_SECONDS = 5

export function useSubmitLock() {
  const [until, setUntil] = useState<number | null>(null)
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    if (until === null) {
      setRemaining(0)
      return
    }
    const tick = () => {
      const left = Math.max(0, until - Date.now())
      setRemaining(left)
      if (left === 0) setUntil(null)
    }
    tick()
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [until])

  return {
    locked: remaining > 0,
    secondsLeft: Math.ceil(remaining / 1000),
    lock: () => setUntil(Date.now() + LOCK_SECONDS * 1000),
  }
}
