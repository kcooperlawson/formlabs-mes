import { useInstallable } from '../hooks/useInstallable'
import { promptInstall } from './installPrompt'

// Chrome/Android's real, one-tap install - no menu-hunting, no written
// instructions to get wrong. Renders nothing until the browser has
// actually decided this can be installed (a valid manifest, a registered
// service worker, HTTPS - see installPrompt.ts) and nothing once it
// already has been, so there's never a button here that wouldn't work.
//
// iOS Safari has no equivalent API at all - this button simply never
// appears there. That's a real, unsolved gap for iPhone operators, not
// something this component is hiding; worth its own pass (a one-time
// "tap Share, then Add to Home Screen" walkthrough) rather than being
// squeezed in here.
export function InstallButton({ className }: { className?: string }) {
  const installable = useInstallable()
  if (!installable) return null

  return (
    <button type="button" className={className} onClick={() => { void promptInstall() }}>
      📲 Install App on This Phone
    </button>
  )
}
