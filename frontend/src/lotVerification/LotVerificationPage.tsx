import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { lotVerificationApi, type LotCheck } from '../api/lotVerification'
import { fl } from '../theme'
import { Drill } from '../drill/DrillContext'

const tile = fl.tile
const card = fl.card
const WINDOWS = [7, 14, 30, 90] as const

const TONE: Record<string, string> = { mismatch: '#EF4444', expired: '#F59E0B', rejected: '#38BDF8' }
const HEADLINE: Record<string, string> = {
  mismatch: 'LOT MISMATCH — poured anyway',
  expired: 'EXPIRED LOT — poured anyway',
  rejected: 'CARTRIDGE PULLED — nothing poured',
}

function textColorFor(hex: string): string {
  const c = hex.replace('#', '')
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(c.slice(i, i + 2), 16) / 255)
  const lin = (v: number) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
  return lum < 0.45 ? '#FFFFFF' : '#111827'
}

function ResinChip({ name, color }: { name: string; color: string }) {
  return (
    <span
      className="inline-block rounded-full border px-2 py-0.5 text-xs font-semibold"
      style={{ backgroundColor: color, color: textColorFor(color), borderColor: color }}
    >
      {name}
    </span>
  )
}

function downloadCsv(checks: LotCheck[], days: number) {
  const header = ['When', 'Operator', 'Station', 'Format', 'Resin', 'Run lot', 'Cartridge lot',
    'Result', 'Level', 'Reason', 'Log #']
  const rows = checks.map((c) => [
    c.timestamp, c.operator_name, c.pump_station, c.cartridge_type, c.resin_type ?? '',
    c.expected_lot ?? '', c.entered_lot ?? '', c.result, c.check_level, c.reason ?? '',
    c.production_log_id ?? '',
  ])
  const csv = [header, ...rows]
    .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `lot_verifications_last_${days}_days.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// Cartridge Lot Verification, ported from pages/Mgr_Lot_Verification.py - the
// manager review of every check api/routers/pouring.py's lot gate logs.
export function LotVerificationPage() {
  const [days, setDays] = useState<(typeof WINDOWS)[number]>(30)
  const [tab, setTab] = useState<'flagged' | 'coverage' | 'all'>('flagged')
  const query = useQuery({ queryKey: ['lot-verification', days], queryFn: () => lotVerificationApi.get(days) })
  const data = query.data

  const flagged = data?.checks.filter((c) => ['mismatch', 'expired', 'rejected'].includes(c.result)) ?? []

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={fl.heading}>🔒 Cartridge Lot Verification</h1>
        <p className={`text-sm ${fl.muted}`}>
          Every lot check completed at a pouring station. The passes are what prove the check actually
          happened; the flags are the mix-ups this gate exists to catch.
        </p>
      </div>

      <select
        className={`${fl.select} w-40`}
        value={days}
        onChange={(e) => setDays(Number(e.target.value) as (typeof WINDOWS)[number])}
      >
        {WINDOWS.map((w) => (
          <option key={w} value={w}>Last {w} days</option>
        ))}
      </select>

      {!data || data.totals.checks_logged === 0 ? (
        <p className={`${card} py-6 text-center text-sm ${fl.muted}`}>
          No lot checks recorded in this window yet. Checks start appearing as soon as operators log
          pouring on V1, V2 or Pigment.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.checks_logged.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Checks logged</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.full_checks.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Full checks ({data.totals.pct_full.toFixed(0)}%)</p>
            </div>
            <div className={tile}>
              <p className={`text-lg font-semibold ${data.totals.flagged > 0 ? 'text-red-400' : 'text-white'}`}>
                {data.totals.flagged.toLocaleString()}
              </p>
              <p className={`text-xs ${fl.muted}`}>
                {data.totals.flagged > 0 ? 'Review needed' : 'All clear'}
              </p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.cartridges_pulled.toLocaleString()}</p>
              <p className={`text-xs ${fl.muted}`}>Cartridges pulled</p>
            </div>
            <div className={tile}>
              <p className="text-lg font-semibold text-white">{data.totals.flag_rate.toFixed(1)}%</p>
              <p className={`text-xs ${fl.muted}`}>Flag rate</p>
            </div>
          </div>

          <div className={fl.tabStrip}>
            {([
              ['flagged', '⛔ Flagged Checks'],
              ['coverage', '📊 Coverage by Operator'],
              ['all', '🗂️ Every Check'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={tab === key ? fl.tabActive : fl.tabInactive}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === 'flagged' && (
            flagged.length === 0 ? (
              <p className="rounded-lg border border-emerald-800 bg-emerald-950 p-3 text-sm text-emerald-300">
                ✅ No mismatched, expired or pulled cartridges in this window.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {flagged.map((c) => (
                  <div key={c.id} className={card} style={{ borderLeft: `4px solid ${TONE[c.result] ?? '#94A3B8'}` }}>
                    <div className="mb-1 flex items-center justify-between">
                      <b style={{ color: TONE[c.result] ?? '#94A3B8' }}>● {HEADLINE[c.result] ?? c.result.toUpperCase()}</b>
                      <span className={`text-xs ${fl.muted}`}>{new Date(c.timestamp).toLocaleString()}</span>
                    </div>
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-[#CBD5E1]">
                      <span><Drill f={{ operator: c.operator_name }}>{c.operator_name}</Drill> · <Drill f={{ pump: c.pump_station }}>{c.pump_station}</Drill> · {c.cartridge_type} ·</span>
                      {c.resin_type && c.resin_color ? (
                        <ResinChip name={c.resin_type} color={c.resin_color} />
                      ) : (
                        <span className={`text-xs ${fl.muted}`}>no resin recorded</span>
                      )}
                    </div>
                    <p className="text-sm text-[#F8FAFC]">
                      <b>Run expected:</b> <code>{c.expected_lot ? <Drill f={{ lot: c.expected_lot }}>{c.expected_lot}</Drill> : '—'}</code><br />
                      <b>Cartridge read:</b> <code>{c.entered_lot ? <Drill f={{ lot: c.entered_lot }}>{c.entered_lot}</Drill> : '—'}</code>
                    </p>
                    <p className="mt-1 text-sm italic text-[#CBD5E1]">
                      {c.reason || 'No reason recorded.'}
                    </p>
                    <p className={`mt-1 text-xs ${fl.muted}`}>
                      {c.production_log_id
                        ? `Production log #${c.production_log_id} carries this flag.`
                        : 'No production logged against this check — the container was pulled before pouring, which is the outcome this control is for.'}
                    </p>
                    {c.photo_filename && (
                      <img
                        src={lotVerificationApi.photoUrl(c.photo_filename)}
                        alt="Lot label as photographed"
                        className="mt-2 max-w-xs rounded-md"
                      />
                    )}
                  </div>
                ))}
              </div>
            )
          )}

          {tab === 'coverage' && (
            <div className="flex flex-col gap-4">
              <div className={card}>
                <p className="mb-2 text-sm font-semibold text-white">By operator</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className={fl.tableHead}>
                      <tr>
                        <th className="py-1 pr-2">Operator</th><th className="py-1 pr-2">Checks</th>
                        <th className="py-1 pr-2">Full</th><th className="py-1 pr-2">One-tap</th>
                        <th className="py-1 pr-2">Flagged</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_operator.map((o) => (
                        <tr key={o.operator_name} className={fl.tableRow}>
                          <td className="py-1 pr-2"><Drill f={{ operator: o.operator_name }}>{o.operator_name}</Drill></td>
                          <td className="py-1 pr-2">{o.checks}</td>
                          <td className="py-1 pr-2">{o.full}</td>
                          <td className="py-1 pr-2">{o.fast}</td>
                          <td className="py-1 pr-2">{o.flags}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className={card}>
                <p className="mb-2 text-sm font-semibold text-white">By station</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className={fl.tableHead}>
                      <tr><th className="py-1 pr-2">Station</th><th className="py-1 pr-2">Checks</th><th className="py-1 pr-2">Flagged</th></tr>
                    </thead>
                    <tbody>
                      {data.by_station.map((s) => (
                        <tr key={s.pump_station} className={fl.tableRow}>
                          <td className="py-1 pr-2"><Drill f={{ pump: s.pump_station }}>{s.pump_station}</Drill></td>
                          <td className="py-1 pr-2">{s.checks}</td>
                          <td className="py-1 pr-2">{s.flags}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {tab === 'all' && (
            <div className={card}>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-white">Every check</p>
                <button onClick={() => downloadCsv(data.checks, days)} className={fl.btnSecondary}>
                  ⬇️ Export this window as CSV
                </button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className={fl.tableHead}>
                    <tr>
                      <th className="py-1 pr-2">When</th><th className="py-1 pr-2">Operator</th>
                      <th className="py-1 pr-2">Station</th><th className="py-1 pr-2">Format</th>
                      <th className="py-1 pr-2">Resin</th><th className="py-1 pr-2">Run lot</th>
                      <th className="py-1 pr-2">Cartridge lot</th><th className="py-1 pr-2">Result</th>
                      <th className="py-1 pr-2">Level</th><th className="py-1 pr-2">Reason</th>
                      <th className="py-1 pr-2">Log #</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.checks.map((c) => (
                      <tr key={c.id} className={fl.tableRow}>
                        <td className="py-1 pr-2 whitespace-nowrap">{new Date(c.timestamp).toLocaleString()}</td>
                        <td className="py-1 pr-2"><Drill f={{ operator: c.operator_name }}>{c.operator_name}</Drill></td>
                        <td className="py-1 pr-2"><Drill f={{ pump: c.pump_station }}>{c.pump_station}</Drill></td>
                        <td className="py-1 pr-2">{c.cartridge_type}</td>
                        <td className="py-1 pr-2">
                          {c.resin_type && c.resin_color ? <ResinChip name={c.resin_type} color={c.resin_color} /> : '—'}
                        </td>
                        <td className="py-1 pr-2">{c.expected_lot ? <Drill f={{ lot: c.expected_lot }}>{c.expected_lot}</Drill> : '—'}</td>
                        <td className="py-1 pr-2">{c.entered_lot ? <Drill f={{ lot: c.entered_lot }}>{c.entered_lot}</Drill> : '—'}</td>
                        <td className="py-1 pr-2">{c.result}</td>
                        <td className="py-1 pr-2">{c.check_level}</td>
                        <td className="py-1 pr-2">{c.reason ?? ''}</td>
                        <td className="py-1 pr-2">{c.production_log_id ?? ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
