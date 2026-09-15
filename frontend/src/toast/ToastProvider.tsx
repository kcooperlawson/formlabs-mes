import { createContext, type ReactNode, useCallback, useContext, useRef, useState } from 'react'

type ToastKind = 'success' | 'error'
interface ToastItem {
  id: number
  message: string
  kind: ToastKind
  leaving: boolean
}

interface ToastApi {
  show: (message: string, kind?: ToastKind) => void
}

const ToastContext = createContext<ToastApi | null>(null)

// A bottom-of-screen confirmation toast, restoring what st.toast() used to
// give the original app for free on every credential/avatar/theme save -
// this port had been showing that same confirmation as a static inline
// line instead, which is easy to miss on a phone mid-shift. One shared
// instance rather than a per-page implementation, the same reasoning as
// every other shell-level piece of chrome.
const LIFETIME_MS = 3200
const EXIT_MS = 260

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextId = useRef(0)

  const show = useCallback((message: string, kind: ToastKind = 'success') => {
    const id = ++nextId.current
    setToasts((prev) => [...prev, { id, message, kind, leaving: false }])
    window.setTimeout(() => {
      setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
      window.setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, EXIT_MS)
    }, LIFETIME_MS)
  }, [])

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[200] flex flex-col items-center gap-2 px-4">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto w-full max-w-sm rounded-lg border px-4 py-2.5 text-sm font-semibold shadow-[var(--fl-shadow-hover)] ${
              t.kind === 'success'
                ? 'border-[var(--fl-accent)] bg-[var(--fl-surface)] text-[var(--fl-ink)]'
                : 'border-red-700 bg-red-950 text-red-200'
            }`}
            style={{
              animation: `${t.leaving ? 'fl-toast-out' : 'fl-toast-in'} ${EXIT_MS}ms cubic-bezier(0.22,0.61,0.36,1) both`,
            }}
          >
            {t.kind === 'success' ? '✅ ' : '⚠️ '}{t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast() called outside <ToastProvider>')
  return ctx
}
