import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, BarChart3, Camera, ClipboardList, FlaskConical, HelpCircle, Package, Radio,
  Settings, Wrench, type LucideIcon,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { accountApi } from './api/account'
import { referenceApi } from './api/reference'
import { useAuth } from './auth/AuthProvider'
import { CelebrationLayer } from './shell/Celebrate'
import { ChecklistGate } from './checklist/ChecklistGate'
import { useOfflineQueueCount } from './hooks/useOfflineQueueCount'
import { startOfflineQueue } from './offline/queue'
import { DebugOperatorProvider } from './operatorForm/DebugOperatorContext'
import { AccountPanel } from './shell/AccountPanel'
import { ThemeFlourish, useFlourishVisible } from './shell/ThemeFlourish'
import { hasAnyManagerAbility } from './ManagerShell'
import { paletteByName } from './palettes'
import { fl } from './theme'
import { AuditTab } from './pouring/AuditTab'
import { DowntimeTab } from './pouring/DowntimeTab'
import { NotesTab } from './pouring/NotesTab'
import { PackingTab } from './pouring/PackingTab'
import { PouringTab } from './pouring/PouringTab'
import { SummaryTab } from './pouring/SummaryTab'

type TabKey = 'pouring' | 'packing' | 'downtime' | 'audit' | 'notes' | 'summary'

// Visible on every tab, not just Pouring: a packing or downtime submit can
// queue exactly the same way, and whoever is standing at this screen needs
// to see "this is still going to send" regardless of which tab they're on
// when connectivity actually comes back.
function OfflineQueueBanner() {
  const count = useOfflineQueueCount()
  if (!count) return null
  return (
    <div className="flex items-center gap-2 rounded-lg border border-amber-600 bg-amber-950/40 px-3 py-2 text-sm text-amber-300">
      <Radio size={15} className="shrink-0" />
      {count} {count === 1 ? 'entry' : 'entries'} queued offline — will send the moment the connection is back.
    </div>
  )
}

// Manager_Cockpit.py-style superuser debug block, ported from
// Operator_Form.py lines ~271-286: a manager/admin keeps their own role and
// abilities throughout (the checklist gate below still skips for them
// unconditionally), but can pick a real operator from this selector to
// attribute pours/packing/downtime/audits/notes to that name instead of
// their own - "for system testing" or to log/review on that operator's
// behalf. Not shown to real operators/packers; the picker never rendered
// for them in the original either.
function DebugModeBar({ asOperator, onChange }: { asOperator: string; onChange: (name: string) => void }) {
  const opsQuery = useQuery({ queryKey: ['reference', 'active-operators'], queryFn: referenceApi.activeOperators })
  const names = opsQuery.data ?? []

  return (
    <div className="rounded-lg border border-amber-600 bg-amber-950/40 p-3">
      <p className="flex items-center gap-1.5 text-sm font-bold text-amber-400"><Wrench size={15} /> Superuser Debug Mode Active</p>
      <p className={`mb-2 text-xs ${fl.muted}`}>
        Signed in as Management/Admin. Select an operator to submit logs for system testing, or on their behalf.
      </p>
      <select className={fl.select} value={asOperator} onChange={(e) => onChange(e.target.value)}>
        <option value="">— Log as myself —</option>
        {names.map((n) => (
          <option key={n} value={n}>{n}</option>
        ))}
      </select>
    </div>
  )
}

