import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { referenceApi } from '../api/reference'
import { pouringApi } from '../api/pouring'
import { useLotGate } from '../hooks/useLotGate'
import { useSubmitLock } from '../hooks/useSubmitLock'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { useToast } from '../toast/ToastProvider'
import { ChangeoverBanner } from './ChangeoverBanner'
import { EMPTY_BULK, ProductionOutputFields, type BulkState } from './ProductionOutputFields'
import { EMPTY_LOT_FIELDS, LotVerificationGate, type LotFieldsState } from './LotVerificationGate'
import { SubmitBar } from './SubmitBar'
import { fl } from '../theme'

const select = `${fl.select} py-3 text-base`
const label = `mb-1 block ${fl.label}`
const textarea = `${fl.input} py-2 text-base font-normal text-[var(--fl-ink)]`

interface UndoState {
  logId: number
  units: number
  expiresAt: number
}

// The Hourly Pouring Count tab, assembled from every piece the pilot has
// built so far: the changeover mechanic (ChangeoverBanner), the lot
// verification gate, and the production-output/submit machinery. Ported
// from pages/operator_form/pouring_tab.py's render(ctx) end to end - see
// that file's own section comments (1. Station & Material, 2. Lot
// Verification, 3. Production Output) for the parts this mirrors.
export function PouringTab({ shift }: { shift: string }) {
  const queryClient = useQueryClient()
  const submitLock = useSubmitLock()
  const asOperator = useDebugOperator()
  const toast = useToast()

  const [station, setStation] = useState('')
  const [cartLabel, setCartLabel] = useState('')
  const [resin, setResin] = useState('')
  const [bottlesFilled, setBottlesFilled] = useState(250)
  const [scrapEmpty, setScrapEmpty] = useState(0)
  const [scrapFilled, setScrapFilled] = useState(0)
  const [checkWeightG, setCheckWeightG] = useState<number | null>(null)
  const [notes, setNotes] = useState('')
  const [bulk, setBulk] = useState<BulkState>(EMPTY_BULK)
  const [lot, setLot] = useState<LotFieldsState>(EMPTY_LOT_FIELDS)
  const [gateOk, setGateOk] = useState(false)
  const [gateBlockers, setGateBlockers] = useState<string[]>([])
  const [bulkBlocked, setBulkBlocked] = useState(false)
  const [undo, setUndo] = useState<UndoState | null>(null)
  const [result, setResult] = useState<{ landed: string; messages: string[] } | null>(null)

  const pumpsQuery = useQuery({ queryKey: ['reference', 'pumps'], queryFn: referenceApi.pumps })
  const resinsQuery = useQuery({ queryKey: ['reference', 'resins'], queryFn: referenceApi.resins })
  const plantSettingsQuery = useQuery({
    queryKey: ['reference', 'plant-settings'],
    queryFn: referenceApi.plantSettings,
  })
  const bulkEnabled = plantSettingsQuery.data?.enable_bulk_pour ?? false
  const formatsQuery = useQuery({
    queryKey: ['reference', 'container-formats', bulkEnabled],
    queryFn: () => referenceApi.containerFormats(bulkEnabled),
    enabled: plantSettingsQuery.isSuccess,
  })

  const cartCode = formatsQuery.data?.codes[cartLabel] ?? ''
  const isBulk = cartCode === 'Bulk'
  const isOffTank = isBulk && bulk.offTank

  const resinNames = [...new Set((resinsQuery.data ?? []).map((r) => r.resin_name))].sort()
  // The picker's own target-weight caption prefers a spec matched to this
  // exact cartridge format, falling back to any format's spec for the
  // resin - mirrors pouring_tab.py's cart_matched/all_specs_df fallback.
  const weightSpec =
    (resinsQuery.data ?? []).find((r) => r.resin_name === resin && r.cartridge_type === cartCode) ??
    (resinsQuery.data ?? []).find((r) => r.resin_name === resin) ??
    null

  const gateQuery = useLotGate(station, resin, cartCode)

  const invalidateAfterWrite = () => {
    queryClient.invalidateQueries({ queryKey: ['pouring', 'reactor-lookup', station, resin] })
    queryClient.invalidateQueries({ queryKey: ['pouring', 'lot-gate', station, resin, cartCode] })
  }

  const submitMutation = useMutation({
    mutationFn: (formData: FormData) => pouringApi.submit(formData),
    onSuccess: (resp) => {
      setResult({ landed: resp.landed, messages: resp.messages })
      if (resp.log_id) {
        setUndo({ logId: resp.log_id, units: isBulk ? bulk.containers : bottlesFilled,
                  expiresAt: Date.now() + 120_000 })
      }
      setLot(EMPTY_LOT_FIELDS)
      submitLock.lock()
      invalidateAfterWrite()
      toast.show(resp.landed || 'Logged.')
    },
  })

  const undoMutation = useMutation({
    mutationFn: (logId: number) => pouringApi.undo(logId, asOperator),
    onSuccess: (resp) => {
      if (resp.ok) setUndo(null)
      setResult({ landed: '', messages: [resp.message] })
      toast.show(resp.message, resp.ok ? 'success' : 'error')
    },
  })

  const canSubmit = gateOk && !(isBulk && bulkBlocked) && !!station && !!resin && !!cartCode

  const handleSubmit = () => {
    const fd = new FormData()
    fd.set('station', station)
    fd.set('cartridge_type', cartCode)
    fd.set('resin', resin)
    fd.set('entered_lot', lot.enteredLot || (!gateQuery.data?.gate_applies ? gateQuery.data?.auto_lot ?? '' : ''))
    fd.set('fast_confirm', String(lot.fastConfirm))
    fd.set('mismatch_reason_kind', lot.reasonKind)
    fd.set('mismatch_reason_detail', lot.reasonDetail)
    if (lot.photo) fd.set('mismatch_photo', lot.photo)
    fd.set('is_bulk', String(isBulk))
    fd.set('bulk_containers', String(bulk.containers))
    fd.set('bulk_amount_each', String(bulk.amountEach))
    fd.set('bulk_unit', bulk.unit)
    fd.set('bulk_off_tank', String(bulk.offTank))
    fd.set('bulk_note', bulk.note)
    fd.set('bottles_filled', String(bottlesFilled))
    fd.set('scrap_empty', String(scrapEmpty))
    fd.set('scrap_filled', String(scrapFilled))
    if (checkWeightG != null) fd.set('check_weight_g', String(checkWeightG))
    fd.set('notes', notes)
    if (asOperator) fd.set('as_operator', asOperator)
    submitMutation.mutate(fd)
  }

  return (
    <div className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-[#CBD5E1]">
        1. Station & Material Setup
      </h3>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className={label}>Pump Station</label>
          <select className={select} value={station} onChange={(e) => setStation(e.target.value)}>
            <option value="">— choose —</option>
            {(pumpsQuery.data ?? []).map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={label}>Container Format</label>
          <select className={select} value={cartLabel} onChange={(e) => setCartLabel(e.target.value)}>
            <option value="">— choose —</option>
            {(formatsQuery.data?.labels ?? []).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={label}>Resin Formulation</label>
          <select className={select} value={resin} onChange={(e) => setResin(e.target.value)}>
            <option value="">— choose —</option>
            {resinNames.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </div>
      {weightSpec && (
        <p
          className="inline-block w-fit rounded-md border px-2 py-0.5 text-xs font-semibold"
          style={{ backgroundColor: weightSpec.color.bg, color: weightSpec.color.fg, borderColor: weightSpec.color.border }}
        >
          {weightSpec.resin_name} · target {weightSpec.target_g}g
        </p>
      )}

      {station && resin && !isOffTank && (
        <ChangeoverBanner station={station} resin={resin} shift={shift} />
      )}
      {isOffTank && (
        <p className={`text-sm ${fl.muted}`}>
          🛢️ No tank on this one — it came out of a drum.
        </p>
      )}

      {station && resin && cartCode && (
        <>
          <hr className={fl.divider} />
          <h3 className="text-sm font-semibold text-[#CBD5E1]">
            2. Lot Verification
          </h3>
          <LotVerificationGate
            station={station}
            resin={resin}
            cartCode={cartCode}
            value={lot}
            onChange={(patch) => setLot((prev) => ({ ...prev, ...patch }))}
            onGateOkChange={(ok, blockers) => {
              setGateOk(ok)
              setGateBlockers(blockers)
            }}
          />

          <hr className={fl.divider} />
          <ProductionOutputFields
            station={station}
            resin={resin}
            isBulk={isBulk}
            bulk={bulk}
            onBulkChange={(patch) => setBulk((prev) => ({ ...prev, ...patch }))}
            onBulkBlockedChange={setBulkBlocked}
            bottlesFilled={bottlesFilled}
            onBottlesFilledChange={setBottlesFilled}
            scrapEmpty={scrapEmpty}
            onScrapEmptyChange={setScrapEmpty}
            scrapFilled={scrapFilled}
            onScrapFilledChange={setScrapFilled}
            checkWeightG={checkWeightG}
            onCheckWeightChange={setCheckWeightG}
            weightSpec={weightSpec}
          />

          <div>
            <label className={label}>Process Observations / Notes</label>
            <textarea
              className={textarea}
              rows={2}
              placeholder="e.g. Target fill weight nominal..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          {result && (
            <div className={`${fl.card} text-sm`}>
              {result.landed && <p className="font-medium text-white">{result.landed}</p>}
              {result.messages.map((m, i) => (
                <p key={i} className="text-[#CBD5E1]">{m}</p>
              ))}
            </div>
          )}
          {submitMutation.isError && (
            <p className="text-sm text-red-400">
              {(submitMutation.error as Error).message}
            </p>
          )}

          <SubmitBar
            canSubmit={canSubmit}
            blockers={gateBlockers}
            locked={submitLock.locked}
            lockSecondsLeft={submitLock.secondsLeft}
            isSubmitting={submitMutation.isPending}
            onSubmit={handleSubmit}
            undo={undo}
            onUndo={() => undo && undoMutation.mutate(undo.logId)}
            isUndoing={undoMutation.isPending}
          />
        </>
      )}
    </div>
  )
}
