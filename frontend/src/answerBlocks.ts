import type { Segment } from './citations'

/**
 * The model answers in light markdown — bold runs, "* " bullets, occasional
 * "###" headings — which previously reached the page as literal asterisks.
 *
 * This renders that subset only, rather than pulling in a markdown library:
 * the input isn't arbitrary markdown, and a parser has to interleave with
 * citation markers anyway, which a drop-in renderer can't do.
 */

export type Inline =
  | { kind: 'text'; text: string; bold: boolean }
  | { kind: 'marker'; label: string; n: number }

export interface Block {
  kind: 'paragraph' | 'bullet' | 'heading'
  inlines: Inline[]
}

const BULLET_PREFIX = /^\s*[*-]\s+/
const HEADING_PREFIX = /^\s*#{1,6}\s+/
// A markdown thematic break ("---"). The headings already separate sections, so
// this is dropped rather than drawn — otherwise it reaches the page as dashes.
const THEMATIC_BREAK = /^\s*([-*_])\s*(\1\s*){2,}$/

/** Splits segments at newlines, keeping markers attached to their line. */
function toLines(segments: Segment[]): Segment[][] {
  const lines: Segment[][] = [[]]

  for (const segment of segments) {
    if (segment.kind === 'marker') {
      lines[lines.length - 1].push(segment)
      continue
    }

    segment.text.split('\n').forEach((part, index) => {
      if (index > 0) lines.push([])
      if (part) lines[lines.length - 1].push({ kind: 'text', text: part })
    })
  }

  return lines
}

/**
 * Toggles bold at each `**`, carrying the state across a line's markers so
 * emphasis spanning a citation still closes.
 */
function splitBold(text: string, state: { bold: boolean }): Inline[] {
  const inlines: Inline[] = []
  let rest = text

  while (rest.length > 0) {
    const at = rest.indexOf('**')
    if (at === -1) {
      inlines.push({ kind: 'text', text: rest, bold: state.bold })
      break
    }
    if (at > 0) inlines.push({ kind: 'text', text: rest.slice(0, at), bold: state.bold })
    state.bold = !state.bold
    rest = rest.slice(at + 2)
  }

  return inlines
}

export function toBlocks(segments: Segment[]): Block[] {
  const blocks: Block[] = []

  for (const line of toLines(segments)) {
    if (line.length === 0) continue

    const first = line[0]
    let kind: Block['kind'] = 'paragraph'
    let stripped = line

    if (first.kind === 'text') {
      if (line.length === 1 && THEMATIC_BREAK.test(first.text)) continue

      if (BULLET_PREFIX.test(first.text)) {
        kind = 'bullet'
        stripped = [{ ...first, text: first.text.replace(BULLET_PREFIX, '') }, ...line.slice(1)]
      } else if (HEADING_PREFIX.test(first.text)) {
        kind = 'heading'
        stripped = [{ ...first, text: first.text.replace(HEADING_PREFIX, '') }, ...line.slice(1)]
      }
    }

    const state = { bold: false }
    const inlines = stripped.flatMap((segment) =>
      segment.kind === 'marker' ? [segment] : splitBold(segment.text, state),
    )

    // A line that was only markdown punctuation leaves nothing to show.
    if (inlines.every((inline) => inline.kind === 'text' && inline.text.trim() === '')) continue

    // A fully-bold line reads as a heading whether or not it used '#'.
    const isAllBold =
      kind === 'paragraph' &&
      inlines.length > 0 &&
      inlines.every((inline) => inline.kind === 'marker' || inline.bold)

    blocks.push({ kind: isAllBold ? 'heading' : kind, inlines })
  }

  return blocks
}
