import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

// Wakes a live dashboard the instant a pour/pack/downtime lands, instead of
// waiting for its own poll interval - see api/realtime.py and the
// GET /ws/updates handler in api/main.py for the other half of this.
//
// Carries no data of its own: every message just means "something changed,
// go re-fetch" - queryKeys is invalidated exactly like a mutation's own
// onSuccess would, so this is additive to the existing refetchInterval
// polling (kept as a fallback) rather than a replacement for it. A dropped
// connection reconnects with backoff on its own; the worst case if it never
// reconnects is the screen behaves exactly as it did before this existed.
export function useRealtimeInvalidate(queryKeys: unknown[][]) {
  const queryClient = useQueryClient()
  const keysRef = useRef(queryKeys)
  keysRef.current = queryKeys

  useEffect(() => {
    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let stopped = false
    let attempt = 0

    function connect() {
      if (stopped) return
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${scheme}//${location.host}/ws/updates`)

      socket.onmessage = () => {
        for (const key of keysRef.current) {
          queryClient.invalidateQueries({ queryKey: key })
        }
      }
      socket.onopen = () => {
        attempt = 0
      }
      socket.onclose = () => {
        if (stopped) return
        // Backoff rather than a fixed interval - a plant PC rebooting or a
        // brief network blip shouldn't turn into every open tab hammering
        // the same endpoint in lockstep every second.
        const delay = Math.min(1000 * 2 ** attempt, 30_000)
        attempt += 1
        reconnectTimer = setTimeout(connect, delay)
      }
    }

    connect()
    return () => {
      stopped = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [queryClient])
}
