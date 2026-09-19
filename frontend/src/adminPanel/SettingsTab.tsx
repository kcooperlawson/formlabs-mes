import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { adminApi, type UpdatePlantSettingsRequest } from '../api/admin'
import { fl } from '../theme'

const input = fl.input

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function daysStringToSet(s: string): Set<number> {
  const out = new Set<number>()
  for (let i = 0; i < 7; i++) if (s[i] === '1') out.add(i)
  return out
}

function PlantConfigForm() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin-settings'], queryFn: adminApi.settings })
  const s = query.data

  const [form, setForm] = useState<UpdatePlantSettingsRequest | null>(null)
  const [days, setDays] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (s && !form) {
      setForm({
        shift_1_start: s.shift_1_start, shift_1_hours: s.shift_1_hours, shift_1_break_mins: s.shift_1_break_mins,
        shift_2_start: s.shift_2_start, shift_2_hours: s.shift_2_hours, shift_2_break_mins: s.shift_2_break_mins,
        shift_count: s.shift_count, target_lph: s.target_lph, yield_target_pct: s.yield_target_pct,
        enable_packing: s.enable_packing, enable_bulk_pour: s.enable_bulk_pour, enable_device_gateway: s.enable_device_gateway,
        operating_days: [], use_work_orders: !s.simple_mode,
        pump_form_url: s.pump_form_url, pump_form_label: s.pump_form_label,
      })
      setDays(daysStringToSet(s.operating_days))
    }
  }, [s, form])

  const mutation = useMutation({
    mutationFn: () => adminApi.updateSettings({ ...form!, operating_days: Array.from(days) }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] })
      setForm({
        shift_1_start: result.saved.shift_1_start, shift_1_hours: result.saved.shift_1_hours,
        shift_1_break_mins: result.saved.shift_1_break_mins,
        shift_2_start: result.saved.shift_2_start, shift_2_hours: result.saved.shift_2_hours,
        shift_2_break_mins: result.saved.shift_2_break_mins,
        shift_count: result.saved.shift_count, target_lph: result.saved.target_lph,
        yield_target_pct: result.saved.yield_target_pct,
        enable_packing: result.saved.enable_packing, enable_bulk_pour: result.saved.enable_bulk_pour,
        enable_device_gateway: result.saved.enable_device_gateway,
        operating_days: [], use_work_orders: !result.saved.simple_mode,
        pump_form_url: result.saved.pump_form_url, pump_form_label: result.saved.pump_form_label,
      })
      setDays(daysStringToSet(result.saved.operating_days))
    },
  })

  if (!form) return null
  const set = <K extends keyof UpdatePlantSettingsRequest>(key: K, value: UpdatePlantSettingsRequest[K]) =>
    setForm((f) => (f ? { ...f, [key]: value } : f))

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold text-white">☀️ Shift 1 Schedule</p>
          <label className={fl.label}>Start Time (HH:MM)</label>
          <input className={input} value={form.shift_1_start} onChange={(e) => set('shift_1_start', e.target.value)} />
          <label className={fl.label}>Duration (Hours)</label>
          <input className={input} type="number" step={0.5} value={form.shift_1_hours} onChange={(e) => set('shift_1_hours', Number(e.target.value))} />
          <label className={fl.label}>Break Time (Mins)</label>
          <input className={input} type="number" step={15} value={form.shift_1_break_mins} onChange={(e) => set('shift_1_break_mins', Number(e.target.value))} />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold text-white">🌙 Shift 2 Schedule</p>
          <label className={fl.label}>Start Time (HH:MM)</label>
          <input className={input} value={form.shift_2_start} onChange={(e) => set('shift_2_start', e.target.value)} />
          <label className={fl.label}>Duration (Hours)</label>
          <input className={input} type="number" step={0.5} value={form.shift_2_hours} onChange={(e) => set('shift_2_hours', Number(e.target.value))} />
          <label className={fl.label}>Break Time (Mins)</label>
          <input className={input} type="number" step={15} value={form.shift_2_break_mins} onChange={(e) => set('shift_2_break_mins', Number(e.target.value))} />
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold text-white">🎯 Performance Targets</p>
          <label className={fl.label}>Shifts run per day</label>
          <input className={input} type="number" min={1} max={3} value={form.shift_count} onChange={(e) => set('shift_count', Number(e.target.value))} />
          <label className={fl.label}>Fallback Rate (L/h) — used by pumps with no rate of their own</label>
          <input className={input} type="number" step={10} value={form.target_lph} onChange={(e) => set('target_lph', Number(e.target.value))} />
          <label className={fl.label}>Yield Target (%)</label>
          <input className={input} type="number" step={0.5} value={form.yield_target_pct} onChange={(e) => set('yield_target_pct', Number(e.target.value))} />
          <label className="mt-2 flex items-center gap-2 text-sm text-[#CBD5E1]">
            <input type="checkbox" checked={form.enable_packing} onChange={(e) => set('enable_packing', e.target.checked)} />
            📦 Enable Packing Module globally
          </label>
          <label className="flex items-center gap-2 text-sm text-[#CBD5E1]">
            <input type="checkbox" checked={form.enable_bulk_pour} onChange={(e) => set('enable_bulk_pour', e.target.checked)} />
            🛢️ Allow measured pours (any container the app doesn't know)
          </label>
          <label className="flex items-center gap-2 text-sm text-[#CBD5E1]">
            <input type="checkbox" checked={form.enable_device_gateway} onChange={(e) => set('enable_device_gateway', e.target.checked)} />
            🔌 Machine gateway (bench scales, pump controllers)
          </label>
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold text-white">📅 Days this plant runs</p>
        <p className={`text-xs ${fl.muted}`}>
          Shifts only count as running on these days, so the stopped-record alarm stays quiet on a weekend or a
          shutdown day. A shift counts by the day it STARTS, so a Friday night shift is still watched into Saturday.
        </p>
        <div className="mt-2 flex flex-wrap gap-3">
          {DAY_LABELS.map((label, i) => (
            <label key={label} className="flex items-center gap-1.5 text-sm text-[#CBD5E1]">
              <input
                type="checkbox" checked={days.has(i)}
                onChange={(e) => setDays((d) => { const nd = new Set(d); e.target.checked ? nd.add(i) : nd.delete(i); return nd })}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold text-white">🏭 How this plant runs this system</p>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <label className={`flex-1 rounded-lg border p-3 text-sm ${!form.use_work_orders ? 'border-[#EA580C] bg-[#EA580C]/10' : 'border-[#334155]'}`}>
            <input type="radio" className="mr-2" checked={!form.use_work_orders} onChange={() => set('use_work_orders', false)} />
            <b className="text-white">Logging system</b>
            <p className={`mt-1 ${fl.muted}`}>Operators log; managers read the record and run the system. No work orders, and no separate IT role.</p>
          </label>
          <label className={`flex-1 rounded-lg border p-3 text-sm ${form.use_work_orders ? 'border-[#EA580C] bg-[#EA580C]/10' : 'border-[#334155]'}`}>
            <input type="radio" className="mr-2" checked={form.use_work_orders} onChange={() => set('use_work_orders', true)} />
            <b className="text-white">Execution system</b>
            <p className={`mt-1 ${fl.muted}`}>Work orders dispatched to stations and tracked against a target, and administration separated from the manager role again.</p>
          </label>
        </div>
      </div>

      <div>
        <p className="text-sm font-semibold text-white">🔗 Pump Form Link</p>
        <p className={`text-xs ${fl.muted}`}>
          Puts a button on the operator terminal that opens this address in a new tab. Leave it empty and no button appears.
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-[3fr_2fr]">
          <input className={input} placeholder="https://forms.example.com/pump-check" value={form.pump_form_url} onChange={(e) => set('pump_form_url', e.target.value)} />
          <input className={input} placeholder="Open the pump form" value={form.pump_form_label} onChange={(e) => set('pump_form_label', e.target.value)} />
        </div>
      </div>

      {mutation.data?.pump_form_warning && <p className="text-sm text-amber-400">⚠️ {mutation.data.pump_form_warning}</p>}
      {mutation.data?.orders_off_warning && <p className="text-sm text-amber-400">⚠️ {mutation.data.orders_off_warning}</p>}
      {mutation.data?.no_admin_warning && <p className="text-sm text-red-400">🔒 {mutation.data.no_admin_warning}</p>}

      <button className={fl.btn} disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        💾 Save Operational Parameters
      </button>
    </div>
  )
}

const PUMP_TYPES = [
  { value: '', label: '— type not set —' },
  { value: 'piston_diaphragm', label: 'Piston diaphragm' },
  { value: 'electric_motor', label: 'Electric motor' },
]

function PumpsPanel() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin-pumps'], queryFn: adminApi.pumps })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-pumps'] })
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('')
  const [rates, setRates] = useState<Record<number, number>>({})

  const addMutation = useMutation({ mutationFn: () => adminApi.addPump(newName.trim(), newType), onSuccess: () => { setNewName(''); setNewType(''); invalidate() } })
  const rateMutation = useMutation({ mutationFn: ({ id, rate }: { id: number; rate: number }) => adminApi.setPumpRate(id, rate), onSuccess: invalidate })
  const deleteMutation = useMutation({ mutationFn: (id: number) => adminApi.deletePump(id), onSuccess: invalidate })

  const pumps = query.data ?? []
  const typeMutation = useMutation({
    mutationFn: ({ id, pumpType }: { id: number; pumpType: string }) => adminApi.setPumpType(id, pumpType),
    onSuccess: invalidate,
  })

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-white">🏷️ Pump Stations</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input className={`${input} flex-1`} placeholder="e.g. Station A" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <select className={`${fl.select} sm:w-52`} value={newType} onChange={(e) => setNewType(e.target.value)}>
          {PUMP_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <button className={fl.btn} disabled={!newName.trim() || addMutation.isPending} onClick={() => addMutation.mutate()}>➕ Add</button>
      </div>
      <p className={`text-xs ${fl.muted}`}>
        The expected rate lives on the pump. A pump with no rate of its own uses what its own shifts measure;
        pumps with neither share the plant fallback figure between them, rather than each claiming all of it.
      </p>
      <div className="flex flex-col gap-2">
        {pumps.map((p) => (
          <div key={p.id} className="rounded-lg border border-[#334155] bg-[#0F172A] p-3">
            <div className="flex items-center justify-between">
              <b className="text-white">{p.station_name}</b>
              <span className={`text-xs font-bold ${p.status === 'Active' ? 'text-emerald-400' : 'text-amber-400'}`}>● {p.status}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span className={`text-xs ${fl.muted}`}>Type</span>
              <select
                className={`${fl.select} w-52`}
                value={p.pump_type ?? ''}
                onChange={(e) => typeMutation.mutate({ id: p.id, pumpType: e.target.value })}
              >
                {PUMP_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <p className={`text-xs ${fl.muted}`}>
              expects {p.target_lph
                ? `${p.target_lph.toLocaleString()} L/h`
                : p.measured_median_lph
                  ? `${p.measured_median_lph.toLocaleString()} L/h (measured from its own shifts)`
                  : `a share of the plant figure — no rate set and not enough shifts to measure one`}
            </p>
            <p className={`text-xs ${fl.muted}`}>
              {p.measured_median_lph
                ? `Measured: ${p.measured_median_lph.toLocaleString()} L/h median over ${p.measured_samples} shifts.`
                : 'Not enough shifts logged yet to measure this one.'}
            </p>
            <div className="mt-2 flex items-center gap-2">
              <input
                className={`${input} w-32`} type="number" step={10} min={0} max={5000}
                value={rates[p.id] ?? p.target_lph ?? 0}
                onChange={(e) => setRates((r) => ({ ...r, [p.id]: Number(e.target.value) }))}
              />
              <button
                className={fl.btnSecondary} disabled={rateMutation.isPending}
                onClick={() => rateMutation.mutate({ id: p.id, rate: rates[p.id] ?? p.target_lph ?? 0 })}
              >
                💾
              </button>
              {p.measured_median_lph != null && Math.abs(p.measured_median_lph - (p.target_lph ?? p.effective_lph)) >= 25 && (
                <button className={fl.btnSecondary} onClick={() => rateMutation.mutate({ id: p.id, rate: p.measured_median_lph! })}>
                  ↩️ Use measured {p.measured_median_lph.toLocaleString()} L/h
                </button>
              )}
              <button className={fl.btnDanger} disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(p.id)}>🗑️</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function DowntimeCodesPanel() {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['admin-downtime-reasons'], queryFn: adminApi.downtimeReasons })
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin-downtime-reasons'] })
  const [newName, setNewName] = useState('')

  const addMutation = useMutation({ mutationFn: () => adminApi.addDowntimeReason(newName), onSuccess: () => { setNewName(''); invalidate() } })
  const deleteMutation = useMutation({ mutationFn: (id: number) => adminApi.deleteDowntimeReason(id), onSuccess: invalidate })

  const reasons = query.data ?? []

  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-white">⚠️ Downtime Codes</p>
      <div className="flex gap-2">
        <input className={`${input} flex-1`} placeholder="e.g. Missing Materials" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button className={fl.btn} disabled={!newName.trim() || addMutation.isPending} onClick={() => addMutation.mutate()}>➕ Add</button>
      </div>
      <div className="flex flex-col gap-2">
        {reasons.map((r) => (
          <div key={r.id} className="flex items-center justify-between rounded-lg border border-[#334155] bg-[#0F172A] p-3">
            <b className="text-[#A855F7]">{r.reason_name}</b>
            <button className={fl.btnDanger} disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(r.id)}>🗑️</button>
          </div>
        ))}
      </div>
    </div>
  )
}

export function SettingsTab() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className={fl.heading}>🏭 Global Plant Operational Parameters</p>
        <p className={`text-xs ${fl.muted}`}>Update shift schedules, pacing targets, and module availability globally.</p>
      </div>
      <PlantConfigForm />
      <hr className={fl.divider} />
      <p className={fl.heading}>⚙️ Master Plant Equipment &amp; Configuration</p>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <PumpsPanel />
        <DowntimeCodesPanel />
      </div>
    </div>
  )
}
