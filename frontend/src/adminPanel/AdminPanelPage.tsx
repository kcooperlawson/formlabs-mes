import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { adminApi } from '../api/admin'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { fl } from '../theme'
import { CrashReportsTab } from './CrashReportsTab'
import { DatabaseTab } from './DatabaseTab'
import { SettingsTab } from './SettingsTab'
import { SuggestionsTab } from './SuggestionsTab'
import { UpdatesTab } from './UpdatesTab'
import { UsersTab } from './UsersTab'

type TabKey = 'users' | 'suggestions' | 'crashes' | 'database' | 'settings' | 'updates'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'users', label: '👥 User Management & Roster' },
  { key: 'suggestions', label: '💡 Suggestions & Issue Inbox' },
  { key: 'crashes', label: '🐞 Crash Reports' },
  { key: 'database', label: '📜 System & Database Utilities' },
  { key: 'settings', label: '⚙️ Plant Configuration' },
  { key: 'updates', label: '🆙 Updates' },
]

// IT Admin Console, ported from pages/Admin_Panel.py. Gated server-side by
// crud.can_administer (an admin always reaches it; so does a manager on a
// plant running in simple/logging mode) - every request here can come back
// 403, in which case the page just says so rather than assuming access.
export function AdminPanelPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<TabKey>('users')

  // A gate check up front, same as every other console-only endpoint would
  // 403 anyway - this way the page says so once instead of five tabs each
  // failing their own query silently.
  const gateQuery = useQuery({ queryKey: ['admin-users'], queryFn: adminApi.users, retry: false })

  if (gateQuery.isLoading) return null
  if (gateQuery.isError) {
    const denied = gateQuery.error instanceof ApiError && gateQuery.error.status === 403
    return (
      <div className="flex flex-col gap-4">
        <h1 className={fl.heading}>🛡️ IT Admin Console</h1>
        <p className={`${fl.card} py-6 text-center text-sm text-red-400`}>
          {denied
            ? '🔒 Access Denied: Restricted to Plant Management.'
            : 'Could not reach the admin console.'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className={fl.heading}>🛡️ IT Admin Console</h1>
        <a
          href="/Formlabs_MES_Update_Guide.pdf" target="_blank" rel="noopener noreferrer"
          className={`text-xs ${fl.muted} hover:text-[#F97316]`}
        >
          🧰 Update process (PDF)
        </a>
      </div>

      <div className={fl.tabStrip}>
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={tab === t.key ? fl.tabActive : fl.tabInactive}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'users' && <UsersTab currentUsername={user?.username ?? ''} />}
      {tab === 'suggestions' && <SuggestionsTab />}
      {tab === 'crashes' && <CrashReportsTab />}
      {tab === 'database' && <DatabaseTab />}
      {tab === 'settings' && <SettingsTab />}
      {tab === 'updates' && <UpdatesTab />}
    </div>
  )
}
