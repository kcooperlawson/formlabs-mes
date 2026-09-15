import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { devicesApi, type DeviceMeta, type DeviceRow } from '../api/devices'
import { fl } from '../theme'

const card = fl.card
const input = fl.input
const select = fl.select

const STATUS_COLORS: Record<string, string> = { Online: '#10B981', Offline: '#F59E0B', Error: '#EF4444', Unknown: '#64748B' }

function timeAgo(iso: string | null): string {
  if (!iso) return 'never'
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000
  if (seconds < 0) return 'just now'
  if (seconds < 60) return `${Math.floor(seconds)}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function TagMapPanel({ device, meta }: { device: DeviceRow; meta: DeviceMeta }) {
  const queryClient = useQueryClient()
  const tagsQuery = useQuery({ queryKey: ['device-tags', device.id], queryFn: () => devicesApi.tags(device.id) })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['device-tags', device.id] })
  const deleteMutation = useMutation({ mutationFn: (tagId: number) => devicesApi.deleteTag(tagId), onSuccess: invalidate })

  const [rawTag, setRawTag] = useState('')
  const [canonical, setCanonical] = useState(meta.canonical_metrics[0] ?? '')
  const [dataType, setDataType] = useState('float')
  const [scale, setScale] = useState(1.0)
  const [unit, setUnit] = useState('')
  const saveMutation = useMutation({
    mutationFn: () => devicesApi.saveTag(device.id, { raw_tag: rawTag.trim(), canonical_metric: canonical, data_type: dataType, scale_factor: scale, unit }),
    onSuccess: () => { setRawTag(''); setUnit(''); invalidate() },
  })

  const tags = tagsQuery.data ?? []

  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-xs font-semibold text-[#94A3B8]">🏷️ Tag Map — {device.device_name}</summary>
      <div className="mt-2 flex flex-col gap-2">
        {tags.length === 0 ? (
          <p className={`text-xs ${fl.muted}`}>No tags mapped yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className={fl.tableHead}>
                <tr><th className="py-1 pr-2">Raw tag</th><th className="py-1 pr-2">Canonical metric</th><th className="py-1 pr-2">Type</th><th className="py-1 pr-2">Scale</th><th className="py-1 pr-2">Unit</th><th></th></tr>
              </thead>
              <tbody>
                {tags.map((t) => (
                  <tr key={t.id} className={fl.tableRow}>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{t.raw_tag}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{t.canonical_metric}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{t.data_type}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{t.scale_factor}</td>
                    <td className="py-1 pr-2 text-[#CBD5E1]">{t.unit}</td>
                    <td className="py-1 pr-2">
                      <button className={fl.btnSecondary} disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(t.id)}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="mt-1 text-xs font-semibold text-white">Add / update a tag</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          <input className={input} placeholder="Raw tag" value={rawTag} onChange={(e) => setRawTag(e.target.value)}
                title="Register address / node id / MQTT topic / regex / JSON path — depends on the device's protocol." />
          <select className={select} value={canonical} onChange={(e) => setCanonical(e.target.value)}>
            {meta.canonical_metrics.map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className={select} value={dataType} onChange={(e) => setDataType(e.target.value)}>
            {['float', 'int', 'string', 'bool'].map((t) => <option key={t}>{t}</option>)}
          </select>
          <input className={input} type="number" step={0.1} placeholder="Scale ×" value={scale} onChange={(e) => setScale(Number(e.target.value))} />
          <input className={input} placeholder="Unit (g)" value={unit} onChange={(e) => setUnit(e.target.value)} />
        </div>
        <button className={`${fl.btn} self-start`} disabled={!rawTag.trim() || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          💾 Save Tag
        </button>
      </div>
    </details>
  )
}

export function DevicesTab({ meta }: { meta: DeviceMeta }) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['devices'], queryFn: devicesApi.list })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['devices'] })
  const toggleMutation = useMutation({ mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => devicesApi.setEnabled(id, enabled), onSuccess: invalidate })
  const deleteMutation = useMutation({ mutationFn: (id: number) => devicesApi.remove(id), onSuccess: invalidate })

  const devices = query.data ?? []
  if (devices.length === 0) {
    return <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>No devices registered yet — add one in the Add / Test Device tab.</p>
  }

  return (
    <div className="flex flex-col gap-2">
      {devices.map((d) => (
        <div key={d.id} className={card}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <b className="text-base text-white">{d.device_name}</b>{' '}
              <span className="text-sm font-bold" style={{ color: STATUS_COLORS[d.status] ?? STATUS_COLORS.Unknown }}>● {d.status}</span>
              <p className={`text-sm ${fl.muted}`}>
                {meta.protocol_labels[d.protocol] ?? d.protocol} · role: {d.device_role} · pump: {d.assigned_pump} · reactor: {d.assigned_reactor} · last seen {timeAgo(d.last_seen_at)}
              </p>
              {d.last_error && <p className="text-xs text-red-400">{d.last_error}</p>}
            </div>
            <div className="flex shrink-0 gap-2">
              <button className={fl.btnSecondary} disabled={toggleMutation.isPending} onClick={() => toggleMutation.mutate({ id: d.id, enabled: !d.is_enabled })}>
                {d.is_enabled ? '⏸️ Disable' : '▶️ Enable'}
              </button>
              <button className={fl.btnDanger} disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(d.id)}>🗑️ Delete</button>
            </div>
          </div>
          <TagMapPanel device={d} meta={meta} />
        </div>
      ))}
    </div>
  )
}
