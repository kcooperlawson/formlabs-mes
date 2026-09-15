import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { accountApi } from './api/account'
import { referenceApi } from './api/reference'
import { useAuth } from './auth/AuthProvider'
import { ChecklistGate } from './checklist/ChecklistGate'
import { DebugOperatorProvider } from './operatorForm/DebugOperatorContext'
import { AccountPanel } from './shell/AccountPanel'
import { fl } from './theme'
import { AuditTab } from './pouring/AuditTab'
import { DowntimeTab } from './pouring/DowntimeTab'
import { NotesTab } from './pouring/NotesTab'
import { PackingTab } from './pouring/PackingTab'
import { PouringTab } from './pouring/PouringTab'
import { SummaryTab } from './pouring/SummaryTab'

type TabKey = 'pouring' | 'packing' | 'downtime' | 'audit' | 'notes' | 'summary'

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
      <p className="text-sm font-bold text-amber-400">🛠️ Superuser Debug Mode Active</p>
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

  const tabs: { key: TabKey; label: string }[] = [
    isPacker ? { key: 'packing', label: '📦 Packing' } : { key: 'pouring', label: '🧪 Pouring' },
    { key: 'downtime', label: '⚠️ Downtime' },
    { key: 'audit', label: '📸 Audit' },
    { key: 'notes', label: '📋 Notes' },
    { key: 'summary', label: '📊 Summary' },
  ]
  const [tab, setTab] = useState<TabKey>(tabs[0].key)
  const [myStation, setMyStation] = useState('')
  const [showAccount, setShowAccount] = useState(false)
  const [debugAsOperator, setDebugAsOperator] = useState('')

  return (
    <div className="min-h-svh bg-[var(--fl-ground)] p-4">
      <div
        className="mx-auto flex max-w-lg flex-col gap-4 rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-4 shadow-[0_4px_10px_rgba(0,0,0,0.3)] sm:p-6"
        style={{ borderBottomColor: 'var(--fl-accent)', borderBottomWidth: 3 }}
      >
        {isManagement && (
          <button
            onClick={() => navigate('/')}
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
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-current text-sm font-extrabold text-[var(--fl-muted)] opacity-70 hover:opacity-100"
            >
              ?
            </a>
            <div className="relative">
              <button onClick={() => setShowAccount((v) => !v)} title="Account & Preferences" className={`${fl.btnSecondary} px-2.5`}>
                ⚙️
              </button>
              {showAccount && <AccountPanel onClose={() => setShowAccount(false)} />}
            </div>
            <button onClick={logout} className={fl.btnSecondary}>
              Sign out
            </button>
          </div>
        </div>

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
                <button key={t.key} onClick={() => setTab(t.key)} className={tab === t.key ? fl.tabActive : fl.tabInactive}>
                  {t.label}
                </button>
              ))}
            </div>

            {tab === 'pouring' && <PouringTab shift={user?.shift ?? 'Shift 1'} />}
            {tab === 'packing' && <PackingTab />}
            {tab === 'downtime' && <DowntimeTab myStation={myStation} />}
            {tab === 'audit' && <AuditTab myStation={myStation} />}
            {tab === 'notes' && <NotesTab />}
            {tab === 'summary' && <SummaryTab />}
          </ChecklistGate>
        </DebugOperatorProvider>
      </div>
    </div>
  )
}
