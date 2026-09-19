// Captures Chrome/Android's `beforeinstallprompt` event the moment it
// fires so a later "Install App" button can trigger the native install
// dialog on demand - the event fires once per page load and is gone for
// good if nothing was listening yet, so this has to be a plain module-
// level listener (registered the instant this file is imported), not
// something set up inside a component that might not have mounted yet.
//
// iOS Safari never fires this event at all - Apple provides no
// programmatic install path there - so getInstallableSnapshot() simply
// never turns true on an iPhone, and anything built on top of this hook
// correctly renders nothing rather than a button that would do nothing.
//
// Same pub-sub shape as offline/queue.ts's subscribeQueueCount /
// getQueueCountSnapshot, for the same reason: this is state a component
// needs to react to that changes from outside React entirely.
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

type Listener = () => void
const listeners = new Set<Listener>()
let deferredEvent: BeforeInstallPromptEvent | null = null
let installed = isStandalone()

function isStandalone(): boolean {
  try {
    return (
      window.matchMedia('(display-mode: standalone)').matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true
    )
  } catch {
    return false
  }
}

function notify() {
  for (const listener of listeners) listener()
}

window.addEventListener('beforeinstallprompt', (e) => {
  // Stops Chrome's own mini-infobar so the app's own button is the one
  // and only prompt an operator sees, rather than both.
  e.preventDefault()
  deferredEvent = e as BeforeInstallPromptEvent
  notify()
})

window.addEventListener('appinstalled', () => {
  deferredEvent = null
  installed = true
  notify()
})

export function subscribeInstallable(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getInstallableSnapshot(): boolean {
  return deferredEvent !== null && !installed
}

// Must be called from directly inside a click handler - browsers refuse
// to show the native dialog otherwise. The captured event is single-use
// regardless of what the operator picks, so this clears it either way;
// if Chrome decides to offer it again it will fire a fresh
// beforeinstallprompt on a later page load.
export async function promptInstall(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
  if (!deferredEvent) return 'unavailable'
  const event = deferredEvent
  deferredEvent = null
  notify()
  await event.prompt()
  return (await event.userChoice).outcome
}
