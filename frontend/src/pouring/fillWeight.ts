// A direct port of fill_weight.py's judge()/describe() - pure arithmetic on
// numbers the operator screen already has (the resin's target/min/max from
// /reference/resins), so this runs client-side for instant feedback exactly
// like the Streamlit version's every-keystroke rerun did, with no round
// trip. The actual submitted reading is re-judged server-side in
// api/routers/pouring.py's /submit using the same fill_weight.py this
// mirrors, so the two can never disagree about what was recorded.
export interface WeightVerdict {
  measured: number
  target: number
  deviation: number
  status: 'in' | 'under' | 'over' | null
  pct_of_fill: number
}

const PLAUSIBLE_MIN_G = 1
const PLAUSIBLE_MAX_G = 100_000

export function judge(
  measured: number | null,
  spec: { target_g: number; min_g: number; max_g: number } | null,
): WeightVerdict | null {
  if (measured === null || Number.isNaN(measured)) return null
  if (measured < PLAUSIBLE_MIN_G || measured > PLAUSIBLE_MAX_G) return null
  if (!spec || !spec.target_g) return null

  const { target_g: target, min_g: lo, max_g: hi } = spec
  const deviation = measured - target

  let status: WeightVerdict['status']
  if (lo != null && measured < lo) status = 'under'
  else if (hi != null && measured > hi) status = 'over'
  else if (lo == null && hi == null) status = null
  else status = 'in'

  return {
    measured,
    target,
    deviation: Math.round(deviation * 100) / 100,
    status,
    pct_of_fill: target ? Math.round((deviation / target) * 100 * 1000) / 1000 : 0,
  }
}

export function describe(verdict: WeightVerdict | null): { icon: string; message: string } {
  if (!verdict) return { icon: '', message: '' }
  const { deviation, status } = verdict
  const off =
    Math.abs(deviation) < 0.05
      ? 'exactly on target'
      : `${Math.abs(deviation).toFixed(1)} g ${deviation > 0 ? 'over' : 'under'} target`

  if (status === 'in') return { icon: '✅', message: `In band — ${off}.` }
  if (status === 'over') return { icon: '🔺', message: `Over the high limit — ${off}. Worth flagging to your lead.` }
  if (status === 'under') return { icon: '🔻', message: `Under the low limit — ${off}. Worth flagging to your lead.` }
  return { icon: '•', message: `Recorded — ${off}.` }
}
