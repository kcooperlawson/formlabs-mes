import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { accountApi, FEEDBACK_CATEGORIES, type MyFeedback } from '../api/account'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { PALETTES, paletteByName } from '../palettes'
import { useToast } from '../toast/ToastProvider'
import { fl } from '../theme'

const input = fl.input
const select = fl.select

const STATUS_COLOR: Record<string, string> = {
  Open: 'text-red-400', 'In Review': 'text-amber-400', Implemented: 'text-emerald-400', Dismissed: `text-[var(--fl-muted)]`,
}

type PanelTab = 'security' | 'avatar' | 'feedback'

const TABS: { key: PanelTab; label: string }[] = [
  { key: 'security', label: '🔑 Security' },
  { key: 'avatar', label: '🎨 Theme & Avatar' },
  { key: 'feedback', label: '💡 Feedback' },
]

function SecurityTab() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [username, setUsername] = useState(user?.username ?? '')
  const [pin, setPin] = useState('')

  const mutation = useMutation({
    mutationFn: () => accountApi.updateCredentials(fullName, username, pin),
    onSuccess: (updated) => {
      queryClient.setQueryData(['auth', 'me'], updated)
      setPin('')
      toast.show('Account credentials updated.')
    },
  })

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-[var(--fl-ink)]">Update Account Credentials</p>
      <label className={`block ${fl.label}`}>Full Display Name</label>
      <input className={input} value={fullName} onChange={(e) => setFullName(e.target.value)} />
      <label className={`block ${fl.label}`}>Username / ID</label>
      <input className={input} value={username} onChange={(e) => setUsername(e.target.value)} />
      <label className={`block ${fl.label}`}>New PIN / Password</label>
      <input className={input} type="password" placeholder="Leave blank to keep current PIN" value={pin} onChange={(e) => setPin(e.target.value)} />
      {mutation.isError && (
        <p className="text-xs text-red-400">
          {mutation.error instanceof ApiError ? mutation.error.message : 'Something went wrong.'}
        </p>
      )}
      <button className={`${fl.btn} mt-1`} disabled={!fullName.trim() || !username.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
        💾 Save Credentials
      </button>
    </div>
  )
}

function ThemeSwatch({ dot }: { dot: string }) {
  return <span className="inline-block h-3 w-3 shrink-0 rounded-full border border-black/20" style={{ backgroundColor: dot }} />
}

function ThemePicker() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const current = paletteByName(user?.preferred_theme)

  const mutation = useMutation({
    mutationFn: (name: string) => accountApi.updateTheme(name),
    onSuccess: (updated) => {
      queryClient.setQueryData(['auth', 'me'], updated)
      toast.show(`Theme set to ${updated.preferred_theme}.`)
    },
  })

  const dark = PALETTES.filter((p) => !p.light)
  const light = PALETTES.filter((p) => p.light)

  return (
    <div>
      <p className="text-sm font-semibold text-[var(--fl-ink)]">Interface Preferences</p>
      <label className={`mt-2 block ${fl.label}`}>System Theme</label>
      <div className="mt-1 flex items-center gap-2">
        <ThemeSwatch dot={current.accent} />
        <select
          className={`${select} flex-1`}
          value={current.name}
          onChange={(e) => mutation.mutate(e.target.value)}
          disabled={mutation.isPending}
        >
          <optgroup label="Dark">
            {dark.map((p) => <option key={p.slug} value={p.name}>{p.name}</option>)}
          </optgroup>
          <optgroup label="Light">
            {light.map((p) => <option key={p.slug} value={p.name}>{p.name}</option>)}
          </optgroup>
        </select>
      </div>
      <p className={`mt-1 text-xs ${fl.muted}`}>
        Saved to your account, so it follows you to any terminal you sign into. A light theme or a
        high-contrast one can read better under bright floor lighting or from further away than this
        one does.
      </p>
    </div>
  )
}

function AvatarTab() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const toast = useToast()
  const fileRef = useRef<HTMLInputElement>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)

  const mutation = useMutation({
    mutationFn: () => accountApi.uploadAvatar(file!),
    onSuccess: (updated) => {
      queryClient.setQueryData(['auth', 'me'], updated)
      setFile(null)
      setPreview(null)
      if (fileRef.current) fileRef.current.value = ''
      toast.show('Avatar updated.')
    },
  })

  const currentSrc = preview ?? (user?.avatar_filename ? accountApi.avatarUrl(user.avatar_filename) : null)

  return (
    <div className="flex flex-col gap-3">
      <ThemePicker />
      <hr className={fl.divider} />
      <div>
        <p className="text-sm font-semibold text-[var(--fl-ink)]">Profile Picture</p>
        <div className="mt-2 flex items-center gap-3">
          {currentSrc ? (
            <img src={currentSrc} alt="Avatar" className="h-16 w-16 shrink-0 rounded-full object-cover" />
          ) : (
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-[var(--fl-ground)] text-2xl">👤</span>
          )}
          <input
            ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp"
            className={`${input} flex-1`}
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null
              setFile(f)
              setPreview(f ? URL.createObjectURL(f) : null)
            }}
          />
        </div>
      </div>
      {mutation.isError && (
        <p className="text-xs text-red-400">
          {mutation.error instanceof ApiError ? mutation.error.message : 'Something went wrong.'}
        </p>
      )}
      <button className={`${fl.btn} self-start`} disabled={!file || mutation.isPending} onClick={() => mutation.mutate()}>
        💾 Save Avatar
      </button>
    </div>
  )
}

