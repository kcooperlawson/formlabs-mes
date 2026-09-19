import { ChecklistStatus } from './ChecklistStatus'
import { fl } from '../theme'

// The manager's view of the same thing operators see about themselves: who
// has done their startup checklist and their photo audits, for any day.
export function CheckStatusPage() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={fl.heading}>🧾 Checklist &amp; Audit Status</h1>
        <p className={`text-xs ${fl.muted}`}>
          Every operator and pump worked on a day, and which of the four checks are on record for each — the
          startup checklist, the start-of-shift photo, a transfer check where somebody moved pumps, and the
          end-of-shift photo. Read from the rows the floor already produces, so it says what happened rather than
          what somebody remembered to tick. Pick any past date to see how a previous shift went.
        </p>
      </div>
      <ChecklistStatus />
    </div>
  )
}
