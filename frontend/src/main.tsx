import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
// vite-plugin-pwa's virtual module - only exists in a built/dev-served app
// (vite.config.ts's VitePWA plugin generates it), not under plain `tsc`.
// registerType: 'autoUpdate' means this both installs the service worker on
// first load and swaps in a new one the moment a fresh build is available,
// with no "click to update" prompt to add to an operator's shift.
import { registerSW } from 'virtual:pwa-register'
import App from './App.tsx'
import { AuthProvider } from './auth/AuthProvider.tsx'
import { ThemeRoot } from './ThemeRoot.tsx'
import { ToastProvider } from './toast/ToastProvider.tsx'
import './index.css'
// Side-effect import: registers the beforeinstallprompt listener the
// instant this bundle evaluates, so it's guaranteed to be in place before
// Chrome could ever fire the (once-only) event - see pwa/installPrompt.ts.
import './pwa/installPrompt.ts'
import { primeAudio } from './sound/chimes.ts'

registerSW({ immediate: true })

// Unlocks the shared AudioContext on the very first real interaction
// anywhere in the app - Safari refuses to start audio at all unless that
// happens inside a genuine user gesture, and by the time a sound cue is
// actually due (a log landing, a lot mismatch) the gesture that triggered
// it has usually already ended. Removes itself after firing once.
window.addEventListener('pointerdown', primeAudio, { once: true })

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeRoot>
          <ToastProvider>
            <BrowserRouter>
              <App />
            </BrowserRouter>
          </ToastProvider>
        </ThemeRoot>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
