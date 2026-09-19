import { ClipboardCheck,
  Camera, Cloud, ClipboardList, Droplets, LayoutDashboard, Lock, PieChart, Scale, Settings,
  Shield, Target, Trash2, TrendingUp, Tv, Users, FlaskConical, type LucideIcon,
} from 'lucide-react'
import { Children, type ReactNode } from 'react'
import { fl } from '../theme'
import type { TabKey } from '../ManagerShell'

function LaunchCard({
  label, icon: Icon, onClick, disabled, caption,
}: { label: string; icon: LucideIcon; onClick: () => void; disabled?: boolean; caption?: string }) {
  return (
    <div>
      <button
        onClick={onClick}
        disabled={disabled}
        className={`${disabled ? 'cursor-not-allowed rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3 opacity-40' : fl.cardHover} flex w-full items-center gap-2.5 text-left text-sm font-semibold text-[var(--fl-ink)]`}
      >
        <Icon size={17} className="shrink-0 text-[var(--fl-accent-2)]" strokeWidth={2.25} />
        {label}
      </button>
      {caption && <p className={`mt-1 text-xs ${fl.muted}`}>{caption}</p>}
    </div>
  )
}

function Section({ title, icon: Icon, caption, children }: { title: string; icon: LucideIcon; caption?: string; children: ReactNode }) {
  // A card dropped by canSee()/canAdminister comes through as a literal
  // `false` child - toArray() strips those before this ever counts them, so
  // a section left with nothing a person can actually open doesn't draw its
  // own heading over an empty grid; it just isn't there; see the note below
  // on why toArray() rather than Children.map() in the first place.
  const cards = Children.toArray(children)
  if (cards.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h2 className="flex items-center gap-1.5 text-sm font-bold uppercase tracking-wide text-[var(--fl-body)]">
          <Icon size={15} className="shrink-0" /> {title}
        </h2>
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
        {cards.map((child, i) => (
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
  onNavigate, ordersOn, canAdminister, canSee, isManagement,
}: {
  onNavigate: (tab: TabKey) => void
  ordersOn: boolean
  canAdminister: boolean
  /** Same question ManagerShell's own sidebar asks per tab (see
   * canSeeManagerTab) - a card whose door doesn't open for this person
   * isn't drawn at all, rather than sitting there disabled or 403ing the
   * moment it's clicked. */
  canSee: (tab: TabKey) => boolean
  /** TV Mode has no ability of its own to grant - App.tsx's own /tv route
   * is plain role === manager/admin, so this mirrors that exactly rather
   * than needing an entry in ManagerShell's TAB_ABILITY map for a door
   * nothing can ever be granted into. */
  isManagement: boolean
}) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold text-[var(--fl-ink)] sm:text-2xl">
          <LayoutDashboard size={22} className="shrink-0" /> Production Records
        </h1>
        <p className={`mt-1 text-sm ${fl.muted}`}>
          Everything here reads what the operators logged. Nothing on this page has to be filled in first.
        </p>
      </div>

      <Section title="What was poured" icon={Droplets}>
        {canSee('historical') && <LaunchCard label="Historical Production Trends" icon={TrendingUp} onClick={() => onNavigate('historical')} />}
        {canSee('scrap-intel') && <LaunchCard label="Scrap & Yield Intelligence" icon={PieChart} onClick={() => onNavigate('scrap-intel')} />}
        {canSee('lot-verification') && <LaunchCard label="Cartridge Lot Verification" icon={Lock} onClick={() => onNavigate('lot-verification')} />}
        {canSee('batch-history') && <LaunchCard label="Batch History & QC Turnaround" icon={FlaskConical} onClick={() => onNavigate('batch-history')} />}
        {canSee('cleanliness') && <LaunchCard label="Cleanliness & Photo Audits" icon={Camera} onClick={() => onNavigate('cleanliness')} />}
        {canSee('checks') && <LaunchCard label="Checklist & Audit Status" icon={ClipboardCheck} onClick={() => onNavigate('checks')} />}
        {canSee('google-sync') && <LaunchCard label="Google Cloud Sheets Sync" icon={Cloud} onClick={() => onNavigate('google-sync')} />}
      </Section>

      <Section title="The floor" icon={Users}>
        {canSee('roster') && <LaunchCard label="Floor Staff Roster" icon={Users} onClick={() => onNavigate('roster')} />}
        {canSee('floor-comms') && <LaunchCard label="Notes from the Floor" icon={ClipboardList} onClick={() => onNavigate('floor-comms')} />}
        {isManagement && (
          <a href="/tv" target="_blank" rel="noopener noreferrer" className={`${fl.cardHover} flex items-center gap-2.5 text-sm font-semibold text-[var(--fl-ink)]`}>
            <Tv size={17} className="shrink-0 text-[var(--fl-accent-2)]" strokeWidth={2.25} /> Floor Display (TV Mode)
          </a>
        )}
      </Section>

      <Section title="Setup — optional" icon={Settings} caption="None of this is needed to log a pour. Set a piece up when you want the answer it gives you.">
        {canSee('assigned-runs') && (
          <LaunchCard
            label="Work Orders & Assigned Runs"
            icon={Target}
            onClick={() => onNavigate('assigned-runs')}
            disabled={!ordersOn}
            caption={!ordersOn ? 'Off while this plant runs as a logging system.' : undefined}
          />
        )}
        {canAdminister && (
          <LaunchCard
            label="Accounts, Equipment & Settings"
            icon={Shield}
            onClick={() => onNavigate('admin')}
            caption={!ordersOn ? 'Yours to run: PINs, pumps, resins, backups, and the mode above.' : undefined}
          />
        )}
        {canSee('resin-canvas') && (
          <LaunchCard label="Master Resin Specifications" icon={Scale} onClick={() => onNavigate('resin-canvas')} caption="Target fill weights, so an out-of-band pour flags itself." />
        )}
        {canSee('log-management') && <LaunchCard label="Log Management & Cleanup" icon={Trash2} onClick={() => onNavigate('log-management')} />}
      </Section>
    </div>
  )
}
