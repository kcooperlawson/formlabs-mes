import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useLotGate } from '../hooks/useLotGate'
import { pouringApi } from '../api/pouring'
import { playAlert } from '../sound/chimes'
import { fl } from '../theme'

export interface LotFieldsState {
  enteredLot: string
  fastConfirm: boolean
  reasonKind: string
  reasonDetail: string
  photo: File | null
}

export const EMPTY_LOT_FIELDS: LotFieldsState = {
  enteredLot: '',
  fastConfirm: false,
  reasonKind: '',
  reasonDetail: '',
  photo: null,
}

interface Props {
  station: string
  resin: string
  cartCode: string
  value: LotFieldsState
  onChange: (patch: Partial<LotFieldsState>) => void
  /** Reports whether every requirement for this gate is currently satisfied,
   * so the parent's submit button can grey out - mirrors pouring_tab.py's
   * own `gate_ok`/`gate_blockers`. Called from an effect, never during
   * render, since it ultimately updates state in a different component. */
  onGateOkChange: (ok: boolean, blockers: string[]) => void
}

const REASON_OPTIONS = [
  '', 'Wrong pallet staged at the station', 'Label misprint or unreadable',
  'Cartridge was relabeled', 'Run lot in the MES is wrong', 'Lead approved the pour', 'Other',
]

const input = `${fl.input} py-3 text-base font-normal text-[#F8FAFC]`

