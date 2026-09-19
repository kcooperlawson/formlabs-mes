import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { updatesApi, type AvailableUpdate } from '../api/updates'
import { fl } from '../theme'

const card = fl.card

function ago(iso: string): string {
  if (!iso) return ''
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000
  if (!Number.isFinite(seconds) || seconds < 0) return ''
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

// Where this PC gets updates from, and every version that source is offering.
//
// The address is this PC's own setting (it lands in .env, which no update
// overwrites), so each plant PC can point somewhere different - the one on
// the floor at a PC serving updates on the plant network, a PC at home at
// its own. Blank means GitHub.
export function UpdatesTab() {
  const queryClient = useQueryClient()
  const [notes, setNotes] = useState('')
  const [address, setAddress] = useState('')
  const [token, setToken] = useState('')
  const [touched, setTouched] = useState(false)

  const statusQuery = useQuery({ queryKey: ['updates-status'], queryFn: updatesApi.status })
  const sourceQuery = useQuery({ queryKey: ['updates-source'], queryFn: updatesApi.source })
  const availableQuery = useQuery({
    queryKey: ['updates-available'],
    queryFn: updatesApi.available,
    retry: false,
  })

  useEffect(() => {
    if (sourceQuery.data && !touched) setAddress(sourceQuery.data.address)
  }, [sourceQuery.data, touched])

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ['updates-source'] })
    queryClient.invalidateQueries({ queryKey: ['updates-available'] })
    queryClient.invalidateQueries({ queryKey: ['updates-status'] })
  }

  const checkNow = useMutation({
    mutationFn: updatesApi.checkNow,
    onSuccess: (data) => {
      queryClient.setQueryData(['updates-status'], data)
      queryClient.invalidateQueries({ queryKey: ['updates-available'] })
    },
  })
  const saveSource = useMutation({
    mutationFn: () => updatesApi.setSource(address, token || null),
    onSuccess: () => { setTouched(false); setToken(''); refreshAll() },
  })
  const publishMutation = useMutation({
    // A full package applies to any older version, so there is no
    // from_version to supply any more (see dev/make_update.py).
    mutationFn: () => updatesApi.publish('', notes),
  })
  const applyMutation = useMutation({
    mutationFn: ({ version, allowOlder }: { version: string; allowOlder: boolean }) =>
      updatesApi.applyVersion(version, allowOlder),
    onSuccess: refreshAll,
  })

  const status = statusQuery.data
  const source = sourceQuery.data
  const versions = availableQuery.data ?? []

  const install = (entry: AvailableUpdate) => {
    const goingBack = !entry.newer && !entry.current
    const warning = goingBack
      ? `Go BACK to ${entry.version}? The files go back; the database does not — anything a newer version changed in the schema stays changed. A backup is taken first.`
      : `Apply ${entry.version}? The database is backed up first, and the app restarts itself when it finishes. Anyone using it — including operators mid-pour — will be disconnected while it restarts.`
    if (window.confirm(warning)) {
      applyMutation.mutate({ version: entry.version, allowOlder: goingBack })
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* --- where updates come from --- */}
      <div className={card}>
        <p className="mb-2 text-sm font-semibold text-white">📡 Update source</p>
        <p className={`mb-2 text-xs ${fl.muted}`}>
          The address of a PC serving updates — type its IP or name (for example <code>192.168.0.15</code>), or a
          full address if it isn't on the default port. Leave it blank to use GitHub instead. This is this PC's own
          setting and survives every update.
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex-1 text-xs text-[#94A3B8]">
            Update server address
            <input
              className={`${fl.input} mt-1 w-full`}
              value={address}
              placeholder="192.168.0.15   (blank = GitHub)"
              onChange={(e) => { setAddress(e.target.value); setTouched(true) }}
            />
          </label>
          <label className="text-xs text-[#94A3B8] sm:w-56">
            Password, if it needs one
            <input
              className={`${fl.input} mt-1 w-full`}
              type="password"
              value={token}
              placeholder={source?.token_set ? '•••••• (set)' : 'none'}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          <button className={fl.btn} disabled={saveSource.isPending} onClick={() => saveSource.mutate()}>
            {saveSource.isPending ? 'Saving…' : '💾 Save'}
          </button>
        </div>
        {saveSource.isError && <p className="mt-2 text-xs text-red-400">{(saveSource.error as Error).message}</p>}
        {source && (
          <p className={`mt-2 text-xs ${fl.muted}`}>
            Currently using {source.kind === 'server'
              ? <>the update server at <b className="text-white">{source.address}</b></>
              : <>GitHub (<b className="text-white">{source.repo}</b>)</>}
            {source.token_set ? ' · password set' : ''}
          </p>
        )}
      </div>

      {/* --- what's on offer --- */}
      <div className={card}>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-sm font-semibold text-white">🔎 Versions available</p>
          <button className={fl.btnSecondary} disabled={checkNow.isPending} onClick={() => checkNow.mutate()}>
            {checkNow.isPending ? 'Checking…' : '🔄 Check now'}
          </button>
        </div>
        <p className="text-sm text-[#CBD5E1]">
          This machine is running <b className="text-white">{status?.current_version ?? '…'}</b>.
        </p>
        {availableQuery.isError && (
          <p className="mt-2 text-sm text-amber-400">
            Could not read the update source: {(availableQuery.error as Error).message}
          </p>
        )}
        {availableQuery.isLoading && <p className={`mt-2 text-sm ${fl.muted}`}>Looking…</p>}
        {availableQuery.isSuccess && versions.length === 0 && (
          <p className={`mt-2 text-sm ${fl.muted}`}>Nothing published there yet.</p>
        )}
        {versions.length > 0 && (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className={fl.tableHead}>
                <tr>
                  <th className="py-1 pr-2">Version</th>
                  <th className="py-1 pr-2">Published</th>
                  <th className="py-1 pr-2">What's in it</th>
                  <th className="py-1 pr-2"></th>
                </tr>
              </thead>
              <tbody>
                {versions.map((entry) => (
                  <tr key={entry.version} className={fl.tableRow}>
                    <td className="py-1 pr-2 whitespace-nowrap text-white">
                      {entry.version}
                      {entry.current && <span className="ml-2 text-xs text-emerald-400">● running now</span>}
                    </td>
                    <td className={`py-1 pr-2 whitespace-nowrap text-xs ${fl.muted}`}>{ago(entry.published_at)}</td>
                    <td className={`py-1 pr-2 text-xs ${fl.muted}`}>{(entry.notes || '').split('\n')[0]}</td>
                    <td className="py-1 pr-2 whitespace-nowrap">
                      {entry.current ? (
                        <span className={`text-xs ${fl.muted}`}>—</span>
                      ) : (
                        <button
                          className={entry.newer ? fl.btn : fl.btnSecondary}
                          disabled={applyMutation.isPending}
                          onClick={() => install(entry)}
                        >
                          {applyMutation.isPending ? '⏳ …' : entry.newer ? `⬆️ Install` : `⬇️ Go back to this`}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {applyMutation.isSuccess && (
          <p className={`mt-2 text-xs ${applyMutation.data.ok ? 'text-emerald-400' : 'text-red-400'}`}>
            {applyMutation.data.ok
              ? `Applied - now on ${applyMutation.data.version}.${applyMutation.data.restarting ? ' Restarting now; reload in ~20 seconds.' : ' Close the app window and start it again to run the new version.'}`
              : 'Failed - the previous version was restored automatically.'}
          </p>
        )}
        {applyMutation.isSuccess && !applyMutation.data.ok && (
          <pre className="mt-1 max-h-40 overflow-auto rounded bg-black/40 p-2 text-[10px] text-[#94A3B8]">{applyMutation.data.log}</pre>
        )}
        {applyMutation.isError && <p className="mt-2 text-xs text-red-400">{(applyMutation.error as Error).message}</p>}
      </div>

      {/* --- publishing, only where the signing key lives --- */}
      {status?.publish_enabled && (
        <details className={card}>
          <summary className="cursor-pointer text-sm font-medium text-white">📤 Publish an update (this machine only)</summary>
          <p className={`mt-2 text-xs ${fl.muted}`}>
            Packages this whole copy of the app — every file a plant PC runs — and uploads it as a GitHub Release.
            It applies to any older version, so there's nothing to tell it about the PCs receiving it. Needs the
            signing key and a GITHUB_RELEASE_TOKEN in .env.
          </p>
          <div className="mt-2 flex flex-col gap-2 sm:max-w-md">
            <label className="text-xs text-[#94A3B8]">
              Notes (shown to whoever applies it)
              <textarea
                className={`${fl.select} mt-1 w-full`}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={2}
              />
            </label>
            <button className={fl.btn} disabled={publishMutation.isPending} onClick={() => publishMutation.mutate()}>
              {publishMutation.isPending ? '⏳ Publishing…' : '📤 Publish'}
            </button>
          </div>
          {publishMutation.isSuccess && (
            <p className="mt-2 text-xs text-emerald-400">
              Published {publishMutation.data.tag_name} ({(publishMutation.data.asset_size / 1024).toFixed(0)} KB) -{' '}
              <a href={publishMutation.data.html_url} target="_blank" rel="noopener noreferrer" className="underline">
                view on GitHub
              </a>
            </p>
          )}
          {publishMutation.isError && <p className="mt-2 text-xs text-red-400">{(publishMutation.error as Error).message}</p>}
        </details>
      )}
    </div>
  )
}
