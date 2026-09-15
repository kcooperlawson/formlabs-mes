import { Children, type ReactNode } from 'react'
import { fl } from '../theme'
import type { TabKey } from '../ManagerShell'

function LaunchCard({
  label, onClick, disabled, caption,
}: { label: string; onClick: () => void; disabled?: boolean; caption?: string }) {
  return (
    <div>
      <button
        onClick={onClick}
        disabled={disabled}
        className={`${disabled ? 'cursor-not-allowed rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3 opacity-40' : fl.cardHover} w-full text-left text-sm font-semibold text-[var(--fl-ink)]`}
      >
        {label}
      </button>
      {caption && <p className={`mt-1 text-xs ${fl.muted}`}>{caption}</p>}
    </div>
  )
}

function Section({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="text-sm font-bold uppercase tracking-wide text-[var(--fl-body)]">{title}</h2>
        {caption && <p className={`text-xs ${fl.muted}`}>{caption}</p>}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/* A brief staggered entrance rather than every card just being
            there on first paint - cheap, and it reads as "this page was
            considered" without asking anyone to wait for it. toArray()
            rather than Children.map: a conditionally-omitted card (the
            admin one, when canAdminister is false) comes through as a
            literal `false` child, and map() would still wrap that in a
            real (if empty) div - a genuine, if invisible, grid cell where
            the card would have been. toArray() drops it before it can. */}
        {Children.toArray(children).map((child, i) => (
          <div key={i} style={{ animation: 'fl-fade-up 420ms cubic-bezier(0.22,0.61,0.36,1) both', animationDelay: `${i * 45}ms` }}>
            {child}
          </div>
        ))}
      </div>
    </div>
  )
}

// Manager_Cockpit.py's own launchpad, ported card-for-card: three grouped
// sections rather than a flat list, because that grouping IS the point of
// the page - "what was poured" needs no manager input at all, "the floor"
// is people, and "setup" is the stuff you configure once and forget. The
// original renders these as st.page_link rows; here they're buttons that
// switch this shell's own tab state instead, since every one of these
// destinations already lives inside this single-page app rather than as
// its own Streamlit page.
export function ManagerCockpitHub({
  onNavigate, ordersOn, canAdminister,
}: { onNavigate: (tab: TabKey) => void; ordersOn: boolean; canAdminister: boolean }) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-bold text-[var(--fl-ink)] sm:text-2xl">📊 Production Records</h1>
        <p className={`mt-1 text-sm ${fl.muted}`}>
          Everything here reads what the operators logged. Nothing on this page has to be filled in first.
        </p>
      </div>

      <Section title="📈 What was poured">
        <LaunchCard label="📈 Historical Production Trends" onClick={() => onNavigate('historical')} />
        <LaunchCard label="📊 Scrap & Yield Intelligence" onClick={() => onNavigate('scrap-intel')} />
        <LaunchCard label="🔒 Cartridge Lot Verification" onClick={() => onNavigate('lot-verification')} />
        <LaunchCard label="🧪 Batch History & QC Turnaround" onClick={() => onNavigate('batch-history')} />
        <LaunchCard label="📸 Cleanliness & Photo Audits" onClick={() => onNavigate('cleanliness')} />
        <LaunchCard label="☁️ Google Cloud Sheets Sync" onClick={() => onNavigate('google-sync')} />
      </Section>

      <Section title="👥 The floor">
        <LaunchCard label="👥 Floor Staff Roster" onClick={() => onNavigate('roster')} />
        <LaunchCard label="📋 Notes from the Floor" onClick={() => onNavigate('floor-comms')} />
        <a href="/tv" target="_blank" rel="noopener noreferrer" className={`${fl.cardHover} block text-sm font-semibold text-[var(--fl-ink)]`}>
          📺 Floor Display (TV Mode)
        </a>
      </Section>

      <Section title="⚙️ Setup — optional" caption="None of this is needed to log a pour. Set a piece up when you want the answer it gives you.">
        <LaunchCard
          label="🎯 Work Orders & Assigned Runs"
          onClick={() => onNavigate('assigned-runs')}
          disabled={!ordersOn}
          caption={!ordersOn ? 'Off while this plant runs as a logging system.' : undefined}
        />
        {canAdminister && (
          <LaunchCard
            label="🛡️ Accounts, Equipment & Settings"
            onClick={() => onNavigate('admin')}
            caption={!ordersOn ? 'Yours to run: PINs, pumps, resins, backups, and the mode above.' : undefined}
          />
        )}
        <LaunchCard label="⚖️ Master Resin Specifications" onClick={() => onNavigate('resin-canvas')} caption="Target fill weights, so an out-of-band pour flags itself." />
        <LaunchCard label="🗑️ Log Management & Cleanup" onClick={() => onNavigate('log-management')} />
      </Section>
    </div>
  )
}
