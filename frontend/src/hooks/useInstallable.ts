import { useSyncExternalStore } from 'react'
import { getInstallableSnapshot, subscribeInstallable } from '../pwa/installPrompt'

// True once Chrome/Android has decided this app can be installed and
// hasn't been yet - see pwa/installPrompt.ts. Always false on iOS, and on
// desktop unless the browser also supports installable PWAs there.
export function useInstallable(): boolean {
  return useSyncExternalStore(subscribeInstallable, getInstallableSnapshot)
}
