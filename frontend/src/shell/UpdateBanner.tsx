import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { updatesApi } from '../api/updates'
import { fl } from '../theme'

// Sits at the top of ManagerShell, above whatever tab is open - the "give
// a notification on startup or in the web page saying update available"
// half of the auto-update feature. Polls the same /api/updates/status a
// USB stick never needed, since the whole point is finding out about a
// release without anyone having to go looking for one.
//
// Renders nothing at all until there's actually something to say: no
// update, or the status check itself failed (no internet, say - a very
// normal state for a plant PC), both draw nothing rather than a permanent
// fixture nobody needs. A manager/admin who wants to check anyway still
// has IT Admin Console -> System & Database Utilities -> Updates.
export function UpdateBanner() {
  const queryClient = useQueryClient()
  const [applying, setApplying] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const statusQuery = useQuery({
    queryKey: ['updates-status'],
    queryFn: updatesApi.status,
    refetchInterval: 5 * 60_000, // every 5 min - this is a notice, not a live gauge
    retry: false,
  })

  const applyMutation = useMutation({
    mutationFn: updatesApi.apply,
    onMutate: () => setApplying(true),
    onSuccess: (data) => {
      if (data.ok && data.restarting) {
        // The server is about to stop and be started again by whatever
        // launched it (setup/self_restart.py) - there is nothing more this
        // page can usefully do except say so and wait for a reload, rather
        // than firing requests at a process that's mid-restart.
        setResult({ ok: true, message: `Updated to ${data.version}. The app is restarting - reload this page in about 20 seconds.` })
      } else if (data.ok) {
        setResult({
          ok: true,
          message: `Updated to ${data.version}. Close the app window and start it again (START_HERE.bat) to run the new version.`,
        })
        queryClient.invalidateQueries({ queryKey: ['updates-status'] })
      } else {
        setResult({ ok: false, message: `Update failed - the previous version was restored automatically. ${data.log.split('\n').slice(-3).join(' ')}` })
      }
    },
    onError: (err) => setResult({ ok: false, message: (err as Error).message }),
    onSettled: () => setApplying(false),
  })

  const status = statusQuery.data
  if (!status || !status.update_available || result?.ok) {
    if (result?.ok) {
      return (
        <div className={`${fl.card} mb-3 border-emerald-600 bg-emerald-950/40`}>
          <p className="text-sm text-emerald-300">✅ {result.message}</p>
        </div>
      )
    }
    return null
  }

  return (
    <div className={`${fl.card} mb-3 border-amber-600 bg-amber-950/30`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-amber-200">
          🆕 An update is available: <b>{status.current_version}</b> → <b>{status.latest_version}</b>
          {status.notes && <span className="text-amber-300/80"> — {status.notes.split('\n')[0]}</span>}
        </p>
        <button
          className={fl.btn}
          disabled={applying}
          onClick={() => {
            if (window.confirm(
              `Apply update ${status.latest_version}? The database is backed up first, and the app restarts itself when it finishes. This takes a minute or two, and anyone using the app - including operators mid-pour - will be disconnected while it restarts.`
            )) {
              setResult(null)
              applyMutation.mutate()
            }
          }}
        >
          {applying ? '⏳ Applying…' : '⬆️ Apply now'}
        </button>
      </div>
      {result && !result.ok && <p className="mt-1 text-xs text-red-400">{result.message}</p>}
    </div>
  )
}
