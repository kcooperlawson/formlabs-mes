// Design tokens for every ported page, now backed by CSS custom properties
// (--fl-*) instead of literal hex values, so a token here re-themes under
// every palette in palettes.ts rather than only ever painting Formlabs
// Forge. See ThemeRoot.tsx (sets the active palette) and themeCss.ts
// (generates the --fl-* declarations this file reads via Tailwind's
// arbitrary-value syntax, e.g. bg-[var(--fl-surface)]).
export const fl = {
  page: 'text-[var(--fl-ink)]',
  heading: 'text-lg font-bold text-[var(--fl-ink)]',
  muted: 'text-[var(--fl-muted)]',
  label: 'text-[0.68rem] font-extrabold uppercase tracking-wider text-[var(--fl-body)]',

  card: 'rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3',
  cardHover:
    'rounded-lg border border-[var(--fl-border)] border-l-4 border-l-[var(--fl-muted)] bg-[var(--fl-surface)] p-3 transition-all hover:-translate-x-0 hover:border-l-[var(--fl-accent)] hover:bg-[var(--fl-raised)] hover:shadow-[-4px_4px_10px_rgba(0,0,0,0.4)]',
  tile: 'rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3 text-center',

  input:
    'w-full rounded border border-[var(--fl-border)] bg-[var(--fl-surface)] px-2 py-1.5 text-sm font-semibold text-[var(--fl-accent-2)] placeholder:text-[var(--fl-muted)] placeholder:font-normal focus:border-[var(--fl-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--fl-accent)]/20',
  select:
    'w-full rounded border border-[var(--fl-border)] bg-[var(--fl-surface)] px-2 py-1.5 text-sm text-[var(--fl-ink)] focus:border-[var(--fl-accent)] focus:outline-none',

  btn: 'rounded bg-[var(--fl-accent)] px-3 py-2 text-sm font-extrabold uppercase tracking-wide text-white shadow-[var(--fl-shadow)] transition hover:bg-[var(--fl-accent-2)] hover:shadow-[var(--fl-shadow-hover)] disabled:opacity-40',
  btnSecondary:
    'rounded border border-[var(--fl-border)] bg-transparent px-3 py-1.5 text-xs font-semibold text-[var(--fl-body)] transition hover:border-[var(--fl-accent)] hover:text-[var(--fl-accent-2)] disabled:opacity-40',
  btnDanger:
    'rounded bg-[#7F1D1D] px-3 py-2 text-sm font-extrabold uppercase tracking-wide text-white shadow transition hover:bg-[#DC2626] disabled:opacity-40',

  badge:
    'inline-block rounded border border-[var(--fl-accent)] bg-[var(--fl-accent-wash)] px-2.5 py-1 text-xs font-extrabold uppercase tracking-widest text-[var(--fl-accent-2)]',

  tabStrip: 'flex gap-2 overflow-x-auto pb-2',
  tabActive:
    'shrink-0 rounded-full border border-current bg-[var(--fl-overlay-strong)] px-4 py-2 text-sm font-black text-[var(--fl-ink)] shadow-[inset_0_0_10px_currentColor,0_4px_15px_rgba(0,0,0,0.3)]',
  tabInactive:
    'shrink-0 rounded-full border border-[var(--fl-overlay)] bg-[var(--fl-overlay-weak)] px-4 py-2 text-sm font-bold text-[var(--fl-muted)] transition hover:-translate-y-0.5 hover:bg-[var(--fl-overlay)]',

  navItem:
    'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-semibold text-[var(--fl-body)] transition hover:bg-[var(--fl-overlay-weak)] hover:text-[var(--fl-ink)]',

  tableHead: 'text-[0.68rem] font-extrabold uppercase tracking-wider text-[var(--fl-muted)]',
  tableRow: 'border-t border-[var(--fl-border)]',

  divider: 'border-[var(--fl-border)]',
}
