import { useQuery, useQueryClient } from '@tanstack/react-query'
import { pouringApi } from '../api/pouring'

export function useLotGate(station: string, resin: string, cartCode: string) {
  return useQuery({
    queryKey: ['pouring', 'lot-gate', station, resin, cartCode],
    queryFn: () => pouringApi.lotGate(station, resin, cartCode),
    enabled: !!station && !!resin && !!cartCode,
  })
}

export function useInvalidateLotGate() {
  const queryClient = useQueryClient()
  return (station: string, resin: string, cartCode: string) =>
    queryClient.invalidateQueries({ queryKey: ['pouring', 'lot-gate', station, resin, cartCode] })
}