// Ported from pouring_tab.py lines ~295-505. The gate's own GET (useLotGate)
// never carries the real expected lot - only whether it applies, and (once
// something has been verified before) the fast path's own display text,
// which is what THIS operator typed last time, not the hidden value it was
// checked against. The actual verdict comes from a live GET as they type
// (debounced) that runs the same comparison /submit will re-run for real.
export function LotVerificationGate({ station, resin, cartCode, value, onChange, onGateOkChange }: Props) {
  const gateQuery = useLotGate(station, resin, cartCode)
  const gate = gateQuery.data

  const debouncedLot = useDebouncedValue(value.enteredLot, 400)
  const checkQuery = useQuery({
    queryKey: ['pouring', 'lot-check', station, resin, cartCode, debouncedLot],
    queryFn: () => pouringApi.lotCheck(station, resin, cartCode, debouncedLot),
    enabled: !!gate && gate.gate_applies && !gate.fast_path && debouncedLot.trim().length > 0,
  })
  const result = gate?.gate_applies && !gate.fast_path ? checkQuery.data?.result : undefined

  let ok = false
  const blockers: string[] = []
  if (gate) {
    if (!gate.gate_applies) {
      ok = true
    } else if (gate.fast_path) {
      ok = value.fastConfirm
      if (!ok) blockers.push('confirm the cartridge still reads the lot shown above')
    } else {
      if (!value.enteredLot.trim()) blockers.push(`type the L- lot from the ${gate.noun}`)
      if (result === 'mismatch' && !(value.reasonKind && value.reasonDetail.trim())) {
        blockers.push('pick a reason and add details before logging a flagged pour')
      }
      if (result === 'mismatch' && !value.photo) blockers.push(`photograph the ${gate.noun} bottom`)
      ok = blockers.length === 0
    }
  }

  // Side effects on other components' state belong in an effect, not the
  // render body - this fires after commit, once per actual change.
  useEffect(() => {
    onGateOkChange(ok, blockers)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ok, blockers.join('|')])

  // Fires once per transition into 'mismatch', not on every render while
  // it stays that way - result is the effect's only dependency, so React
  // only re-runs this when the verdict itself actually changes. The catch
  // is worth its own sound: the lot check doing exactly its job, not an
  // ordinary log landing.
  useEffect(() => {
    if (result === 'mismatch') playAlert()
  }, [result])

  // A tick counter rather than a boolean so each fresh mismatch/verified
  // verdict gets its own key and the CSS animation replays - a boolean
  // would only fire the very first time, since the class name itself
  // wouldn't change on a later render that lands on the same result.
  const [shakeTick, setShakeTick] = useState(0)
  const [pulseTick, setPulseTick] = useState(0)
  useEffect(() => {
    if (result === 'mismatch') setShakeTick((t) => t + 1)
    if (result === 'verified') setPulseTick((t) => t + 1)
  }, [result])

  if (!gate) return null

  if (!gate.gate_applies) {
    return (
      <div>
        <p className={`text-sm ${fl.muted}`}>
          No lot label on this format — nothing to verify.
        </p>
        <input
          className={input}
          value={value.enteredLot || gate.auto_lot}
          onChange={(e) => onChange({ enteredLot: e.target.value })}
          placeholder="Batch Lot Number"
        />
      </div>
    )
  }

  if (gate.fast_path) {
    return (
      <div className="flex flex-col gap-2">
        <p className="rounded-lg border border-emerald-800 bg-emerald-950 px-3 py-2 text-sm text-emerald-300">
          ✅ Verified by {gate.fast_path.by} — same run, same lot, same station.
        </p>
        <label className="flex items-center gap-2 text-sm text-[#CBD5E1]">
          <input
            type="checkbox"
            checked={value.fastConfirm}
            onChange={(e) => onChange({ fastConfirm: e.target.checked, enteredLot: '' })}
          />
          {gate.still_reads_label} <strong className="text-white">L-{gate.fast_path.entered_masked}</strong>
        </label>
        <p className={`text-xs ${fl.muted}`}>
          A full check comes back on any change of run, lot, resin or station, after 4 hours,
          and on every 10th log.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {gate.expected_is_real ? (
        <p className={`text-sm ${fl.muted}`}>
          Expected lot for this run: <code>• • • • • • • • •</code> — hidden on purpose, read the{' '}
          {gate.noun}, not the screen.
        </p>
      ) : (
        <p className={`text-sm ${fl.muted}`}>
          {gate.matched_run
            ? `No open run matches this station, resin and format, so the ${gate.noun} lot is recorded rather than checked.`
            : `Recorded rather than checked - ${gate.where_hint}`}
        </p>
      )}

      <input
        className={input}
        value={value.enteredLot}
        onChange={(e) => onChange({ enteredLot: e.target.value })}
        placeholder="2411A0742"
      />

      {result === 'verified' && (
        <p key={pulseTick} className="fl-pulse-good rounded text-sm font-medium text-emerald-400">✅ Lot matches this run.</p>
      )}
      {result === 'recorded' && (
        <p className="text-sm text-[#CBD5E1]">📝 Lot recorded against this log.</p>
      )}
      {result === 'mismatch' && (
        <div key={shakeTick} className="fl-shake flex flex-col gap-2 rounded-lg border border-red-800 bg-red-950 p-3">
          <p className="text-sm font-semibold text-red-300">
            ⛔ STOP — DO NOT POUR. This {gate.noun} is not from the lot assigned to your run.
          </p>
          <p className="text-xs text-red-400">Logging it anyway? Say what happened.</p>
          <select
            className={input}
            value={value.reasonKind}
            onChange={(e) => onChange({ reasonKind: e.target.value })}
          >
            {REASON_OPTIONS.map((r) => (
              <option key={r} value={r}>
                {r || '— pick a reason —'}
              </option>
            ))}
          </select>
          <input
            className={input}
            value={value.reasonDetail}
            onChange={(e) => onChange({ reasonDetail: e.target.value })}
            placeholder="Details (required)"
          />
          <label className="text-sm text-[#CBD5E1]">
            Photograph the {gate.noun} bottom — required to log a pour against a flag.
            <input
              className="mt-1 block text-sm text-[#CBD5E1]"
              type="file"
              accept="image/*"
              onChange={(e) => onChange({ photo: e.target.files?.[0] ?? null })}
            />
          </label>
        </div>
      )}
    </div>
  )
}
