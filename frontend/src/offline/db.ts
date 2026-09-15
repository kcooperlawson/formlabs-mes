// A minimal IndexedDB wrapper for exactly one thing: outbound writes made
// while offline. IndexedDB, not localStorage, because a queued pouring
// submit can carry a File (the lot-mismatch photo) - localStorage only
// holds strings, IndexedDB's structured-clone storage holds Blobs/Files
// natively, so a photo taken with no signal survives until it can send.
const DB_NAME = 'mes-offline'
const DB_VERSION = 1
const STORE = 'queue'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export interface QueuedRequest {
  id?: number
  kind: 'pouring' | 'packing' | 'downtime'
  createdAt: number
  // FormData can't be structured-cloned as-is, but its individual string/File
  // values can - stored as entries and rebuilt into a real FormData on replay.
  entries: Array<[string, string | File]>
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = fn(tx.objectStore(STORE))
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  } finally {
    db.close()
  }
}

export const offlineDb = {
  add: (entry: Omit<QueuedRequest, 'id'>) => withStore('readwrite', (s) => s.add(entry)),
  all: () => withStore<QueuedRequest[]>('readonly', (s) => s.getAll()),
  remove: (id: number) => withStore('readwrite', (s) => s.delete(id)),
  count: () => withStore<number>('readonly', (s) => s.count()),
}
