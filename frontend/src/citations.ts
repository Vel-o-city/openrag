export interface CitedChunk {
  id: string
  label: string
  text: string
  truncated: boolean
  char_count: number
  page_number: number
  document_id: string
  filename: string
}

export interface CitedDocument {
  id: string
  filename: string
  pages: number[]
}

export interface LabelTarget {
  kind: 'entity' | 'chunk'
  id: string
  name: string | null
}

export interface Citations {
  entities: string[]
  relationships: string[]
  chunks: CitedChunk[]
  documents: CitedDocument[]
  labels: Record<string, LabelTarget>
  precise: boolean
  flagged_urls: string[]
}

export type Segment =
  | { kind: 'text'; text: string }
  | { kind: 'marker'; label: string; n: number }

const LABEL = String.raw`[EC]\d{1,3}`

// The model groups labels inside one bracket at least as often as it writes
// them separately — "[E11, C1]" rather than "[E11][C1]". The prompt asks for
// one label per bracket, but that's a request, not a guarantee, so parse the
// grouped form too: a bracket holding a comma/semicolon-separated list becomes
// one footnote per label. Missing this left the grouped form as literal prose,
// which is the whole citation UI silently not firing.
const MARKER = new RegExp(String.raw`\[(${LABEL}(?:\s*[,;]\s*${LABEL})*)\]`, 'g')
const LABEL_SEPARATOR = /\s*[,;]\s*/

// A marker arriving one token at a time passes through "[", "[C", "[C3" before
// it becomes "[C3]" — and a grouped one additionally through "[E11,", "[E11, C".
// Rendering those intermediates flashes bracket noise into the prose, so
// withhold a trailing partial match while streaming — the same trick the
// backend uses to keep the ---CITATIONS--- marker from leaking.
const PARTIAL_TAIL = new RegExp(
  String.raw`\[[EC]?\d{0,3}(?:\s*[,;]\s*(?:[EC]?\d{0,3})?)*$`,
)

interface ParseOptions {
  isStreaming: boolean
  /** Labels the backend confirmed. Undefined until the citations event lands. */
  resolvable?: Set<string>
}

/**
 * Splits an answer into text and citation-marker segments, numbering markers
 * by order of first appearance so footnote [1] is the one the reader meets
 * first. Streamed text only ever grows, so those numbers are stable — a
 * marker never renumbers as more tokens arrive.
 */
export function parseAnswer(
  text: string,
  { isStreaming, resolvable }: ParseOptions,
): { segments: Segment[]; order: string[] } {
  const body = isStreaming ? text.replace(PARTIAL_TAIL, '') : text
  const segments: Segment[] = []
  const numberByLabel = new Map<string, number>()
  let cursor = 0

  for (const match of body.matchAll(MARKER)) {
    const index = match.index ?? 0

    if (index > cursor) {
      segments.push({ kind: 'text', text: body.slice(cursor, index) })
    }

    for (const label of match[1].split(LABEL_SEPARATOR)) {
      // Once the payload has arrived, a label it doesn't know is one the model
      // invented — the backend already dropped it, so drop the marker too
      // rather than leaving a footnote that points nowhere.
      const isDead = resolvable !== undefined && !resolvable.has(label)
      if (isDead) continue

      if (!numberByLabel.has(label)) numberByLabel.set(label, numberByLabel.size + 1)
      segments.push({ kind: 'marker', label, n: numberByLabel.get(label)! })
    }

    cursor = index + match[0].length
  }

  if (cursor < body.length) {
    segments.push({ kind: 'text', text: body.slice(cursor) })
  }

  return { segments, order: [...numberByLabel.keys()] }
}
