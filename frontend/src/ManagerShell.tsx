import { useQuery } from '@tanstack/react-query'
import {
  Activity, ArrowLeft, BarChart3, BookOpen, ClipboardEdit, Compass, FlaskConical, PanelLeftClose,
  Plug, Settings, ShieldCheck, Tv, User, type LucideIcon,
} from 'lucide-react'
import { useLayoutEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { AdminPanelPage } from './adminPanel/AdminPanelPage'
import { AnalyticsHubPage } from './analyticsHub/AnalyticsHubPage'
import { accountApi } from './api/account'
import { referenceApi } from './api/reference'
import { AssignedRunsPage } from './assignedRuns/AssignedRunsPage'
import { useAuth } from './auth/AuthProvider'
import { brandTitle } from './brandTitle'
import { paletteByName } from './palettes'
import { fl } from './theme'
import { AccountPanel } from './shell/AccountPanel'
import { ManagerCockpitHub } from './shell/ManagerCockpitHub'
import { ThemeFlourish } from './shell/ThemeFlourish'
import { UpdateBanner } from './shell/UpdateBanner'
import { BatchHistoryPage } from './batchHistory/BatchHistoryPage'
import { CheckStatusPage } from './checklist/CheckStatusPage'
import { CleanlinessGalleryPage } from './cleanliness/CleanlinessGalleryPage'
import { DeviceRegistryPage } from './deviceRegistry/DeviceRegistryPage'
import { GoogleSyncPage } from './googleSync/GoogleSyncPage'
import { HistoricalPage } from './historical/HistoricalPage'
import { LogManagementPage } from './logManagement/LogManagementPage'
import { LotVerificationPage } from './lotVerification/LotVerificationPage'
import { ReactorFleetPage } from './reactors/ReactorFleetPage'
import { ResinCanvasPage } from './resinCanvas/ResinCanvasPage'
import { RosterPage } from './roster/RosterPage'
import { FloorCommsPage } from './scada/FloorCommsPage'
import { ScadaPage } from './scada/ScadaPage'
import { ScrapIntelPage } from './scrap/ScrapIntelPage'

export type TabKey = 'cockpit' | 'scada' | 'reactors' | 'floor-comms' | 'cleanliness' | 'checks' | 'roster' | 'scrap-intel' | 'lot-verification' | 'batch-history' | 'historical' | 'resin-canvas' | 'assigned-runs' | 'log-management' | 'google-sync' | 'analytics' | 'admin' | 'devices'

// Which tab - top-level sidebar item, or launchpad card inside 'cockpit' -
// a granted ability (IT Admin > Users, crud.ABILITIES) actually unlocks.
// Every entry here matches the exact require_ability(...) call its own
// endpoint enforces (checked against every api/routers/*.py file directly,
// not just the ABILITIES catalog's own summary text) - this list existing
// separately from the backend is exactly the risk the backend can't cover
// by itself: a card drawn for someone who can't open what it links to isn't
// a security hole (every route still checks for itself), but it is a false
// promise, and the whole reason this exists is so a person only sees doors
// that actually open. 'admin' and 'devices' stay purely role-gated below
// (canAdminister/canSeeDeviceGateway already mirror database.py's own
// role_can_administer exactly, and there is no ability that hands out IT
// Admin). 'reactors' rides on view_scada rather than a tab of its own - see
// api/routers/reactors.py's fleet(): "the whole plant at once" already
// covers the reactor wall, and a second ability for the same door would
// just be two switches for one light.
const TAB_ABILITY: Partial<Record<TabKey, string>> = {
  cockpit: 'view_manager_cockpit',
  scada: 'view_scada',
  reactors: 'view_scada',
  analytics: 'view_analytics',
  historical: 'view_manager_cockpit',
  'scrap-intel': 'view_manager_cockpit',
  'lot-verification': 'view_manager_cockpit',
  'batch-history': 'view_manager_cockpit',
  cleanliness: 'view_manager_cockpit',
  checks: 'view_manager_cockpit',
  'floor-comms': 'view_manager_cockpit',
  'assigned-runs': 'view_manager_cockpit',
  'google-sync': 'export_data',
  roster: 'manage_people',
  'resin-canvas': 'manage_resins',
  'log-management': 'manage_logs',
}

interface AbilityUser {
  role: string
  abilities: string[]
}

// A manager/admin already holds every ability their role grants (see
// crud.ROLE_ABILITIES) - checked by role here too, rather than requiring
// their /me abilities list to be fully populated, so this reads the same
// the instant they sign in as it does after a refresh.
export function canSeeManagerTab(user: AbilityUser | null | undefined, key: TabKey): boolean {
  if (!user) return false
  if (user.role === 'manager' || user.role === 'admin') return true
  const needs = TAB_ABILITY[key]
  return !!needs && user.abilities.includes(needs)
}

// Answers "does this person have anywhere to go in here at all" - what
// OperatorFormPage's own "Manager Cockpit" button asks before it draws
// itself, so an operator with no grants at all still sees exactly the
// screen they saw before any of this existed.
export function hasAnyManagerAbility(user: AbilityUser | null | undefined): boolean {
  if (!user) return false
  if (user.role === 'manager' || user.role === 'admin') return true
  return (Object.keys(TAB_ABILITY) as TabKey[]).some((key) => canSeeManagerTab(user, key))
}

// The manager/admin shell. Ported from ui_shell.py's render_shell(): a
// persistent left sidebar carries identity, the top-level nav_menu, the
// handbook link, the account popover and sign-out - the same content, in
// the same order, as the Streamlit sidebar every manager/admin page shared.
// The old horizontal 16-tab strip that lived here is gone; those
// destinations now split the way the original app actually split them.
// Live SCADA / Reactor Fleet / Analytics / Admin / Devices are top-level
// sections (nav_menu's own links), while everything Manager_Cockpit.py used
// to hand out from its own launchpad - Historical, Scrap Intel, Roster,
// Assigned Runs and the rest - now lives one click away on the "Manager
// Cockpit" tab, which is also this shell's default/home view.
// A pill that slides between nav items instead of the active state just
// snapping from one button to the next - its own component (not inline in
// sidebarContent below) because sidebarContent is rendered TWICE at once
// (the desktop <aside> and the mobile drawer both mount it, one hidden by
// CSS rather than unmounted) - a plain ref map at the ManagerShell level
// would have the two copies fighting over the same keys. As its own
// component, each mount gets its own refs and measures its own layout.
function SidebarNav({
  items, activeKey, onSelect,
}: { items: { key: TabKey; label: string; icon: LucideIcon }[]; activeKey: TabKey; onSelect: (key: TabKey) => void }) {
  const itemRefs = useRef<Partial<Record<TabKey, HTMLButtonElement>>>({})
  const [highlight, setHighlight] = useState<{ top: number; height: number } | null>(null)

  useLayoutEffect(() => {
    const el = itemRefs.current[activeKey]
    if (el) setHighlight({ top: el.offsetTop, height: el.offsetHeight })
  }, [activeKey, items.length])

  return (
    <div className="relative flex flex-col gap-1">
      {highlight && (
        <div
          className="absolute inset-x-0 rounded-md border-l-4 border-l-[var(--fl-accent)] bg-[var(--fl-raised)]"
          style={{
            top: highlight.top, height: highlight.height,
            transition: 'top 260ms cubic-bezier(0.22,0.61,0.36,1), height 260ms cubic-bezier(0.22,0.61,0.36,1)',
          }}
        />
      )}
      {items.map((item) => (
        <button
          key={item.key}
          ref={(el) => { itemRefs.current[item.key] = el ?? undefined }}
          onClick={() => onSelect(item.key)}
          className={`relative flex items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition ${
            activeKey === item.key
              ? 'font-bold text-[var(--fl-ink)]'
              : `font-semibold text-[var(--fl-body)] hover:bg-[var(--fl-overlay-weak)] hover:text-[var(--fl-ink)]`
          }`}
        >
          <item.icon size={16} className="shrink-0" strokeWidth={2.25} />
          {item.label}
        </button>
      ))}
    </div>
  )
}

function loadCollapsed(): boolean {
  try {
    return localStorage.getItem('mes_sidebar_collapsed') === '1'
  } catch {
    return false
  }
}

// Object.keys() preserves insertion order for string keys - TAB_ABILITY
// lists 'cockpit' first for exactly this reason, so this tries the natural
// home first and only falls through the rest in the same order the
// sidebar/launchpad would draw them.
const FALLBACK_TAB_ORDER = Object.keys(TAB_ABILITY) as TabKey[]

export function ManagerShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  // 'cockpit' is the right default for a manager/admin (canSeeManagerTab is
  // true for everything unconditionally), but an operator or packer who
  // only holds, say, manage_people has no business landing on a cockpit tab
  // whose own launchpad they can't yet see anything useful behind if this
  // fell back to 'cockpit' blindly - land them on the first tab (sidebar
  // item or launchpad card alike) they actually have instead.
  const [tab, setTab] = useState<TabKey>(() => FALLBACK_TAB_ORDER.find((key) => canSeeManagerTab(user, key)) ?? 'cockpit')
  const [showAccount, setShowAccount] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(loadCollapsed)
  const versionQuery = useQuery({ queryKey: ['reference', 'app-version'], queryFn: referenceApi.appVersion, staleTime: Infinity })

  function toggleCollapsed() {
    setCollapsed((v) => {
      const next = !v
      try {
        localStorage.setItem('mes_sidebar_collapsed', next ? '1' : '0')
      } catch {
        /* a private window or blocked storage just means it won't be remembered next time */
      }
      return next
    })
  }

  const settingsQuery = useQuery({ queryKey: ['reference', 'plant-settings'], queryFn: referenceApi.plantSettings })
  const simpleMode = settingsQuery.data?.simple_mode ?? true
  const ordersOn = !simpleMode
  // Mirrors database.py's role_can_administer: admin always administers; a
  // manager only does while this plant runs in simple/logging mode. Getting
  // this wrong is what used to leave "Admin Console" offered to a manager
  // in execution mode - a link that opened to a page whose every API call
  // then came back 403, rather than the link simply not being there.
  const canAdminister = user?.role === 'admin' || (simpleMode && user?.role === 'manager')
  const canSeeDeviceGateway = canAdminister && (settingsQuery.data?.enable_device_gateway ?? false)

  const coreNavItems: { key: TabKey; label: string; icon: LucideIcon }[] = [
    { key: 'cockpit', label: 'Manager Cockpit', icon: Compass },
    { key: 'scada', label: 'Live SCADA', icon: Activity },
    { key: 'reactors', label: 'Live Reactors', icon: FlaskConical },
    { key: 'analytics', label: 'Analytics Hub', icon: BarChart3 },
  ]
  const navItems: { key: TabKey; label: string; icon: LucideIcon }[] = coreNavItems
    .filter((item) => canSeeManagerTab(user, item.key))
    .concat(
      canAdminister ? [{ key: 'admin', label: 'IT Admin', icon: ShieldCheck }] : [],
      canSeeDeviceGateway ? [{ key: 'devices', label: 'Device Gateway', icon: Plug }] : [],
    )

  function go(next: TabKey) {
    setTab(next)
    setDrawerOpen(false)
  }

  const sidebarContent = (
    <>
      {/* Collapse arrow, ported from Streamlit's own native sidebar control -
          desktop only, since the mobile drawer already has its own
          open/close affordance (the ☰ button in the top header). The logo
          lives in that top header now, not here, so it isn't shown twice. */}
      <button
        onClick={toggleCollapsed}
        title="Collapse sidebar"
        className="hidden h-7 w-7 items-center justify-center self-end rounded text-[var(--fl-muted)] hover:bg-[var(--fl-overlay-weak)] hover:text-[var(--fl-ink)] md:flex"
      >
        <PanelLeftClose size={16} />
      </button>

      <div className="flex items-center gap-3">
        {user?.avatar_filename ? (
          <img src={accountApi.avatarUrl(user.avatar_filename)} alt="" className="h-11 w-11 rounded-full object-cover" />
        ) : (
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-[var(--fl-ground)] text-[var(--fl-muted)]">
            <User size={20} />
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate font-bold text-[var(--fl-ink)]">{user?.full_name}</p>
          <p className={`text-xs ${fl.muted}`}>
            <span className={fl.badge}>{user?.role}</span>
            {user?.shift && <span className="ml-1.5">Shift: {user.shift}</span>}
          </p>
        </div>
      </div>

      <hr className={fl.divider} />

      <nav className="flex flex-col gap-1">
        <p className={`px-3 pb-1 ${fl.label}`}>Navigation</p>
        <SidebarNav items={navItems} activeKey={tab} onSelect={go} />
        {/* A real route, not a tab - mirrors ui_shell.py's nav_links(),
            which offers every role the Operator Form/Workstation
            unconditionally. A manager/admin lands there with Debug Mode
            available to test or log on an operator's behalf. */}
        <button onClick={() => navigate('/operator-form')} className={`${fl.navItem} flex items-center gap-2.5`}>
          <ClipboardEdit size={16} className="shrink-0" strokeWidth={2.25} /> Operator Form
        </button>
      </nav>

      {/* The Operations Handbook is written for managers - an operator or
          packer landing in this shell on a granted ability alone (see the
          canSeeManagerTab gating above) gets their own Operator Guide from
          OperatorFormPage instead, not this one. Same gate as Launch TV
          Mode below: real role, not an ability, since there's nothing to
          grant into a document. */}
      {(user?.role === 'manager' || user?.role === 'admin') && (
        <a
          href="/Formlabs_MES_Handbook.pdf" target="_blank" rel="noopener noreferrer"
          className={`flex items-center gap-1.5 px-3 text-xs ${fl.muted} hover:text-[var(--fl-accent-2)]`}
        >
          <BookOpen size={13} className="shrink-0" /> Operations handbook (PDF)
        </a>
      )}

      <hr className={fl.divider} />

      <div className="flex flex-col gap-2">
        {/* Just the trigger here - sidebarContent mounts twice at once (the
            drawer and the desktop aside, one hidden by CSS rather than
            unmounted, see this file's own note above SidebarNav), and
            AccountPanel closes itself on any click its own ref doesn't
            contain. Two mounted copies meant the display:none one saw
            every click inside the VISIBLE copy as "outside" and closed
            both - the panel vanishing the instant a tab inside it was
            clicked. AccountPanel itself renders once, below, outside
            sidebarContent, so there is only ever one instance and one
            listener regardless of which trigger was pressed. */}
        <button onClick={() => setShowAccount((v) => !v)} className={`${fl.btnSecondary} w-full flex items-center justify-center gap-2`}>
          <Settings size={15} /> Account & Preferences
        </button>
        {/* /tv itself is plain role === manager/admin (App.tsx), not an
            ability - nothing to grant into it, so this matches that
            exactly rather than drawing a link that bounces straight back
            for anyone here on a granted ability alone. */}
        {(user?.role === 'manager' || user?.role === 'admin') && (
          <a href="/tv" target="_blank" rel="noopener noreferrer" className={`${fl.btnSecondary} flex items-center justify-center gap-2 text-center`}>
            <Tv size={15} /> Launch TV Mode
          </a>
        )}
        <button onClick={logout} className={fl.btnDanger}>
          Log Out & Clear Device
        </button>
        {versionQuery.data?.version && (
          <p className={`text-center text-[11px] ${fl.muted}`}>{versionQuery.data.version}</p>
        )}
      </div>
    </>
  )

  // An operator/packer with nothing granted at all - never had anything, or
  // had it revoked since a bookmark or a stale tab was left open on this
  // path - has nothing in here to see. Every hook above has already run
  // unconditionally by this point, so this early return is safe; a
  // manager/admin never hits it (hasAnyManagerAbility is role-true for them).
  if (!hasAnyManagerAbility(user)) return <Navigate to="/operator-form" replace />

  const { lead: titleLead, tail: titleTail, sub: titleSub } = brandTitle(simpleMode)
  const themeSlug = paletteByName(user?.preferred_theme).slug

  return (
    <div className="flex h-svh flex-col bg-[var(--fl-ground)]">
      {/* The same branding as the login screen - same wording, same cyan
          accent, deliberately independent of the active theme (see
          brandTitle.ts) - so the plant's own name for itself doesn't change
          with a personal colour preference any more than it changes the
          moment somebody signs in. Full width, and doubles as the mobile
          menu bar (the ☰ button only shows below md; the sidebar itself
          covers that job on desktop). */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--fl-border)] bg-[var(--fl-surface)] px-4 py-3 sm:px-6">
        <button onClick={() => setDrawerOpen(true)} className={`${fl.btnSecondary} shrink-0 md:hidden`} aria-label="Open menu">
          ☰
        </button>
        <img
          src="/formlabs_logo.png" alt=""
          className="h-8 shrink-0 object-contain"
          style={{ filter: 'drop-shadow(0px 0px 8px rgba(0, 210, 255, 0.4))' }}
        />
        <div className="min-w-0">
          <h1 className="truncate text-lg font-extrabold tracking-tight text-white sm:text-xl">
            {titleLead} <span className="font-light text-[#00D2FF]">{titleTail}</span>
          </h1>
          <p className="hidden font-mono text-[0.65rem] uppercase tracking-widest text-[#00D2FF] sm:block">
            {titleSub}
          </p>
        </div>
      </header>

      {/* Rendered once here, not inside sidebarContent (which mounts twice
          at once - see the note above its "Account & Preferences" trigger
          button) - position:fixed doesn't need to sit near either trigger
          to appear in the right place, and one instance means one
          click-outside listener, so a click anywhere inside it is
          correctly recognised as inside. */}
      {showAccount && <AccountPanel onClose={() => setShowAccount(false)} />}

      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/60" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 flex-col gap-4 overflow-y-auto border-r border-[var(--fl-border)] bg-[var(--fl-surface)] p-4">
            {sidebarContent}
          </div>
        </div>
      )}

      {/* Below the header, the sidebar and main content each fill and
          scroll within the REST of the screen - a fixed-height app shell
          (not min-h-svh + sticky) so the sidebar's own h-full never
          overshoots the viewport by the header's own height. */}
      <div className="flex flex-1 overflow-hidden">
        {collapsed ? (
          <button
            onClick={toggleCollapsed}
            title="Expand sidebar"
            className="hidden h-8 w-8 shrink-0 items-center justify-center self-start rounded-r-md border border-l-0 border-[var(--fl-border)] bg-[var(--fl-surface)] text-[var(--fl-muted)] hover:text-[var(--fl-ink)] md:flex"
          >
            »
          </button>
        ) : (
          <aside className="hidden h-full w-64 shrink-0 flex-col gap-4 overflow-y-auto border-r border-[var(--fl-border)] bg-[var(--fl-surface)] p-4 md:flex">
            {sidebarContent}
          </aside>
        )}

        <main className="relative h-full min-w-0 flex-1 overflow-y-auto p-4">
          <ThemeFlourish slug={themeSlug} />
          {/* Its own positioned+stacked layer, not just plain content after
              the flourish in DOM order: a static (non-positioned) sibling
              actually paints BEFORE a position:absolute z-0 element in CSS's
              own stacking rules, which would otherwise put the "background"
              flourish on top of the page. */}
          <div className="relative z-10">
          {(user?.role === 'manager' || user?.role === 'admin') && <UpdateBanner />}
          {tab === 'cockpit' && (
            <ManagerCockpitHub
              onNavigate={go}
              ordersOn={ordersOn}
              canAdminister={canAdminister}
              canSee={(key) => canSeeManagerTab(user, key)}
              isManagement={user?.role === 'manager' || user?.role === 'admin'}
            />
          )}
          {tab !== 'cockpit' && canSeeManagerTab(user, 'cockpit') && (
            <button onClick={() => go('cockpit')} className="mb-4 flex items-center gap-1.5 text-sm font-semibold text-[var(--fl-accent-2)] hover:underline">
              <ArrowLeft size={15} /> Manager Cockpit
            </button>
          )}

          {tab === 'scada' && <ScadaPage />}
          {tab === 'reactors' && <ReactorFleetPage />}
          {tab === 'cleanliness' && <CleanlinessGalleryPage />}
          {tab === 'checks' && <CheckStatusPage />}
          {tab === 'roster' && <RosterPage />}
          {tab === 'floor-comms' && <FloorCommsPage />}
          {tab === 'scrap-intel' && <ScrapIntelPage />}
          {tab === 'lot-verification' && <LotVerificationPage />}
          {tab === 'batch-history' && <BatchHistoryPage />}
          {tab === 'historical' && <HistoricalPage />}
          {tab === 'resin-canvas' && <ResinCanvasPage />}
          {tab === 'assigned-runs' && <AssignedRunsPage />}
          {tab === 'log-management' && <LogManagementPage />}
          {tab === 'google-sync' && <GoogleSyncPage />}
          {tab === 'analytics' && <AnalyticsHubPage />}
          {tab === 'admin' && canAdminister && <AdminPanelPage />}
          {tab === 'devices' && canSeeDeviceGateway && <DeviceRegistryPage />}
          </div>
        </main>
      </div>
    </div>
  )
}
