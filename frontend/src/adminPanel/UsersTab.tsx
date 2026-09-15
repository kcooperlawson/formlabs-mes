import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { adminApi, type AdminUser } from '../api/admin'
import { fl } from '../theme'

const card = fl.card
const input = fl.input
const select = fl.select

const ROLES = ['operator', 'packer', 'manager', 'admin']
const SHIFTS = ['Shift 1', 'Shift 2', 'Floater']

function ProvisionForm({ onCreated }: { onCreated: () => void }) {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [pin, setPin] = useState('')
  const [role, setRole] = useState('operator')
  const [shift, setShift] = useState('Shift 1')
  const [targetLph, setTargetLph] = useState(400)

  const mutation = useMutation({
    mutationFn: () => adminApi.createUser({ full_name: fullName, email, username, pin, role, shift, target_lph: targetLph }),
    onSuccess: () => {
      setFullName(''); setEmail(''); setUsername(''); setPin('')
      onCreated()
    },
  })

  return (
    <div className={`${card} flex flex-col gap-2`}>
      <p className="text-sm font-semibold text-white">➕ Provision New User</p>
      <input className={input} placeholder="Full Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
      <input className={input} placeholder="Work Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input className={input} placeholder="Username / ID" value={username} onChange={(e) => setUsername(e.target.value)} />
      <input className={input} type="password" placeholder="PIN / Password" value={pin} onChange={(e) => setPin(e.target.value)} />
      <select className={select} value={role} onChange={(e) => setRole(e.target.value)}>
        {ROLES.map((r) => <option key={r} value={r}>{r[0].toUpperCase() + r.slice(1)}</option>)}
      </select>
      <select className={select} value={shift} onChange={(e) => setShift(e.target.value)}>
        {SHIFTS.map((s) => <option key={s}>{s}</option>)}
      </select>
      <label className={`block ${fl.label}`}>Target Rate (L/h)</label>
      <input className={input} type="number" step={10} value={targetLph} onChange={(e) => setTargetLph(Number(e.target.value))} />
      {mutation.isError && <p className="text-xs text-red-400">{(mutation.error as Error).message}</p>}
      <button className={fl.btn} disabled={!fullName || !email || !username || !pin || mutation.isPending}
             onClick={() => mutation.mutate()}>
        Create Account
      </button>
    </div>
  )
}

