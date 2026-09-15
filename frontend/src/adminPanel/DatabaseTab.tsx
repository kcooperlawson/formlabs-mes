import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { adminApi } from '../api/admin'
import { fl } from '../theme'

const card = fl.card
const select = fl.select

function WipPanel() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin-wip'], queryFn: adminApi.wip })
  const mutation = useMutation({
    mutationFn: adminApi.clearWip,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-wip'] }),
  })
  const wip = query.data?.wip ?? 0

  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">🧹 System Utility: Clear Unpacked Floor WIP</summary>
      <p className="mt-2 text-sm text-[#CBD5E1]">
        Current Today's Floor WIP: <b className="text-white">{wip.toLocaleString()} units</b>
      </p>
      {wip > 0 ? (
        <button className={`${fl.btn} mt-2`} disabled={mutation.isPending} onClick={() => mutation.mutate()}>
          ⚖️ Auto-Pack Remaining WIP to Zero
        </button>
      ) : (
        <p className="mt-2 text-sm text-emerald-400">Floor WIP is already balanced at 0.</p>
      )}
      {mutation.isSuccess && <p className="mt-1 text-xs text-emerald-400">Cleared {mutation.data.cleared} units!</p>}
    </details>
  )
}

function BackupPanel() {
  const queryClient = useQueryClient()
  const statusQuery = useQuery({ queryKey: ['admin-backup-status'], queryFn: adminApi.backupStatus })
  const listQuery = useQuery({ queryKey: ['admin-backup-list'], queryFn: adminApi.backups })
  const [selected, setSelected] = useState('')
  const [confirmText, setConfirmText] = useState('')

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['admin-backup-status'] })
    queryClient.invalidateQueries({ queryKey: ['admin-backup-list'] })
  }
  const createMutation = useMutation({ mutationFn: adminApi.createBackup, onSuccess: invalidate })
  const restoreMutation = useMutation({
    mutationFn: () => adminApi.restoreBackup(selected),
    onSuccess: () => setConfirmText(''),
  })

  const status = statusQuery.data
  const files = listQuery.data ?? []
  const armed = confirmText.trim() === 'RESTORE' && !!selected

  const banner = !status ? null : status.state === 'ok'
    ? <p className="text-sm text-emerald-400">🟢 Automatic backup is running. {status.message}</p>
    : status.state === 'stale'
      ? <p className="text-sm text-amber-400">🟠 {status.message} Take one now, and check there is disk space and that pg_dump is still on this machine.</p>
      : <p className="text-sm text-red-400">🔴 {status.message} Take one now.</p>

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-white">🛡️ Database Disaster Recovery</p>
      {banner}
      {status && (
        <p className={`text-xs ${fl.muted}`}>
          One is taken automatically when the newest is more than {status.due_after_hours} hours old and somebody
          opens the app; the {status.keep_backups} most recent are kept and older ones removed.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">📦 Generate Database Backup</p>
          <button className={fl.btn} disabled={createMutation.isPending} onClick={() => createMutation.mutate()}>
            📦 Generate Database Backup
          </button>
          {createMutation.isSuccess && <p className="mt-1 text-xs text-emerald-400">Backup created: {createMutation.data.filename}</p>}
          {createMutation.isError && <p className="mt-1 text-xs text-red-400">{(createMutation.error as Error).message}</p>}
        </div>

        <div className={card}>
          <p className="mb-2 text-sm font-semibold text-white">🔄 Restore Database</p>
          <p className={`mb-2 text-xs ${fl.muted}`}>
            ⚠️ Overwrites the live database with an old snapshot. Nothing entered since that backup survives.
          </p>
          <select className={`${select} mb-2`} value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">— choose a backup —</option>
            {files.map((f) => <option key={f}>{f}</option>)}
          </select>
          <input
            className={`${fl.input} mb-2`} placeholder='Type RESTORE to confirm' value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
          />
          <button className={fl.btnDanger} disabled={!armed || restoreMutation.isPending} onClick={() => restoreMutation.mutate()}>
            🔄 Restore Database
          </button>
          {restoreMutation.isSuccess && <p className="mt-1 text-xs text-emerald-400">Restored from {selected}!</p>}
          {restoreMutation.isError && <p className="mt-1 text-xs text-red-400">{(restoreMutation.error as Error).message}</p>}
        </div>
      </div>
    </div>
  )
}

export function DatabaseTab() {
  return (
    <div className="flex flex-col gap-3">
      <WipPanel />
      <BackupPanel />
    </div>
  )
}
