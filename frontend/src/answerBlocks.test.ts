import { describe, expect, it } from 'vitest'
import { toBlocks } from './answerBlocks'
import { parseAnswer, type Segment } from './citations'

const RESOLVABLE = new Set(['C1', 'C2', 'E1', 'E2'])

function blocksFor(answer: string) {
  const { segments } = parseAnswer(answer, { isStreaming: false, resolvable: RESOLVABLE })
  return toBlocks(segments)
}

/** Renders a block back to a string: **bold**, <n> for a footnote. */
function render(inlines: ReturnType<typeof toBlocks>[number]['inlines']): string {
  return inlines
    .map((inline) =>
      inline.kind === 'marker'
        ? `<${inline.n}>`
        : inline.bold
          ? `**${inline.text}**`
          : inline.text,
    )
    .join('')
}

function shapeOf(answer: string) {
  return blocksFor(answer).map((block) => `${block.kind}:${render(block.inlines)}`)
}

describe('toBlocks', () => {
  it('turns a plain answer into one paragraph', () => {
    expect(shapeOf('Ada built it.')).toEqual(['paragraph:Ada built it.'])
  })

  it('unwraps bold runs instead of leaving asterisks in the prose', () => {
    expect(shapeOf('Built by **Ada Lovelace** in 1843.')).toEqual([
      'paragraph:Built by **Ada Lovelace** in 1843.',
    ])
  })

  it('treats a fully-bold line as a heading', () => {
    expect(shapeOf('**Who runs it**\nAda does.')).toEqual([
      'heading:**Who runs it**',
      'paragraph:Ada does.',
    ])
  })

  it('strips heading hashes', () => {
    expect(shapeOf('### Leadership\nAda does.')).toEqual([
      'heading:Leadership',
      'paragraph:Ada does.',
    ])
  })

  it('strips bullet markers, for both * and -', () => {
    expect(shapeOf('Details:\n* First\n- Second')).toEqual([
      'paragraph:Details:',
      'bullet:First',
      'bullet:Second',
    ])
  })

  it('keeps footnotes attached to the line they were on', () => {
    expect(shapeOf('* Funded by the council [C1]\n* Built in 1843 [E1]')).toEqual([
      'bullet:Funded by the council <1>',
      'bullet:Built in 1843 <2>',
    ])
  })

  it('closes bold that spans a citation marker', () => {
    // The '**' opens in one text segment and closes in another, with a marker
    // in between — a per-segment parse would leave it open.
    expect(shapeOf('**Ada [C1] Lovelace** built it.')).toEqual([
      'paragraph:**Ada **<1>** Lovelace** built it.',
    ])
  })

  it('drops blank lines rather than emitting empty paragraphs', () => {
    expect(shapeOf('First.\n\n\nSecond.')).toEqual(['paragraph:First.', 'paragraph:Second.'])
  })

  it('drops a line that was only markdown punctuation', () => {
    expect(shapeOf('Real line.\n**\n')).toEqual(['paragraph:Real line.'])
  })

  it('handles a bold label leading a bullet', () => {
    expect(shapeOf('* **Funding:** grants only.')).toEqual([
      'bullet:**Funding:** grants only.',
    ])
  })

  it.each(['---', '***', '- - -', '___'])('drops the thematic break %j', (rule) => {
    expect(shapeOf(`First.\n${rule}\nSecond.`)).toEqual([
      'paragraph:First.',
      'paragraph:Second.',
    ])
  })

  it('keeps a single-dash bullet, which looks similar but is not a break', () => {
    expect(shapeOf('- Only one item')).toEqual(['bullet:Only one item'])
  })

  it('returns nothing for an empty answer', () => {
    expect(blocksFor('')).toEqual([])
  })

  it('leaves a mid-stream partial marker out without breaking blocks', () => {
    const { segments } = parseAnswer('Ada built it [C', { isStreaming: true })
    expect(toBlocks(segments).map((b) => `${b.kind}:${render(b.inlines)}`)).toEqual([
      'paragraph:Ada built it ',
    ])
  })

  it('numbers footnotes across blocks, not per block', () => {
    const shape = shapeOf('* One [C1]\n* Two [C2]\n* Again [C1]')
    expect(shape).toEqual(['bullet:One <1>', 'bullet:Two <2>', 'bullet:Again <1>'])
  })

  it('preserves segment order for a marker opening a line', () => {
    const segments: Segment[] = [
      { kind: 'marker', label: 'C1', n: 1 },
      { kind: 'text', text: ' leads.' },
    ]
    expect(toBlocks(segments).map((b) => `${b.kind}:${render(b.inlines)}`)).toEqual([
      'paragraph:<1> leads.',
    ])
  })
})
