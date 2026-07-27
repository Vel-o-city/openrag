/**
 * Remembers which documents *this* browser uploaded, so a citation into one
 * can be badged as yours.
 *
 * Deliberately client-side. The upload response already returns document_id,
 * so matching locally needs no server work — and the alternative, sending a
 * visitor id up to be stored on a public Document node, would put a tracking
 * identifier in a shared graph to achieve exactly the same badge.
 */

const STORAGE_KEY = 'openrag:own-docs'
const MAX_REMEMBERED = 20
const EXPIRY_MS = 30 * 24 * 60 * 60 * 1000 // 30 days

interface OwnDocument {
  id: string
  at: number
}

// Safari in private mode throws on setItem, and storage can be disabled
// outright. Losing the badge is fine; breaking an upload is not.
function read(): OwnDocument[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []

    const cutoff = Date.now() - EXPIRY_MS
    return parsed.filter(
      (entry): entry is OwnDocument =>
        typeof entry?.id === 'string' && typeof entry?.at === 'number' && entry.at > cutoff,
    )
  } catch {
    return []
  }
}

function write(entries: OwnDocument[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // Storage unavailable or full — the badge just won't persist.
  }
}

export function rememberOwnDocument(id: string): void {
  if (!id) return
  const existing = read().filter((entry) => entry.id !== id)
  write([...existing, { id, at: Date.now() }].slice(-MAX_REMEMBERED))
}

export function isOwnDocument(id: string): boolean {
  return read().some((entry) => entry.id === id)
}

export function ownDocumentIds(): string[] {
  return read().map((entry) => entry.id)
}