// The whole Operator Form pilot, assembled: the checklist gate (blocking,
// same as pages/operator_form/checklist.py's st.stop()) in front of a
// role-based tab strip, mirroring Operator_Form.py's own
// `_station_tool_tabs_spec`-style role branching - a packer never sees
// Pouring, an operator never sees Packing.
export function OperatorFormPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const role = user?.role ?? 'operator'
  const isPacker = role === 'packer'
  const isManagement = role === 'manager' || role === 'admin'
  // Debug Mode (impersonating another operator's logs) stays manager/admin
  // only - isManagement, unchanged, still gates that. This is broader: an
  // operator or packer granted a screen like view_scada from IT Admin has
  // nowhere else to reach it from, so the same button managers see now also
  // shows for them, into the same shell filtered down to just what they hold.
  const canSeeManagerShell = isManagement || hasAnyManagerAbility(user)

  const tabs: { key: TabKey; label: string; icon: LucideIcon }[] = [
    isPacker ? { key: 'packing', label: 'Packing', icon: Package } : { key: 'pouring', label: 'Pouring', icon: FlaskConical },
    { key: 'downtime', label: 'Downtime', icon: AlertTriangle },
    { key: 'audit', label: 'Audit', icon: Camera },
    { key: 'notes', label: 'Notes', icon: ClipboardList },
    { key: 'summary', label: 'Summary', icon: BarChart3 },
  ]
  const [tab, setTab] = useState<TabKey>(tabs[0].key)
  const [myStation, setMyStation] = useState('')
  const [showAccount, setShowAccount] = useState(false)
  const [debugAsOperator, setDebugAsOperator] = useState('')

  // Idempotent (see startOfflineQueue's own guard) - safe to call on every
  // mount rather than threading a "did this already happen" flag through
  // the app shell just for this.
  useEffect(() => {
    startOfflineQueue()
  }, [])

  const themeSlug = paletteByName(user?.preferred_theme).slug
  // The card is tall enough on the Pouring tab to fill (and outscroll) the
  // whole phone screen, so a fully opaque card hides the flourish behind it
  // the moment there's real content - only the short "just logged in" state
  // ever left a gap for it to peek through. Going slightly translucent (+ a
  // blur so the glow reads as backdrop, not as illegible text underneath)
  // keeps it visible at any scroll depth instead. Skipped entirely for
  // themes with no flourish to show - no reason to blur a card over nothing.
  const showFlourish = useFlourishVisible(themeSlug)

  return (
    <div className="relative min-h-svh overflow-hidden bg-[var(--fl-ground)] p-4">
      {/* Operators are exactly who this whole feature was described as
          being for ("I want them to be like this is cool to use") - this
          page just never actually got the flourish ManagerShell's had all
          along, on a theme that had one to show. */}
      <ThemeFlourish slug={themeSlug} />
      <div
        className={`relative z-10 mx-auto flex max-w-lg flex-col gap-4 rounded-lg border border-[var(--fl-border)] p-4 shadow-[0_4px_10px_rgba(0,0,0,0.3)] sm:p-6 ${showFlourish ? 'bg-[var(--fl-surface-glass)] backdrop-blur-[3px]' : 'bg-[var(--fl-surface)]'}`}
        style={{ borderBottomColor: 'var(--fl-accent)', borderBottomWidth: 3 }}
      >
        {canSeeManagerShell && (
          <button
            onClick={() => navigate('/cockpit')}
            className="self-start text-sm font-semibold text-[var(--fl-accent-2)] hover:underline"
          >
            ← Manager Cockpit
          </button>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            <img src="/formlabs_logo.png" alt="" className="h-8 w-8 shrink-0 object-contain" />
            {user?.avatar_filename ? (
              <img src={accountApi.avatarUrl(user.avatar_filename)} alt="" className="h-8 w-8 shrink-0 rounded-full object-cover" />
            ) : null}
            <h1 className="truncate text-lg font-bold text-[var(--fl-ink)]">{user?.full_name}</h1>
            <span className={`${fl.badge} shrink-0`}>{user?.shift ?? '—'}</span>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <a
              href="/Formlabs_MES_Operator_Guide.pdf" target="_blank" rel="noopener noreferrer"
              title="Operator guide — how to log an hour, and what to do when something is not right"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-current text-[var(--fl-muted)] opacity-70 hover:opacity-100"
            >
              <HelpCircle size={16} />
            </a>
            <div className="relative">
              <button onClick={() => setShowAccount((v) => !v)} title="Account & Preferences" className={`${fl.btnSecondary} px-2.5`}>
                <Settings size={15} />
              </button>
              {showAccount && <AccountPanel onClose={() => setShowAccount(false)} />}
            </div>
            <button onClick={logout} className={fl.btnSecondary}>
              Sign out
            </button>
          </div>
        </div>

        <CelebrationLayer />

        <OfflineQueueBanner />

        {isManagement && <DebugModeBar asOperator={debugAsOperator} onChange={setDebugAsOperator} />}

        <DebugOperatorProvider value={isManagement && debugAsOperator ? debugAsOperator : undefined}>
          <ChecklistGate
            role={role}
            shift={user?.shift ?? 'Shift 1'}
            station={myStation}
            onStationChange={setMyStation}
          >
            <div className={fl.tabStrip}>
              {tabs.map((t) => (
                <button key={t.key} onClick={() => setTab(t.key)} className={`flex items-center gap-1.5 ${tab === t.key ? fl.tabActive : fl.tabInactive}`}>
                  <t.icon size={14} className="shrink-0" strokeWidth={2.25} /> {t.label}
                </button>
              ))}
            </div>

            {/* key={tab} forces a fresh mount per tab so fl-tab-enter's
                animation replays on every switch, not just the first. */}
            <div key={tab} className="fl-tab-enter">
              {tab === 'pouring' && <PouringTab shift={user?.shift ?? 'Shift 1'} myStation={myStation} />}
              {tab === 'packing' && <PackingTab />}
              {tab === 'downtime' && <DowntimeTab myStation={myStation} />}
              {tab === 'audit' && <AuditTab myStation={myStation} />}
              {tab === 'notes' && <NotesTab />}
              {tab === 'summary' && <SummaryTab />}
            </div>
          </ChecklistGate>
        </DebugOperatorProvider>
      </div>
    </div>
  )
}
