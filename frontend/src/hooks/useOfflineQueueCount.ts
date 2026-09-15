import { useSyncExternalStore } from 'react'
import { getQueueCountSnapshot, subscribeQueueCount } from '../offline/queue'

// How many pouring/packing/downtime submissions are sitting in IndexedDB
// waiting for the network to come back - see offline/queue.ts.
export function useOfflineQueueCount(): number {
  return useSyncExternalStore(subscribeQueueCount, getQueueCountSnapshot)
}
