import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cleanlinessApi } from '../api/cleanliness'
import { fl } from '../theme'

const tile = fl.tile
const card = fl.card

// Cleanliness & Station Photo Gallery, ported from pages/Mgr_Cleanliness.py
// - the manager review side of every audit_tab.py/checklist.py photo
// submission.
export function CleanlinessGalleryPage() {
  const queryClient = useQueryClient()
  const statsQuery = useQuery({ queryKey: ['cleanliness', 'stats'], queryFn: cleanlinessApi.stats })
  const auditsQuery = useQuery({ queryKey: ['cleanliness', 'audits'], queryFn: cleanlinessApi.audits })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => cleanlinessApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cleanliness', 'audits'] })
      queryClient.invalidateQueries({ queryKey: ['cleanliness', 'stats'] })
    },
  })

  const stats = statsQuery.data
  const audits = auditsQuery.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <h1 className={fl.heading}>📸 Cleanliness &amp; Station Photo Gallery</h1>

      {stats && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{stats.total_audits}</p>
            <p className={`text-xs ${fl.muted}`}>All Photo Audits</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{stats.start_checks}</p>
            <p className={`text-xs ${fl.muted}`}>Start Shift Checks</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{stats.end_checks}</p>
            <p className={`text-xs ${fl.muted}`}>End Shift Checks</p>
          </div>
          <div className={tile}>
            <p className="text-lg font-semibold text-white">{stats.transfers}</p>
            <p className={`text-xs ${fl.muted}`}>Pump Transfers</p>
          </div>
          <div className={tile} style={stats.spills > 0 ? { borderColor: '#EF4444' } : undefined}>
            <p className={`text-lg font-semibold ${stats.spills > 0 ? 'text-red-400' : 'text-white'}`}>{stats.spills}</p>
            <p className={`text-xs ${fl.muted}`}>Spills / Issues</p>
          </div>
        </div>
      )}

      {audits.length === 0 ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
          📸 No photo audits yet. Operators submit these from the workstation, under Station Cleanliness.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {audits.map((a) => (
            <div key={a.id} className={card}>
              <div className="mb-2 flex items-center justify-between">
                <span className={`text-sm font-bold ${a.is_spill ? 'text-red-400' : 'text-sky-400'}`}>
                  ● {a.audit_type}
                </span>
                <span className={`text-xs ${fl.muted}`}>{a.pump_station}</span>
              </div>
              {a.photos.length === 0 ? (
                <p className={`text-sm ${fl.muted}`}>📝 Log entry without image attachment.</p>
              ) : (
                <div className="mb-2 flex flex-wrap gap-1">
                  {a.photos.map((p, i) => (
                    <img
                      key={p}
                      src={cleanlinessApi.photoUrl(p)}
                      alt={a.audit_type}
                      className={i === 0 ? 'w-full rounded-md object-cover' : 'h-20 w-20 rounded-md object-cover'}
                    />
                  ))}
                </div>
              )}
              <p className={`text-xs ${fl.muted}`}>
                📅 {new Date(a.timestamp).toLocaleString()} · 👤 {a.operator_name}
              </p>
              <p className="mt-1 text-sm italic text-[#CBD5E1]">
                {a.notes || 'No additional operator notes logged.'}
              </p>
              <button
                onClick={() => deleteMutation.mutate(a.id)}
                disabled={deleteMutation.isPending}
                className={`${fl.btnSecondary} mt-2 w-full`}
              >
                🗑️ Delete Photo Audit #{a.id}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
