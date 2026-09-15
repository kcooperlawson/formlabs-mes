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

registerSW({ immediate: true })

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