function RosterTable({ users }: { users: AdminUser[] }) {
  return (
    <div className={card}>
      <p className="mb-2 text-sm font-semibold text-white">📋 Current Staff Database</p>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className={fl.tableHead}>
            <tr>
              <th className="py-1 pr-2">ID</th><th className="py-1 pr-2">Name</th>
              <th className="py-1 pr-2">Username</th><th className="py-1 pr-2">Email</th>
              <th className="py-1 pr-2">Role</th><th className="py-1 pr-2">Shift</th>
              <th className="py-1 pr-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className={fl.tableRow}>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.id}</td>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.full_name}</td>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.username}</td>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.email}</td>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.role}</td>
                <td className="py-1 pr-2 text-[#CBD5E1]">{u.shift}</td>
                <td className="py-1 pr-2">
                  {u.is_locked
                    ? <span className="text-xs font-semibold text-red-400">🔒 Locked ({u.locked_minutes_left}m)</span>
                    : <span className="text-xs font-semibold text-emerald-400">✅ Active</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ModifyRoleShift({ users, onDone }: { users: AdminUser[]; onDone: () => void }) {
  const [userId, setUserId] = useState<number | ''>('')
  const [role, setRole] = useState('operator')
  const [shift, setShift] = useState('Shift 1')
  const mutation = useMutation({
    mutationFn: () => adminApi.updateRoleShift(userId as number, role, shift),
    onSuccess: onDone,
  })
  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🛠️ Modify User Role &amp; Shift Assignment</summary>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <select className={select} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
          <option value="">— choose —</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <select className={select} value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((r) => <option key={r}>{r}</option>)}
        </select>
        <select className={select} value={shift} onChange={(e) => setShift(e.target.value)}>
          {SHIFTS.map((s) => <option key={s}>{s}</option>)}
        </select>
        <button className={`${fl.btn} sm:w-40`} disabled={!userId || mutation.isPending} onClick={() => mutation.mutate()}>
          💾 Apply
        </button>
      </div>
    </details>
  )
}

function AbilitiesPanel({ users }: { users: AdminUser[] }) {
  const queryClient = useQueryClient()
  const [userId, setUserId] = useState<number | ''>('')
  const sheetQuery = useQuery({
    queryKey: ['admin-abilities', userId],
    queryFn: () => adminApi.userAbilities(userId as number),
    enabled: userId !== '',
  })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-abilities', userId] })
  const grantMutation = useMutation({ mutationFn: (key: string) => adminApi.grantAbility(userId as number, key), onSuccess: invalidate })
  const revokeMutation = useMutation({ mutationFn: (key: string) => adminApi.revokeAbility(userId as number, key), onSuccess: invalidate })

  const sheet = sheetQuery.data

  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🎟️ Extra Abilities</summary>
      <p className={`mt-2 text-xs ${fl.muted}`}>
        Give one account something its role does not include. The person keeps their role everywhere else.
      </p>
      <select className={`${select} mt-2`} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
        <option value="">— choose personnel —</option>
        {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
      </select>

      {sheet && (
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm text-white">
            <b>{sheet.full_name}</b> — role <code className="text-[#F97316]">{sheet.role}</code>
          </p>
          <div className="flex flex-col gap-1.5">
            {sheet.abilities.map((a) => {
              const heldByRole = a.status === 'role'
              const checked = a.status !== ''
              const disabled = heldByRole || !a.can_grant
              return (
                <label key={a.key} className="flex items-start gap-2 text-sm text-[#CBD5E1]" title={a.help}>
                  <input
                    type="checkbox" className="mt-0.5" checked={checked} disabled={disabled}
                    onChange={(e) => {
                      if (e.target.checked) grantMutation.mutate(a.key)
                      else revokeMutation.mutate(a.key)
                    }}
                  />
                  <span>
                    {a.label}
                    {heldByRole && <span className={`ml-2 text-xs ${fl.muted}`}>(comes with this role)</span>}
                    {!heldByRole && !a.can_grant && <span className={`ml-2 text-xs ${fl.muted}`}>(you don't hold this yourself)</span>}
                  </span>
                </label>
              )
            })}
          </div>

          {sheet.history.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#94A3B8]">History</p>
              <ul className="mt-1 flex flex-col gap-0.5">
                {sheet.history.slice(0, 12).map((h, i) => (
                  <li key={i} className={`text-xs ${fl.muted}`}>
                    {h.active
                      ? `✅ ${h.label} — given by ${h.granted_by ?? 'somebody'} on ${h.granted_at ? new Date(h.granted_at).toLocaleString() : '?'}`
                      : `↩️ ${h.label} — given by ${h.granted_by ?? 'somebody'}, removed by ${h.revoked_by ?? 'somebody'} on ${h.revoked_at ? new Date(h.revoked_at).toLocaleString() : '?'}`}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </details>
  )
}

function ResetPinPanel({ users, onDone }: { users: AdminUser[]; onDone: () => void }) {
  const [userId, setUserId] = useState<number | ''>('')
  const [pin, setPin] = useState('')
  const mutation = useMutation({ mutationFn: () => adminApi.resetPin(userId as number, pin), onSuccess: () => { setPin(''); onDone() } })
  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🔑 Reset User PIN</summary>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <select className={select} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
          <option value="">— choose —</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <input className={input} type="password" placeholder="New PIN" value={pin} onChange={(e) => setPin(e.target.value)} />
        <button className={`${fl.btn} sm:w-40`} disabled={!userId || !pin || mutation.isPending} onClick={() => mutation.mutate()}>
          💾 Reset PIN
        </button>
      </div>
      {mutation.isError && <p className="mt-1 text-xs text-red-400">{(mutation.error as Error).message}</p>}
    </details>
  )
}

function UnlockPanel({ users, onDone }: { users: AdminUser[]; onDone: () => void }) {
  const locked = users.filter((u) => u.is_locked)
  const [userId, setUserId] = useState<number | ''>('')
  const mutation = useMutation({ mutationFn: () => adminApi.unlockUser(userId as number), onSuccess: onDone })
  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🔓 Unlock Account</summary>
      {locked.length === 0 ? (
        <p className={`mt-2 text-xs ${fl.muted}`}>No accounts are currently locked out.</p>
      ) : (
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <select className={select} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
            <option value="">— choose —</option>
            {locked.map((u) => <option key={u.id} value={u.id}>{u.username} ({u.locked_minutes_left}m left)</option>)}
          </select>
          <button className={`${fl.btn} sm:w-40`} disabled={!userId || mutation.isPending} onClick={() => mutation.mutate()}>
            🔓 Unlock Now
          </button>
        </div>
      )}
    </details>
  )
}

function TerminatePanel({ users, currentUsername, onDone }: { users: AdminUser[]; currentUsername: string; onDone: () => void }) {
  const [userId, setUserId] = useState<number | ''>('')
  const mutation = useMutation({ mutationFn: () => adminApi.deleteUser(userId as number), onSuccess: () => { setUserId(''); onDone() } })
  const target = users.find((u) => u.id === userId)
  const isSelf = target?.username === currentUsername
  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">⚠️ Terminate Account</summary>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <select className={select} value={userId} onChange={(e) => setUserId(Number(e.target.value))}>
          <option value="">— choose —</option>
          {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
        </select>
        <button className={`${fl.btnDanger} sm:w-40`} disabled={!userId || isSelf || mutation.isPending} onClick={() => mutation.mutate()}>
          🗑️ Delete User
        </button>
      </div>
      {isSelf && <p className="mt-1 text-xs text-red-400">You cannot delete your own admin account!</p>}
      {mutation.isError && <p className="mt-1 text-xs text-red-400">{(mutation.error as Error).message}</p>}
    </details>
  )
}

export function UsersTab({ currentUsername }: { currentUsername: string }) {
  const queryClient = useQueryClient()
  const usersQuery = useQuery({ queryKey: ['admin-users'], queryFn: adminApi.users })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-users'] })
  const users = usersQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <ProvisionForm onCreated={invalidate} />
        <RosterTable users={users} />
      </div>
      <ModifyRoleShift users={users} onDone={invalidate} />
      <AbilitiesPanel users={users} />
      <ResetPinPanel users={users} onDone={invalidate} />
      <UnlockPanel users={users} onDone={invalidate} />
      <TerminatePanel users={users} currentUsername={currentUsername} onDone={invalidate} />
    </div>
  )
}