function FeedbackHistoryRow({ row }: { row: MyFeedback }) {
  return (
    <div className="rounded-md border border-[var(--fl-border)] bg-[var(--fl-ground)] p-2.5">
      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs font-bold ${STATUS_COLOR[row.status] ?? 'text-[var(--fl-muted)]'}`}>● {row.status.toUpperCase()}</span>
        <span className={`text-xs ${fl.muted}`}>[{row.category}] {row.timestamp ? new Date(row.timestamp).toLocaleDateString() : ''}</span>
      </div>
      <p className="mt-1 text-sm text-[var(--fl-body)]">{row.suggestion}</p>
      {row.admin_notes && <p className="mt-1 text-xs text-sky-300">Note back from IT: {row.admin_notes}</p>}
    </div>
  )
}

function FeedbackTab() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [category, setCategory] = useState<string>(FEEDBACK_CATEGORIES[0])
  const [text, setText] = useState('')

  const historyQuery = useQuery({ queryKey: ['my-feedback'], queryFn: accountApi.myFeedback })
  const toast = useToast()
  const mutation = useMutation({
    mutationFn: () => accountApi.submitFeedback(category, text.trim()),
    onSuccess: () => {
      setText('')
      queryClient.invalidateQueries({ queryKey: ['my-feedback'] })
      toast.show('Feedback submitted.')
    },
  })

  const history = historyQuery.data ?? []

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-[var(--fl-ink)]">Universal Feedback Box</p>
      <p className={`text-xs ${fl.muted}`}>Signed as {user?.full_name}</p>
      <select className={select} value={category} onChange={(e) => setCategory(e.target.value)}>
        {FEEDBACK_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
      </select>
      <textarea
        className={`${input} h-24`} placeholder="Observation / Description"
        value={text} onChange={(e) => setText(e.target.value)}
      />
      <button className={`${fl.btn} self-start`} disabled={!text.trim() || mutation.isPending} onClick={() => mutation.mutate()}>
        🚀 Submit Feedback
      </button>

      {history.length > 0 && (
        <div className="mt-2 flex flex-col gap-2">
          <p className="text-sm font-semibold text-[var(--fl-ink)]">📬 My Submitted Feedback</p>
          {history.map((row) => <FeedbackHistoryRow key={row.id} row={row} />)}
        </div>
      )}
    </div>
  )
}

// The shared "⚙️ Account & Preferences" panel every signed-in role reaches,
// ported from ui_shell.py's render_shell() popover - the one function used
// from all eighteen Streamlit pages.
//
// Rendered as a light, anchored dropdown next to the trigger button, not a
// full-screen modal: the original is a Streamlit st.popover, which floats
// beside the button with no dimmed backdrop, and that lighter feel is most
// of what "looks nicer" was actually about - a modal that darkens the whole
// screen reads as a much heavier interruption for what is a quick
// preferences panel.
//
// The theme picker lives in the "Theme & Avatar" tab (ThemePicker, above) -
// glove-mode/night-dim display toggles are still not ported, a separate,
// pervasive CSS undertaking rather than an account-panel feature.
export function AccountPanel({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<PanelTab>('security')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onPointerDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [onClose])

  return (
    <div
      ref={ref}
      className="fixed inset-x-4 top-20 z-50 rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-4 shadow-[0_12px_32px_rgba(0,0,0,0.55)] sm:inset-x-auto sm:left-auto sm:right-6 sm:w-[26rem]"
    >
      <div className="mb-1 flex items-center justify-between">
        <p className={fl.heading}>⚙️ Account & Preferences</p>
        <button onClick={onClose} className={`${fl.muted} text-lg leading-none hover:text-[var(--fl-ink)]`} aria-label="Close">✕</button>
      </div>
      <div className="flex gap-4 border-b border-[var(--fl-border)]">
        {TABS.map((t) => (
          <button
            key={t.key} onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 pb-2 text-sm font-semibold ${
              tab === t.key ? 'border-[var(--fl-accent)] text-[var(--fl-ink)]' : `border-transparent ${fl.muted} hover:text-[var(--fl-body)]`
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="mt-3 max-h-[70vh] overflow-y-auto">
        {tab === 'security' && <SecurityTab />}
        {tab === 'avatar' && <AvatarTab />}
        {tab === 'feedback' && <FeedbackTab />}
      </div>
    </div>
  )
}
