import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { EXPORT_MODES, googleSyncApi, HORIZONS, type SheetTarget } from '../api/googleSync'
import { fl } from '../theme'

const input = fl.input
const btn = fl.btn
const card = fl.card

function downloadCsv(columns: string[], rows: Record<string, unknown>[], filename: string) {
  const csv = [columns, ...rows.map((r) => columns.map((c) => r[c]))]
    .map((r) => r.map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function AddTargetForm({ expanded }: { expanded: boolean }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [isShared, setIsShared] = useState(false)

  const classifyQuery = useQuery({
    queryKey: ['google-sync', 'classify', url],
    queryFn: () => googleSyncApi.classifyUrl(url),
    enabled: url.length > 0,
  })
  const verdict = classifyQuery.data

  const addMutation = useMutation({
    mutationFn: () => googleSyncApi.addTarget({ name, url, is_shared: isShared }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['google-sync', 'targets'] })
      setName(''); setUrl(''); setIsShared(false)
    },
  })

  return (
    <details className={card} open={expanded}>
      <summary className="cursor-pointer text-sm font-medium text-white">➕ Link a spreadsheet of your own</summary>
      <div className="mt-3 flex flex-col gap-2 text-sm text-[#CBD5E1]">
        <p>
          A Google Sheet is a document — it has no inbox, so it cannot be sent rows directly. Giving your
          sheet an address takes four steps:
        </p>
        <ol className="list-inside list-decimal">
          <li>Open your Google Sheet and choose <b>Extensions → Apps Script</b>.</li>
          <li>Delete whatever is in the editor, paste the script (ask your admin for it), and save.</li>
          <li>Choose <b>Deploy → New deployment → Web app</b>. Set <i>Execute as</i> to <b>Me</b> and <i>Who has access</i> to <b>Anyone</b>, then Deploy and approve the permissions.</li>
          <li>Copy the <b>Web app URL</b> it shows you — it ends in <code>/exec</code> — and paste it below.</li>
        </ol>

        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_2fr]">
          <input className={input} placeholder="Name it (e.g. My weekly report)" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
          <input className={input} placeholder="Web app address (ends in /exec)" value={url} onChange={(e) => setUrl(e.target.value)} />
        </div>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={isShared} onChange={(e) => setIsShared(e.target.checked)} />
          Let other managers send to this sheet too
        </label>

        {verdict && verdict.message && (
          <p className={verdict.ok ? 'text-sm text-emerald-400' : 'text-sm text-red-400'}>{verdict.message}</p>
        )}
        {addMutation.isError && <p className="text-sm text-red-400">{(addMutation.error as Error).message}</p>}

        <button
          className={`${btn} w-full`}
          disabled={!verdict?.ok || !name.trim() || addMutation.isPending}
          onClick={() => addMutation.mutate()}
        >
          💾 Link this sheet
        </button>
      </div>
    </details>
  )
}

function EditTargetsPanel({ targets }: { targets: SheetTarget[] }) {
  const queryClient = useQueryClient()
  const editable = targets.filter((t) => t.editable)

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: { name?: string; webhook_url?: string; is_shared?: boolean } }) =>
      googleSyncApi.updateTarget(id, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['google-sync', 'targets'] }),
  })
  const deleteMutation = useMutation({
    mutationFn: (id: number) => googleSyncApi.deleteTarget(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['google-sync', 'targets'] }),
  })

  if (targets.length === 0) return null

  return (
    <details className={card}>
      <summary className="cursor-pointer text-sm font-medium text-white">✏️ Sheets you have linked</summary>
      <div className="mt-3 flex flex-col gap-3">
        {editable.length === 0 && (
          <p className={`text-sm ${fl.muted}`}>The sheets in your list were shared by somebody else, so only they can change them.</p>
        )}
        {editable.map((t) => (
          <EditRow key={t.id} target={t} onSave={(body) => updateMutation.mutate({ id: t.id, body })} onDelete={() => deleteMutation.mutate(t.id)} />
        ))}
      </div>
    </details>
  )
}

