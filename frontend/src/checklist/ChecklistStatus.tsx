import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { checklistApi, type ComplianceRow } from '../api/checklist'
import { useDebugOperator } from '../operatorForm/DebugOperatorContext'
import { fl } from '../theme'

// Whether the checks actually got done - startup checklist, the start-of-shift
// photo, a transfer check when somebody moved pumps, and the end-of-shift
// photo - for a day.
//
// Nothing here is a new thing to fill in. Every column is read from rows the
// floor already produces, which is what makes it a record of what happened
// rather than a second checklist about the first one. An operator sees their
// own; a manager sees everyone's, from the same endpoint.

function today(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function Mark({ at, expected }: { at: string | null; expected?: boolean }) {
  if (at) {
    const when = new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return <span className="whitespace-nowrap text-emerald-400" title={when}>✓ {when}</span>
  }
  if (expected === false) return <span className={`text-xs ${fl.muted}`}>—</span>
  return <span className="whitespace-nowrap text-amber-400">✗ not done</span>
}

export function ChecklistStatus({ compact = false }: { compact?: boolean }) {
  const asOperator = useDebugOperator()
  const [day, setDay] = useState(today())
  const query = useQuery({
    queryKey: ['checklist', 'compliance', day, asOperator],
    queryFn: () => checklistApi.compliance(day, asOperator),
    refetchInterval: 60_000,
  })

  const rows: ComplianceRow[] = query.data?.rows ?? []
  const outstanding = rows.filter((r) => !r.complete)
  const isToday = day === today()

  return (
    <div className={fl.card}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">
          🧾 Checks {query.data?.scope === 'everyone' ? '— everyone' : '— yours'}
        </p>
        <div className="flex items-center gap-2">
          {/* The history: any past day, not just today. */}
          <input
            className={`${fl.input} w-40`}
            type="date"
            value={day}
            max={today()}
            onChange={(e) => setDay(e.target.value || today())}
          />
          {!isToday && (
            <button className={fl.btnSecondary} onClick={() => setDay(today())}>Today</button>
          )}
        </div>
      </div>

      {query.isLoading && <p className={`text-sm ${fl.muted}`}>Looking…</p>}
      {query.isError && <p className="text-sm text-red-400">{(query.error as Error).message}</p>}

      {query.isSuccess && rows.length === 0 && (
        <p className={`text-sm ${fl.muted}`}>
          Nothing recorded for {isToday ? 'today' : day} yet.
        </p>
      )}

      {rows.length > 0 && (
        <>
          <p className={`mb-2 text-xs ${outstanding.length ? 'text-amber-400' : 'text-emerald-400'}`}>
            {outstanding.length
              ? `${outstanding.length} of ${rows.length} still outstanding`
              : `All ${rows.length} complete`}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className={fl.tableHead}>
                <tr>
                  {query.data?.scope === 'everyone' && <th className="py-1 pr-2">Operator</th>}
                  <th className="py-1 pr-2">Pump</th>
                  {!compact && <th className="py-1 pr-2">Shift</th>}
                  <th className="py-1 pr-2">Startup</th>
                  <th className="py-1 pr-2">Start photo</th>
                  <th className="py-1 pr-2">Transfer</th>
                  <th className="py-1 pr-2">End of shift</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={`${row.operator_name}|${row.pump_station}|${row.shift}`} className={fl.tableRow}>
                    {query.data?.scope === 'everyone' && (
                      <td className="py-1 pr-2 whitespace-nowrap text-[var(--fl-ink)]">{row.operator_name}</td>
                    )}
                    <td className="py-1 pr-2 whitespace-nowrap text-[var(--fl-ink)]">
                      {row.pump_station}
                      {row.poured > 0 && <span className={`ml-1 ${fl.muted}`}>· {row.poured} logs</span>}
                    </td>
                    {!compact && <td className={`py-1 pr-2 whitespace-nowrap ${fl.muted}`}>{row.shift}</td>}
                    <td className="py-1 pr-2"><Mark at={row.checklist_at} /></td>
                    <td className="py-1 pr-2"><Mark at={row.start_audit_at} expected={row.start_expected} /></td>
                    <td className="py-1 pr-2"><Mark at={row.transfer_audit_at} expected={row.transfer_expected} /></td>
                    <td className="py-1 pr-2"><Mark at={row.end_audit_at} expected={row.end_expected} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={`mt-2 text-xs ${fl.muted}`}>
            A dash means that check isn't expected on this row — the start-of-shift photo belongs to the pump
            the shift began on, a transfer check to a pump somebody moved to, and the end-of-shift photo to the
            last pump they worked.
          </p>
        </>
      )}
    </div>
  )
}
