import { Share, SquarePlus, X } from 'lucide-react'
import { useEffect, useState } from 'react'

const DISMISSED_KEY = 'mes-ios-install-hint-dismissed'

// Safari on iOS gives web apps no beforeinstallprompt-style API at all -
// Apple's own restriction, not something this app can route around (see
// InstallButton.tsx for the Android side, which does get a real one-tap
// install). The best available fix here isn't a button, it's not leaving
// an iPhone operator to go find instructions: this shows itself, once,
// pointing at the exact two icons they need to tap in Safari's own UI.
function isIOS(): boolean {
  const ua = navigator.userAgent
  // iPadOS 13+ reports as desktop Safari on "MacIntel" - Apple's own
  // recommended way to tell it apart from an actual Mac is that a Mac has
  // no touch points at all.
  const isAppleTouchDevice = /iPad|iPhone|iPod/.test(ua)
  const isIpadOS13Plus = navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
  return isAppleTouchDevice || isIpadOS13Plus
}

function isSafari(): boolean {
  // Every browser on iOS is required to use Safari's own engine and ships
  // "Safari" in its UA regardless - Chrome/Firefox/Edge on iOS carry their
  // own token too, which is what actually tells them apart. Worth
  // narrowing to Safari specifically: it's the one Apple documents "Add to
  // Home Screen" for, and other iOS browsers' own share sheets don't
  // reliably offer the same real-standalone-app result.
  const ua = navigator.userAgent
  return /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua)
}

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

export function IosInstallHint() {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (isStandalone() || !isIOS() || !isSafari()) return
    try {
      if (localStorage.getItem(DISMISSED_KEY)) return
    } catch {
      // Private browsing or storage blocked - fine to just show it; the
      // worst case is seeing this again next visit, not a broken page.
    }
    setShow(true)
  }, [])

  if (!show) return null

  const dismiss = () => {
    setShow(false)
    try { localStorage.setItem(DISMISSED_KEY, '1') } catch { /* see above */ }
  }

  return (
    <div className="mt-4 rounded border border-[#334155] bg-[#1E293B] p-4 text-sm text-[#CBD5E1]">
      <div className="flex items-start justify-between gap-3">
        <p className="font-bold text-white">Add this to your Home Screen</p>
        <button type="button" onClick={dismiss} aria-label="Dismiss" className="shrink-0 text-[#94A3B8] hover:text-white">
          <X size={18} />
        </button>
      </div>
      <ol className="mt-3 flex flex-col gap-2">
        <li className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0F172A] font-mono text-xs">1</span>
          Tap <Share size={16} className="inline shrink-0 text-[#00D2FF]" aria-hidden /> at the bottom of Safari
        </li>
        <li className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#0F172A] font-mono text-xs">2</span>
          Scroll down and tap <SquarePlus size={16} className="inline shrink-0 text-[#00D2FF]" aria-hidden /> <b>Add to Home Screen</b>
        </li>
      </ol>
      <p className="mt-3 text-xs text-[#94A3B8]">
        It opens like an app after that - no address bar, one tap from your lock screen.
      </p>
    </div>
  )
}
