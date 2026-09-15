import { useQuery, useQueryClient } from '@tanstack/react-query'
import { pouringApi } from '../api/pouring'

// The changeover mechanic's whole client side: an onChange handler updates
// station/resin state, and this re-fetches only when they actually change.
// Compare to pouring_tab.py, where picking either fires a full-page rerun
// that recomputes the equivalent block before anything else repaints.
export function useReactorLookup(station: string, resin: string) {
  return useQuery({
    queryKey: ['pouring', 'reactor-lookup', station, resin],
    queryFn: () => pouringApi.reactorLookup(station, resin),
    enabled: !!station && !!resin,
  })
}

// After a changeover/link/mark-empty write, the lookup for this exact
// station+resin is stale - invalidate just that one query, not the world.
export function useInvalidateReactorLookup() {
  const queryClient = useQueryClient()
  return (station: string, resin: string) =>
    queryClient.invalidateQueries({ queryKey: ['pouring', 'reactor-lookup', station, resin] })
}
