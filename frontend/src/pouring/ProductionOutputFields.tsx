import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { pouringApi } from '../api/pouring'
import { describe, judge } from './fillWeight'
import { fl } from '../theme'

export interface BulkState {
  containers: number
  amountEach: number
  unit: string
  offTank: boolean
  note: string
}

export const EMPTY_BULK: BulkState = { containers: 1, amountEach: 0, unit: 'L', offTank: false, note: '' }

interface WeightSpec {
  target_g: number
  min_g: number
  max_g: number
}

interface Props {
  station: string
  resin: string
  isBulk: boolean
  bulk: BulkState
  onBulkChange: (patch: Partial<BulkState>) => void
  onBulkBlockedChange: (blocked: boolean) => void
  bottlesFilled: number
  onBottlesFilledChange: (n: number) => void
  scrapEmpty: number
  onScrapEmptyChange: (n: number) => void
  scrapFilled: number
  onScrapFilledChange: (n: number) => void
  checkWeightG: number | null
  onCheckWeightChange: (n: number | null) => void
  weightSpec: WeightSpec | null
}

const input = `${fl.input} py-3 text-base font-normal text-[#F8FAFC]`
const label = `mb-1 block ${fl.label}`

// Ported from pouring_tab.py lines ~530-655: bulk-vs-unit output, scrap, and
// the optional check weight. Bulk litres/blocking comes from the server
// (bulk_pour.py needs a DB-backed vessel capacity lookup); the weight
// judgement is pure arithmetic and runs client-side (see ./fillWeight.ts).
export function ProductionOutputFields({
  station, resin, isBulk, bulk, onBulkChange, onBulkBlockedChange,
  bottlesFilled, onBottlesFilledChange, scrapEmpty, onScrapEmptyChange,
  scrapFilled, onScrapFilledChange, checkWeightG, onCheckWeightChange, weightSpec,
}: Props) {
  const debouncedBulk = useDebouncedValue(bulk, 300)
  const bulkPreview = useQuery({
    queryKey: ['pouring', 'bulk-preview', station, resin, debouncedBulk],
    queryFn: () =>
      pouringApi.bulkPreview({
        resin, station, containers: debouncedBulk.containers, amount_each: debouncedBulk.amountEach,
        unit: debouncedBulk.unit, off_tank: debouncedBulk.offTank, note: debouncedBulk.note,
      }),
    enabled: isBulk && !!station && !!resin && debouncedBulk.amountEach > 0,
  })

  const blocked = isBulk && (bulkPreview.data?.blocked ?? false)
  useEffect(() => {
    onBulkBlockedChange(blocked)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [blocked])

  const weightVerdict = judge(checkWeightG, weightSpec)
  const { icon, message } = describe(weightVerdict)

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-[#CBD5E1]">
        3. Production Output
      </h3>

      {isBulk ? (
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className={label}>Amount each</label>
              <input
                className={input}
                type="number"
                min={0}
                step="0.01"
                value={bulk.amountEach || ''}
                onChange={(e) => onBulkChange({ amountEach: Number(e.target.value) })}
              />
            </div>
            <div>
              <label className={label}>Unit</label>
              <select className={input} value={bulk.unit} onChange={(e) => onBulkChange({ unit: e.target.value })}>
                <option value="L">L</option>
                <option value="kg">kg</option>
              </select>
            </div>
            <div>
              <label className={label}>Containers</label>
              <input
                className={input}
                type="number"
                min={1}
                max={999}
                value={bulk.containers}
                onChange={(e) => onBulkChange({ containers: Number(e.target.value) })}
              />
            </div>
          </div>

          <input
            className={input}
            placeholder="Poured into (brown 1L bottles, 55 gal drum, blue tote...)"
            maxLength={60}
            value={bulk.note}
            onChange={(e) => onBulkChange({ note: e.target.value })}
          />

          <label className="flex items-center gap-2 text-sm text-[#CBD5E1]">
            <input
              type="checkbox"
              checked={bulk.offTank}
              onChange={(e) => onBulkChange({ offTank: e.target.checked })}
            />
            Came from a drum or container already off the tank (not this station's vessel)
          </label>

          {bulkPreview.data && bulkPreview.data.litres > 0 && (
            <p className="text-sm font-medium text-[#CBD5E1]">
              {bulkPreview.data.description}
            </p>
          )}
          {bulkPreview.data?.message && (
            <p
              className={
                bulkPreview.data.blocked
                  ? 'text-sm text-red-400'
                  : 'text-sm text-amber-400'
              }
            >
              {bulkPreview.data.message}
            </p>
          )}
        </div>
      ) : (
        <div>
          <label className={label}>✅ Good Units / Containers Filled</label>
          <input
            className={input}
            type="number"
            min={0}
            step={10}
            value={bottlesFilled}
            onChange={(e) => onBottlesFilledChange(Number(e.target.value))}
          />
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className={label}>🗑️ Scrap Empty</label>
          <input
            className={input}
            type="number"
            min={0}
            value={scrapEmpty}
            onChange={(e) => onScrapEmptyChange(Number(e.target.value))}
          />
        </div>
        <div>
          <label className={label}>🗑️ Scrap Filled</label>
          <input
            className={input}
            type="number"
            min={0}
            value={scrapFilled}
            onChange={(e) => onScrapFilledChange(Number(e.target.value))}
          />
        </div>
      </div>

      <div>
        <label className={label}>⚖️ Check weight (g) — optional</label>
        <input
          className={input}
          type="number"
          min={0}
          placeholder="leave blank if not weighed"
          value={checkWeightG ?? ''}
          onChange={(e) => onCheckWeightChange(e.target.value === '' ? null : Number(e.target.value))}
        />
        {checkWeightG != null && !weightVerdict && !weightSpec && (
          <p className={`mt-1 text-xs ${fl.muted}`}>
            Recorded, but there's no weight spec on file for this resin yet.
          </p>
        )}
        {weightVerdict && (
          <p className="mt-1 text-sm font-medium text-[#F8FAFC]">
            {icon} {message}
          </p>
        )}
      </div>
    </div>
  )
}
