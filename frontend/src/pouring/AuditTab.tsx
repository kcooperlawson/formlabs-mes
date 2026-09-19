import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { referenceApi } from '../api/reference'
import { AUDIT_TYPES, auditApi } from '../api/audit'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { useToast } from '../toast/ToastProvider'
import { ChecklistStatus } from '../checklist/ChecklistStatus'
import { fl } from '../theme'

const input = `${fl.input} py-3 text-base font-normal text-[var(--fl-ink)]`
const label = `mb-1 block ${fl.label}`
const textarea = `${fl.input} py-2 text-base font-normal text-[var(--fl-ink)]`
const btn = `w-full ${fl.btn} py-4 text-base`

// Ported from pages/operator_form/audit_tab.py - cleanliness/changeover/
// spill photo audits. Unlike the checklist's own cleanliness step, a photo
// is never required here (the original submits unconditionally).
export function AuditTab({ myStation }: { myStation: string }) {
  const asOperator = useDebugOperator()
  const toast = useToast()
  const pumpsQuery = useQuery({ queryKey: ['reference', 'pumps'], queryFn: referenceApi.pumps })

  const [auditType, setAuditType] = useState<string>(AUDIT_TYPES[0])
  const [station, setStation] = useState(myStation)
  const [isSpill, setIsSpill] = useState(false)
  const [notes, setNotes] = useState('')
  const [photos, setPhotos] = useState<File[]>([])

  const submitMutation = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.set('audit_type', auditType)
      fd.set('station', station)
      fd.set('notes', notes)
      fd.set('is_spill', String(isSpill))
      if (asOperator) fd.set('as_operator', asOperator)
      photos.slice(0, 4).forEach((p) => fd.append('photos', p))
      return auditApi.submit(fd)
    },
    onSuccess: (resp) => {
      setNotes('')
      setPhotos([])
      toast.show(resp.message)
    },
  })

  return (
    <div className="flex flex-col gap-3">
      {/* Whether their own checks are on record, with any past day
          reachable - the photo audits live on this tab, so the question
          "have I done them" belongs here too. */}
      <ChecklistStatus compact />

      <h3 className="text-sm font-semibold text-[#CBD5E1]">
        📸 Cleanliness, Changeover & Spill Photo Audit
      </h3>
      <p className={`text-sm ${fl.muted}`}>
        Document station readiness, pump changeovers, end-of-shift washdowns, or resin spills.
      </p>

      <div>
        <label className={label}>Audit Checklist Event</label>
        <select
          className={input}
          value={auditType}
          onChange={(e) => {
            setAuditType(e.target.value)
            setIsSpill(e.target.value.includes('Spill'))
          }}
        >
          {AUDIT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div>
        <label className={label}>Pump / Workstation</label>
        <select className={input} value={station} onChange={(e) => setStation(e.target.value)}>
          {(pumpsQuery.data ?? []).map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm text-[#CBD5E1]">
        <input type="checkbox" checked={isSpill} onChange={(e) => setIsSpill(e.target.checked)} />
        ⚠️ Check if this is an active resin spill / leak incident
      </label>

      <div>
        <label className={label}>Audit Observations / Cleanliness Verification</label>
        <textarea
          className={textarea}
          rows={2}
          placeholder="e.g. Moving from Alpha Fast to White V5. Dispensing nozzles flushed and drip trays clear."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <div>
        <label className={label}>📷 Attach Inspection Photos</label>
        <p className={`mb-1 text-xs ${fl.muted}`}>
          The first photo is the main one; add more if the situation deserves it. Up to 4.
        </p>
        <input
          className="block text-sm text-[#CBD5E1]"
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => setPhotos(Array.from(e.target.files ?? []))}
        />
        {photos.length > 1 && (
          <p className={`mt-1 text-xs ${fl.muted}`}>
            {photos.length - 1} extra photo(s) will be attached.
          </p>
        )}
      </div>

      <button className={btn} disabled={submitMutation.isPending} onClick={() => submitMutation.mutate()}>
        💾 Submit Cleanliness & Photo Audit
      </button>
    </div>
  )
}
