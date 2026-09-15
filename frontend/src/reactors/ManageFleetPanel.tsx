import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { reactorsApi, type ManageOptions, type ManageReactorRow } from '../api/reactors'
import { fl } from '../theme'

const input = fl.input
const btn = fl.btnSecondary

// The "Manage Permanent Reactor Fleet" expander, ported from
// Live_Reactors.py - gated behind manage_reactors. Not shown at all (not
// even a locked placeholder) when the query 403s, matching the original's
// own `if can("manage_reactors"): with st.expander(...)`.
export function ManageFleetPanel() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const optionsQuery = useQuery({ queryKey: ['reactors', 'manage-options'], queryFn: reactorsApi.manageOptions, retry: false })
  const listQuery = useQuery({
    queryKey: ['reactors', 'manage-list'], queryFn: reactorsApi.manageList, retry: false, enabled: open,
  })

  const [newName, setNewName] = useState('')
  const [newCap, setNewCap] = useState(5000)
  const [newKind, setNewKind] = useState('bulk_vertical')
  const [newTag, setNewTag] = useState('')
  const [newBay, setNewBay] = useState('')

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['reactors', 'manage-list'] })
    queryClient.invalidateQueries({ queryKey: ['reactors', 'fleet'] })
  }

  const addMutation = useMutation({
    mutationFn: () => reactorsApi.add({ reactor_name: newName, max_capacity_l: newCap, vessel_type: newKind, asset_tag: newTag, bay_marker: newBay }),
    onSuccess: () => {
      setNewName(''); setNewTag(''); setNewBay('')
      invalidate()
    },
  })
  const deleteMutation = useMutation({ mutationFn: (id: number) => reactorsApi.remove(id), onSuccess: invalidate })
  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Parameters<typeof reactorsApi.update>[1] }) => reactorsApi.update(id, body),
    onSuccess: invalidate,
  })

  if (optionsQuery.isError) return null
  const options = optionsQuery.data

  return (
    <details className={fl.card} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer text-sm font-medium text-white">⚙️ Manage Permanent Reactor Fleet</summary>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-[280px_1fr]">
        <div className="flex flex-col gap-2">
          <p className="text-xs font-semibold text-white">➕ Add New Permanent Reactor</p>
          <input className={input} placeholder="Reactor Name (e.g. Tank C-5000)" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <input className={input} type="number" value={newCap} onChange={(e) => setNewCap(Number(e.target.value))} placeholder="Max Capacity (L)" />
          <select className={input} value={newKind} onChange={(e) => setNewKind(e.target.value)}>
            {(options?.vessel_types ?? []).map((v) => (
              <option key={v.value} value={v.value}>{v.label}</option>
            ))}
          </select>
          <p className={`text-xs ${fl.muted}`}>{options?.vessel_types.find((v) => v.value === newKind)?.help}</p>
          <div className="flex gap-2">
            <input className={input} placeholder="Asset Tag" value={newTag} onChange={(e) => setNewTag(e.target.value)} />
            <input className={input} placeholder="Bay" maxLength={3} value={newBay} onChange={(e) => setNewBay(e.target.value)} />
          </div>
          <button className={btn} disabled={!newName.trim() || addMutation.isPending} onClick={() => addMutation.mutate()}>
            Add Permanent Reactor
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <p className="text-xs font-semibold text-white">🏭 Permanent Fleet Registration</p>
          {(listQuery.data ?? []).map((r) => (
            <FleetRow key={r.id} row={r} options={options} onSave={(body) => updateMutation.mutate({ id: r.id, body })}
                     onDelete={() => deleteMutation.mutate(r.id)} />
          ))}
          {open && listQuery.data?.length === 0 && <p className={`text-sm ${fl.muted}`}>No permanent reactors added yet.</p>}
        </div>
      </div>
    </details>
  )
}

function FleetRow({
  row, options, onSave, onDelete,
}: {
  row: ManageReactorRow
  options: ManageOptions | undefined
  onSave: (body: { vessel_type: string; asset_tag: string; bay_marker: string; assigned_pump: string; current_resin: string }) => void
  onDelete: () => void
}) {
  const [kind, setKind] = useState(row.vessel_type)
  const [tag, setTag] = useState(row.asset_tag)
  const [bay, setBay] = useState(row.bay_marker)
  const [pump, setPump] = useState(row.assigned_pump)
  const [resin, setResin] = useState(row.current_resin)

  return (
    <div className={fl.card}>
      <div className="mb-1 flex items-center justify-between">
        <p className="text-sm font-semibold text-white">🛢️ {row.reactor_name} <span className={`font-normal ${fl.muted}`}>({row.capacity_l.toLocaleString()} L)</span></p>
        <button className={btn} onClick={onDelete}>🗑️ Remove</button>
      </div>
      <div className="flex flex-wrap gap-2">
        <select className={input} value={kind} onChange={(e) => setKind(e.target.value)}>
          {(options?.vessel_types ?? []).map((v) => (
            <option key={v.value} value={v.value}>{v.label}</option>
          ))}
        </select>
        <input className={input} placeholder="Asset tag" value={tag} onChange={(e) => setTag(e.target.value)} />
        <input className={input} placeholder="Bay" maxLength={3} value={bay} onChange={(e) => setBay(e.target.value)} />
        <select className={input} value={pump} onChange={(e) => setPump(e.target.value)}>
          <option value="">— not set —</option>
          {(options?.pumps ?? []).map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <select className={input} value={resin} onChange={(e) => setResin(e.target.value)}>
          <option value="">— not set —</option>
          {(options?.resins ?? []).map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button className={btn} onClick={() => onSave({ vessel_type: kind, asset_tag: tag, bay_marker: bay, assigned_pump: pump, current_resin: resin })}>
          💾 Save
        </button>
      </div>
      {(!pump || !resin) && (
        <p className="mt-1 text-xs text-amber-400">
          ⚠️ Not linked yet, so this tank's level will not move.
        </p>
      )}
    </div>
  )
}
