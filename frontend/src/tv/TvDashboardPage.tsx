import { useQuery } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { tvApi, type PackingBreakdownRow, type TopPourer, type WorkOrderRow } from '../api/tv'
import { BuildFinale, CartridgeBuild, LayerBar, Odometer, ScreenSweep } from './PrintBuild'

const FINALE_SECONDS = 25_000

function useLiveClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

// The build-finale banner is played once per shift, the moment it reaches
// 100% - a client-side analogue of the original's st.session_state flag,
// living for as long as this tab stays open (a wall display's normal
// lifetime is "all shift", so that's the right scope for it).
function useBuildFinale(active: boolean, key: string): boolean {
  const firstDoneAt = useRef<Map<string, number>>(new Map())
  const [, force] = useState(0)
  useEffect(() => {
    if (active && !firstDoneAt.current.has(key)) {
      firstDoneAt.current.set(key, Date.now())
      const t = setTimeout(() => force((n) => n + 1), FINALE_SECONDS)
      return () => clearTimeout(t)
    }
  }, [active, key])
  if (!active) return false
  const startedAt = firstDoneAt.current.get(key)
  return startedAt != null && Date.now() - startedAt < FINALE_SECONDS
}

const cardStyle: React.CSSProperties = {
  background: 'linear-gradient(180deg, #0D1627 0%, #080D1A 100%)', border: '1px solid #1E2B45',
  borderRadius: 12, padding: 20, textAlign: 'center', boxShadow: '0 8px 24px rgba(0,0,0,0.5)', height: '100%',
}
const labelStyle: React.CSSProperties = { fontSize: '1rem', fontWeight: 700, color: '#94A3B8', letterSpacing: '0.1em', textTransform: 'uppercase' }

