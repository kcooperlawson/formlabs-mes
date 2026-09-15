import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { rosterApi } from '../api/roster'
import { fl } from '../theme'

const input = fl.input
const btn = `${fl.btn} w-full`
const card = fl.card

// Floor Personnel Administration, ported from pages/Mgr_Roster.py. Managers
// provision/reset floor accounts only (operator/packer) - IT Admins handle
// management accounts and terminations elsewhere, per the original page's
// own security notice.
export function RosterPage() {
  const queryClient = useQueryClient()
  const rosterQuery = useQuery({ queryKey: ['roster'], queryFn: rosterApi.list })

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [pin, setPin] = useState('')
  const [role, setRole] = useState<'operator' | 'packer'>('operator')
  const [shift, setShift] = useState('Shift 1')

  const [resetUserId, setResetUserId] = useState<number | ''>('')
  const [resetPin, setResetPin] = useState('')

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['roster'] })

  const provisionMutation = useMutation({
    mutationFn: () => rosterApi.provision({ full_name: fullName, email, username, pin, role, shift }),
    onSuccess: () => {
      setFullName(''); setEmail(''); setUsername(''); setPin('')
      invalidate()
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => rosterApi.resetPin(resetUserId as number, resetPin),
    onSuccess: () => setResetPin(''),
  })

  const roster = rosterQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>👥 Floor Personnel Administration</h1>
      <p className="rounded-lg border border-sky-800 bg-sky-950 px-3 py-2 text-sm text-sky-200">
        💡 Managers can provision and manage floor personnel. IT Admins manage management accounts and terminations.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-[280px_1fr]">
        <div className={`${card} flex flex-col gap-2`}>
          <p className="text-sm font-semibold text-white">➕ Provision Floor Personnel</p>
          <input className={input} placeholder="Full Name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <input className={input} placeholder="Work Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className={input} placeholder="Username / ID" value={username} onChange={(e) => setUsername(e.target.value)} />
          <input className={input} type="password" placeholder="PIN / Password" value={pin} onChange={(e) => setPin(e.target.value)} />
          <select className={input} value={role} onChange={(e) => setRole(e.target.value as 'operator' | 'packer')}>
            <option value="operator">Operator</option>
            <option value="packer">Packer</option>
          </select>
          <select className={input} value={shift} onChange={(e) => setShift(e.target.value)}>
            <option>Shift 1</option>
            <option>Shift 2</option>
            <option>Floater</option>
          </select>
          {provisionMutation.isError && (
            <p className="text-xs text-red-400">{(provisionMutation.error as Error).message}</p>
          )}
          <button className={btn} disabled={!fullName || !email || !username || !pin || provisionMutation.isPending}
                 onClick={() => provisionMutation.mutate()}>
            Create Personnel
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <div className={card}>
            <p className="mb-2 text-sm font-semibold text-white">📋 Floor Roster</p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className={fl.tableHead}>
                  <tr>
                    <th className="py-1 pr-2">ID</th>
                    <th className="py-1 pr-2">Name</th>
                    <th className="py-1 pr-2">Username</th>
                    <th className="py-1 pr-2">Role</th>
                    <th className="py-1 pr-2">Shift</th>
                  </tr>
                </thead>
                <tbody>
                  {roster.map((u) => (
                    <tr key={u.id} className={fl.tableRow}>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{u.id}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{u.full_name}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{u.username}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{u.role}</td>
                      <td className="py-1 pr-2 text-[#CBD5E1]">{u.shift}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {roster.length === 0 && <p className={`py-2 text-sm ${fl.muted}`}>No floor personnel found.</p>}
            </div>
          </div>

          <details className={card}>
            <summary className="cursor-pointer text-sm font-medium text-white">🔑 Reset Floor Operator PIN</summary>
            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <select className={input} value={resetUserId} onChange={(e) => setResetUserId(Number(e.target.value))}>
                <option value="">— choose —</option>
                {roster.map((u) => (
                  <option key={u.id} value={u.id}>{u.username}</option>
                ))}
              </select>
              <input className={input} type="password" placeholder="New PIN" value={resetPin} onChange={(e) => setResetPin(e.target.value)} />
              <button className={`${fl.btn} sm:w-40`} disabled={!resetUserId || !resetPin || resetMutation.isPending}
                     onClick={() => resetMutation.mutate()}>
                💾 Reset PIN
              </button>
            </div>
            {resetMutation.isError && (
              <p className="mt-1 text-xs text-red-400">{(resetMutation.error as Error).message}</p>
            )}
            {resetMutation.isSuccess && <p className="mt-1 text-xs text-emerald-400">PIN updated.</p>}
          </details>
        </div>
      </div>
    </div>
  )
}