function EditRow({ target, onSave, onDelete }: {
  target: SheetTarget
  onSave: (body: { name?: string; webhook_url?: string; is_shared?: boolean }) => void
  onDelete: () => void
}) {
  const [name, setName] = useState(target.name)
  const [url, setUrl] = useState(target.webhook_url)
  const [shared, setShared] = useState(target.is_shared)

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <input className={`${input} flex-1`} value={name} onChange={(e) => setName(e.target.value)} />
        <input className={`${input} flex-[2]`} value={url} onChange={(e) => setUrl(e.target.value)} />
        <label className="flex items-center gap-1 text-xs text-[#CBD5E1]">
          <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
          Shared
        </label>
        <button className={fl.btnSecondary} onClick={() => onSave({ name, webhook_url: url, is_shared: shared })}>
          💾 Save
        </button>
      </div>
      <button className={`${fl.btnSecondary} mt-1`} onClick={onDelete}>
        🗑️ Remove "{target.name}"
      </button>
      <hr className={`my-2 ${fl.divider}`} />
    </div>
  )
}

// External Reporting & Google Cloud Sync, ported from
// pages/Mgr_Google_Sync.py - link a destination sheet, preview/export the
// payload as a file, or push it straight to a linked sheet.
export function GoogleSyncPage() {
  const targetsQuery = useQuery({ queryKey: ['google-sync', 'targets'], queryFn: googleSyncApi.targets })
  const targets = targetsQuery.data ?? []

  const [selectedId, setSelectedId] = useState<number | null>(null)
  useEffect(() => {
    if (targets.length > 0 && (selectedId === null || !targets.some((t) => t.id === selectedId))) {
      setSelectedId(targets[0].id)
    }
    if (targets.length === 0 && selectedId !== null) setSelectedId(null)
  }, [targets, selectedId])
  const target = targets.find((t) => t.id === selectedId) ?? null

  const testMutation = useMutation({ mutationFn: (id: number) => googleSyncApi.testTarget(id) })

  const [exportMode, setExportMode] = useState<string>(EXPORT_MODES[0])
  const [horizon, setHorizon] = useState<string>(HORIZONS[3])
  const previewQuery = useQuery({
    queryKey: ['google-sync', 'export-preview', exportMode, horizon],
    queryFn: () => googleSyncApi.exportPreview(exportMode, horizon),
  })
  const preview = previewQuery.data
  const [selectedCols, setSelectedCols] = useState<string[]>([])
  useEffect(() => {
    if (preview) setSelectedCols(preview.columns)
  }, [preview?.columns.join('|')])

  const pushMutation = useMutation({
    mutationFn: () =>
      googleSyncApi.push({ target_id: selectedId as number, export_mode: exportMode, horizon, columns: selectedCols }),
  })

  const excelAvailable = true // the backend 409s with a clear message if openpyxl is missing

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={fl.heading}>☁️ External Reporting &amp; Google Cloud Sync Control Panel</h1>
        <p className={`text-sm ${fl.muted}`}>
          Send the record to a spreadsheet of your own. Choose what to send and how far back, pick the
          columns, and push. Every push is manual and on demand.
        </p>
      </div>

      <p className="text-sm font-semibold text-white">📗 Destination</p>

      {targets.length === 0 ? (
        <p className={`text-sm ${fl.muted}`}>
          No spreadsheet is linked yet. Add one below — it takes about two minutes and you only do it once
          per sheet.
        </p>
      ) : (
        <div className={card}>
          <select className={input} value={selectedId ?? ''} onChange={(e) => setSelectedId(Number(e.target.value))}>
            {targets.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          {target && (
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className={`text-xs ${fl.muted}`}>{target.last_sync_text}</p>
              <button className={fl.btnSecondary} disabled={testMutation.isPending} onClick={() => testMutation.mutate(target.id)}>
                🔌 Test
              </button>
            </div>
          )}
          {testMutation.data && (
            <p className={`mt-1 text-xs ${testMutation.data.ok ? 'text-emerald-400' : 'text-red-400'}`}>
              {testMutation.data.message}
            </p>
          )}
        </div>
      )}

      <AddTargetForm expanded={targets.length === 0} />
      <EditTargetsPanel targets={targets} />

      <hr className={fl.divider} />
      <p className="text-sm font-semibold text-white">⚙️ Payload Column Customization</p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className={`mb-1 block ${fl.label}`}>1. Select Data Payload Type</label>
          <div className="flex flex-col gap-1 text-sm text-[#CBD5E1]">
            {EXPORT_MODES.map((m) => (
              <label key={m} className="flex items-center gap-2">
                <input type="radio" checked={exportMode === m} onChange={() => setExportMode(m)} />
                {m}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className={`mb-1 block ${fl.label}`}>2. Time Horizon Scope</label>
          <select className={input} value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            {HORIZONS.map((h) => <option key={h} value={h}>{h}</option>)}
          </select>
        </div>
      </div>

      {preview && (
        <div className={card}>
          <p className={`mb-2 text-xs ${fl.muted}`}>Toggle Metrics / Statistics to Include in Payload:</p>
          <div className="flex flex-wrap gap-2">
            {preview.columns.map((c) => (
              <label key={c} className="flex items-center gap-1 rounded border border-[#475569] px-2 py-1 text-xs text-[#CBD5E1]">
                <input
                  type="checkbox"
                  checked={selectedCols.includes(c)}
                  onChange={(e) =>
                    setSelectedCols((prev) => (e.target.checked ? [...prev, c] : prev.filter((x) => x !== c)))
                  }
                />
                {c}
              </label>
            ))}
          </div>
        </div>
      )}

      {target && preview && (
        <p className={`text-sm ${fl.muted}`}>
          Ready to send <b className="text-white">{preview.row_count.toLocaleString()} rows</b> to{' '}
          <b className="text-white">{target.name}</b> — {horizon}.
        </p>
      )}

      <hr className={fl.divider} />
      <p className="text-sm font-semibold text-white">⬇️ Take it as a file</p>
      <p className={`text-sm ${fl.muted}`}>
        No Google account, no setup, nothing to publish — and the file opens straight in Google Sheets
        (File → Import) or Excel.
      </p>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {excelAvailable && (
          <a
            className={`${btn} block text-center no-underline`}
            href={preview && preview.row_count > 0 ? googleSyncApi.exportXlsxUrl(exportMode, horizon, selectedCols) : undefined}
            aria-disabled={!preview || preview.row_count === 0}
            onClick={(e) => { if (!preview || preview.row_count === 0) e.preventDefault() }}
          >
            📗 Download Excel (.xlsx)
          </a>
        )}
        <button
          className={btn}
          disabled={!preview || preview.row_count === 0 || selectedCols.length === 0}
          onClick={() => preview && downloadCsv(selectedCols, preview.rows, `formlabs-mes-export-${new Date().toISOString().slice(0, 10)}.csv`)}
        >
          📄 Download CSV
        </button>
      </div>

      <hr className={fl.divider} />
      <p className="text-sm font-semibold text-white">🚀 Or push it straight into a linked sheet</p>

      {!target ? (
        <p className={`text-sm ${fl.muted}`}>Nothing linked yet — link a sheet above, or just take the file.</p>
      ) : (
        <>
          <button className={`${btn} w-full`} disabled={pushMutation.isPending} onClick={() => pushMutation.mutate()}>
            🚀 Execute Google Sheets Transmission
          </button>
          {pushMutation.data && (
            <div className={pushMutation.data.ok ? 'text-sm text-emerald-400' : 'text-sm text-red-400'}>
              {pushMutation.data.ok ? (
                <>
                  ✅ {pushMutation.data.rows?.toLocaleString()} rows written to tab '{pushMutation.data.tab}' in "{pushMutation.data.sheet}".
                  {pushMutation.data.url && (
                    <>
                      {' '}
                      <a href={pushMutation.data.url} target="_blank" rel="noreferrer" className="underline">
                        Open "{pushMutation.data.sheet}" →
                      </a>
                    </>
                  )}
                </>
              ) : (
                <>❌ {pushMutation.data.message}</>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