function TopPourersCard({ pourers }: { pourers: TopPourer[] }) {
  const top = Math.max(...pourers.map((p) => p.rate_lph), 0)
  return (
    <div style={cardStyle}>
      <div style={{ ...labelStyle, marginBottom: 6, textAlign: 'left' }}>💧 TOP POURERS (L/h)</div>
      <div style={{ textAlign: 'left', marginTop: 4 }}>
        {pourers.length === 0 ? (
          <div style={{ color: '#64748B', padding: '18px 0', textAlign: 'center' }}>Nothing poured on this shift yet.</div>
        ) : (
          pourers.map((p, i) => (
            <div key={p.operator} style={{ display: 'grid', gridTemplateColumns: '2.2rem 1fr auto', alignItems: 'center', gap: 14, padding: '9px 0', borderBottom: '1px solid #16213A' }}>
              <span style={{ fontSize: '1.1rem', fontWeight: 900, color: '#475569', textAlign: 'center' }}>{i + 1}</span>
              <span style={{ fontSize: '1.35rem', fontWeight: 700, color: '#E2E8F0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.operator}</span>
              <span style={{ fontSize: '1.5rem', fontWeight: 900, color: '#00D2FF', fontVariantNumeric: 'tabular-nums' }}>{p.rate_lph.toLocaleString()} L/h</span>
              <div style={{ gridColumn: '2 / 4', height: 6, borderRadius: 3, background: '#16213A', overflow: 'hidden', marginTop: -4 }}>
                <i style={{ display: 'block', height: '100%', width: `${top > 0 ? (p.rate_lph / top) * 100 : 0}%`, background: 'linear-gradient(90deg, #0891B2, #00D2FF)' }} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function PackingBreakdownCard({ rows }: { rows: PackingBreakdownRow[] }) {
  return (
    <div style={{ ...cardStyle, borderColor: '#A855F7' }}>
      <div style={{ ...labelStyle, marginBottom: 12, textAlign: 'left', color: '#A855F7' }}>📦 PACKING BREAKDOWN</div>
      <div style={{ textAlign: 'left', marginTop: 4 }}>
        {rows.length === 0 ? (
          <div style={{ color: '#64748B', padding: '18px 0', textAlign: 'center' }}>Nothing packed on this shift yet.</div>
        ) : (
          rows.map((r) => (
            <div key={`${r.resin}-${r.lot_number}`} style={{ marginBottom: 8, borderBottom: '1px solid #16213A', paddingBottom: 6, overflow: 'hidden' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 12, height: 12, borderRadius: '50%', background: r.color, display: 'inline-block' }} />
                <span style={{ fontWeight: 700, color: '#E2E8F0', fontSize: '1.1rem' }}>{r.resin}</span>
              </span>{' '}
              <span style={{ color: '#94A3B8', fontSize: '0.8rem' }}>({r.lot_number})</span>
              <div style={{ float: 'right' }}>
                <span style={{ color: '#A855F7', fontWeight: 'bold', fontSize: '1.1rem' }}>{r.units.toLocaleString()} Units</span>{' '}
                <span style={{ color: '#64748B', fontSize: '0.9rem' }}>({r.skids.toFixed(1)} Skids)</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function WorkOrdersCard({ orders }: { orders: WorkOrderRow[] }) {
  return (
    <div style={cardStyle}>
      <div style={{ ...labelStyle, marginBottom: 12, textAlign: 'left' }}>⚙️ ACTIVE REACTOR WORK ORDERS</div>
      <div style={{ textAlign: 'left', marginTop: 4 }}>
        {orders.length === 0 ? (
          <div style={{ color: '#64748B', padding: '18px 0', textAlign: 'center' }}>No active Work Orders in progress.</div>
        ) : (
          orders.map((run, i) => (
            <div key={i} style={{ marginBottom: 4, marginTop: 8 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 12, height: 12, borderRadius: '50%', background: run.color, display: 'inline-block' }} />
                <span style={{ fontWeight: 700, color: '#E2E8F0' }}>{run.resin_type}</span>
              </span>
              {' '}|{' '}<span style={{ color: '#94A3B8' }}>{run.pump_station}</span>
              <span style={{ float: 'right', color: '#00D2FF', fontWeight: 'bold' }}>
                {run.current_units.toLocaleString()} / {run.target_units.toLocaleString()}
              </span>
              <div style={{ marginTop: 4 }}>
                <LayerBar pct={run.progress_pct} heightPx={16} />
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Plant Command wall display, ported from pages/Tv_Dashboard.py. Polls every
// 10 seconds (the original's own refresh cadence, via time.sleep(10) +
// st.rerun()) - refetchInterval is the direct replacement.
export function TvDashboardPage() {
  const [mode, setMode] = useState<'auto' | 'daily'>('auto')
  const now = useLiveClock()
  const [sweepDone, setSweepDone] = useState(false)
  useEffect(() => { const t = setTimeout(() => setSweepDone(true), 2500); return () => clearTimeout(t) }, [])

  const query = useQuery({
    queryKey: ['tv-overview', mode],
    queryFn: () => tvApi.overview(mode),
    refetchInterval: 10_000,
  })
  const data = query.data

  const todayKey = now.toISOString().slice(0, 10)
  const finaleKey = `${todayKey}::${data?.active_shift ?? ''}`
  const buildFinaleNow = useBuildFinale(!!data && data.shift_target_l > 0 && data.build_pct >= 99.95, finaleKey)

  if (!data) return <p className="p-6 text-center text-sm text-[#94A3B8]">Loading Plant Command...</p>

  const gap = data.current_output_l - data.expected_now_l
  let paceColor = '#94A3B8', paceWord = 'not started'
  if (data.expected_now_l <= 0) {
    paceColor = '#94A3B8'; paceWord = 'not started'
  } else if (gap >= 0) {
    paceColor = '#10B981'; paceWord = `${gap.toLocaleString(undefined, { maximumFractionDigits: 0 })} L ahead`
  } else if (data.current_output_l >= data.expected_now_l * 0.9) {
    paceColor = '#F59E0B'; paceWord = `${Math.abs(gap).toLocaleString(undefined, { maximumFractionDigits: 0 })} L behind`
  } else {
    paceColor = '#EF4444'; paceWord = `${Math.abs(gap).toLocaleString(undefined, { maximumFractionDigits: 0 })} L behind`
  }
  const pacePct = data.expected_now_l > 0 ? Math.min(100, (data.current_output_l / data.expected_now_l) * 100) : 0

  const kpiCols = data.packing_enabled ? '1.7fr 1.2fr 1.2fr 0.8fr' : '2.6fr 0.8fr'
  const showBreakdown = data.packing_enabled || data.show_runs_card || true
  const breakdownCols = data.packing_enabled && data.show_runs_card ? '1.1fr 1.5fr 1.5fr'
    : data.packing_enabled || data.show_runs_card ? '1fr 1fr' : '1fr'

  return (
    <div style={{ background: '#050914', color: '#E2E8F0', minHeight: '100svh', padding: '16px 20px 4px' }}>
      {!sweepDone && <ScreenSweep />}

      {data.health.is_alarm && (
        <div style={{ background: '#7F1D1D', border: '3px solid #EF4444', borderRadius: 10, padding: '14px 20px', marginBottom: 16, textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', fontWeight: 900, color: '#FFFFFF', letterSpacing: '0.04em' }}>⚠ NOTHING IS BEING LOGGED</div>
          <div style={{ fontSize: '1.1rem', color: '#FECACA', marginTop: 4 }}>{data.health.message}</div>
        </div>
      )}
      {!data.health.is_alarm && data.health.state === 'quiet' && (
        <div style={{ background: '#78350F', border: '2px solid #F59E0B', borderRadius: 10, padding: '10px 18px', marginBottom: 14, textAlign: 'center', fontSize: '1.3rem', fontWeight: 800, color: '#FDE68A' }}>
          {data.health.message}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between', alignItems: 'center', fontSize: 'clamp(1.3rem, 3.4vw, 2.2rem)', fontWeight: 900, color: '#FFFFFF', borderBottom: '2px solid #1E2B45', paddingBottom: 10, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          <img src="/formlabs_logo.png" style={{ height: 50, objectFit: 'contain' }} alt="" />
          <span>LIVE PLANT COMMAND</span>
        </div>
        <span style={{ color: '#10B981', fontSize: '1.5rem' }}>
          ● {data.active_shift.toUpperCase()} ACTIVE &nbsp;|&nbsp; {now.toLocaleTimeString()}
        </span>
      </div>

      {buildFinaleNow && <BuildFinale doneUnits={data.current_output_l} targetUnits={data.shift_target_l} unit="L" />}

      <div style={{ marginBottom: 16 }}>
        <label style={{ marginRight: 16, cursor: 'pointer' }}>
          <input type="radio" checked={mode === 'auto'} onChange={() => setMode('auto')} /> 🟢 Auto-Detect Active Shift
        </label>
        <label style={{ cursor: 'pointer' }}>
          <input type="radio" checked={mode === 'daily'} onChange={() => setMode('daily')} /> 🏭 Full Plant Daily Total
        </label>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: kpiCols, gap: 16 }}>
        <div style={{ ...cardStyle, padding: 15 }}>
          <div style={{ ...labelStyle, textAlign: 'left' }}>💧 TOTAL VOLUME POURED</div>
          <div style={{ fontSize: '3rem', fontWeight: 900, color: '#FFFFFF', lineHeight: 1.1, marginTop: 10, marginBottom: 10, textAlign: 'left' }}>
            <Odometer value={data.current_output_l} uid="vol" /> <span style={{ fontSize: '1.2rem', color: '#94A3B8' }}>Liters</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold', letterSpacing: '0.1em' }}>PACE</div>
              <div style={{ fontSize: '2.1rem', fontWeight: 900, fontVariantNumeric: 'tabular-nums', color: paceColor }}>
                {data.current_run_rate_lph.toLocaleString()} <span style={{ fontSize: '1rem', color: '#94A3B8', fontWeight: 'bold' }}>L/h</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold', letterSpacing: '0.1em' }}>
                TARGET {data.target_lph.toLocaleString()} L/H{!data.pace_derived ? ' · SET' : ` · ${data.pace_station_count} PUMP${data.pace_station_count !== 1 ? 'S' : ''}`}
              </div>
              <div style={{ color: paceColor, fontSize: '1.35rem', fontWeight: 900 }}>{paceWord}</div>
            </div>
          </div>
          <div style={{ marginTop: 10 }}><LayerBar pct={pacePct} /></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #1E2B45', marginTop: 12, paddingTop: 12 }}>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold', letterSpacing: '0.1em' }}>EXPECTED NOW</div>
              <div style={{ color: '#00D2FF', fontSize: '1.2rem', fontWeight: 'bold' }}>{data.expected_now_l.toLocaleString()} L</div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 'bold', letterSpacing: '0.1em' }}>PROJECTED TOTAL</div>
              <div style={{ color: '#A855F7', fontSize: '1.2rem', fontWeight: 'bold' }}>{data.projected_total_l.toLocaleString()} L</div>
            </div>
          </div>
        </div>

        {data.packing_enabled && (
          <div style={{ ...cardStyle, borderColor: '#A855F7' }}>
            <div style={{ ...labelStyle, color: '#A855F7' }}>📦 TOTAL UNITS PACKED</div>
            <div style={{ fontSize: '3.5rem', fontWeight: 900, color: '#A855F7', lineHeight: 1.1, marginTop: 10 }}>
              <Odometer value={data.scope_packed} uid="pack" /> <span style={{ fontSize: '1.5rem', color: '#94A3B8' }}>Units</span>
            </div>
            <div style={{ color: '#A855F7', fontSize: '1.2rem', fontWeight: 'bold', marginTop: 20 }}>
              Est. Skids Built: {(data.scope_packed / 500).toLocaleString(undefined, { maximumFractionDigits: 1 })}
            </div>
          </div>
        )}

        {data.packing_enabled && (
          <div style={{ ...cardStyle, borderColor: '#F59E0B' }}>
            <div style={{ ...labelStyle, color: '#F59E0B' }}>⚠️ UNPACKED FLOOR W.I.P.</div>
            <div style={{ fontSize: '3.5rem', fontWeight: 900, color: '#F59E0B', lineHeight: 1.1, marginTop: 10 }}>
              <Odometer value={data.unpacked_wip} uid="wip" /> <span style={{ fontSize: '1.5rem', color: '#94A3B8' }}>Pending</span>
            </div>
            <div style={{ color: '#94A3B8', fontSize: '1.2rem', fontWeight: 'bold', marginTop: 20 }}>Awaiting pack-out · whole day</div>
          </div>
        )}

        <div style={{ ...cardStyle, padding: '14px 10px' }}>
          <div style={{ ...labelStyle, textAlign: 'center' }}>🖨️ SHIFT BUILD</div>
          <CartridgeBuild
            pct={data.build_pct} imageSrc="/resin_cartridge.png" doneUnits={data.current_output_l}
            targetUnits={data.shift_target_l} unit="L" heightPx={232} finale={buildFinaleNow}
          />
        </div>
      </div>

      <div style={{ height: 16 }} />

      {showBreakdown && (
        <div style={{ display: 'grid', gridTemplateColumns: breakdownCols, gap: 16, paddingBottom: 20 }}>
          <TopPourersCard pourers={data.top_pourers} />
          {data.packing_enabled && <PackingBreakdownCard rows={data.packing_breakdown} />}
          {data.show_runs_card && <WorkOrdersCard orders={data.work_orders} />}
        </div>
      )}
    </div>
  )
}
