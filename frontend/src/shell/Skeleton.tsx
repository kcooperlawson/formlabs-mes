// A placeholder shape that pulses gently while the real content is on its
// way - replaces a bare "Loading…" line with something that at least
// outlines what's about to appear, so the page reads as "working" rather
// than "empty" for the half-second a query takes. prefers-reduced-motion
// already turns every animation's duration near-instant globally (see
// index.css), so this needs no separate opt-out.
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--fl-overlay-weak)] ${className}`} />
}

// Matches StatCard's own layout (ScadaPage.tsx) so the transition from
// skeleton to real card doesn't visibly reflow.
export function StatCardSkeleton() {
  return (
    <div className="rounded-lg border border-[var(--fl-border)] bg-[var(--fl-surface)] p-3">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="mt-2 h-6 w-16" />
      <Skeleton className="mt-2 h-3 w-24" />
    </div>
  )
}
