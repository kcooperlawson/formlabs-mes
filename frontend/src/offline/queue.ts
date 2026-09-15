// Retries the three floor writes that actually happen mid-shift (pouring,
// packing, downtime) when the network drops out from under one, instead of
// handing the operator an error for something that was never their fault.
//
// Deliberately NOT the Background Sync API: it doesn't exist on iOS Safari
// at all, and this app runs on whatever phone an operator already carries -
// a queue the page itself drains on the `online` event and a short interval
// covers the real case (a WiFi blip mid-shift, tab stays open) without
// depending on a browser feature half the fleet can't use. The one thing
// this genuinely can't do is finish a submit after the tab is closed
// offline - see ChecklistGate's own "stays open all shift" assumption,
// which this shares.
import { ApiError } from '../api/client'
import { downtimeApi } from '../api/downtime'
import { packingApi } from '../api/packing'
import { pouringApi } from '../api/pouring'
import { offlineDb, type QueuedRequest } from './db'

type Listener = (count: number) => void
const listeners = new Set<Listener>()
let cachedCount = 0
let flushing = false

function publish(count: number) {
  cachedCount = count
  for (const l of listeners) l(count)
}

export function subscribeQueueCount(listener: Listener): () => void {
  listeners.add(listener)
  listener(cachedCount)
  return () => listeners.delete(listener)
}

export function getQueueCountSnapshot(): number {
  return cachedCount
}

async function refreshCount() {
  publish(await offlineDb.count())
}

// A network-level failure (offline, DNS, server unreachable) throws before
// client.ts ever gets a response to wrap into an ApiError - that's the
// signal this was connectivity, not a real rejection. A 422/403/etc IS an
// ApiError, and queuing that would just fail identically on every retry
// while hiding a real problem (a bad lot, a permission the operator
// doesn't have) behind a false "it's queued" reassurance.
export function isConnectivityError(err: unknown): boolean {
  return !(err instanceof ApiError)
}

export async function enqueue(kind: QueuedRequest['kind'], entries: Array<[string, string | File]>) {
  await offlineDb.add({ kind, entries, createdAt: Date.now() })
  await refreshCount()
  void flush()
}

function toFormData(entries: Array<[string, string | File]>): FormData {
  const fd = new FormData()
  for (const [k, v] of entries) fd.set(k, v)
  return fd
}

function toObject(entries: Array<[string, string | File]>): Record<string, string> {
  return Object.fromEntries(entries) as Record<string, string>
}

async function send(req: QueuedRequest): Promise<void> {
  if (req.kind === 'pouring') {
    await pouringApi.submit(toFormData(req.entries))
    return
  }
  const body = toObject(req.entries)
  if (req.kind === 'packing') {
    await packingApi.submit({
      cartridge_type: body.cartridge_type, resin: body.resin, lot_number: body.lot_number,
      units_packed: Number(body.units_packed), notes: body.notes || undefined,
      as_operator: body.as_operator || undefined,
    })
    return
  }
  await downtimeApi.submit({
    station: body.station, reason: body.reason, duration_min: Number(body.duration_min),
    notes: body.notes || undefined, as_operator: body.as_operator || undefined,
  })
}

// Oldest first, and stops at the first failure rather than skipping ahead -
// a changeover/downtime/pour recorded out of order reads wrong on every
// screen downstream of it, and "stop and retry later" costs nothing when
// the fallback is a 15s timer and the `online` event.
export async function flush(): Promise<void> {
  if (flushing) return
  flushing = true
  try {
    for (;;) {
      const [next] = await offlineDb.all()
      if (!next) break
      try {
        await send(next)
      } catch (err) {
        if (isConnectivityError(err)) return // still offline - try again later
        // A real rejection: drop it rather than retry forever on something
        // that will never succeed, but never silently - the operator needs
        // to know this one didn't actually land.
        console.error('Dropped a queued submission that the server rejected:', err)
      }
      await offlineDb.remove(next.id!)
      await refreshCount()
    }
  } finally {
    flushing = false
  }
}

let started = false
export function startOfflineQueue() {
  if (started) return
  started = true
  void refreshCount().then(flush)
  window.addEventListener('online', () => void flush())
  // Belt-and-suspenders with the `online` event: a captive-portal Wi-Fi that
  // says it's connected but isn't yet, or a browser that just doesn't fire
  // `online` reliably (observed on some Android WebViews), still drains
  // within one interval instead of waiting for the tab to reload.
  window.setInterval(() => void flush(), 15_000)
}
