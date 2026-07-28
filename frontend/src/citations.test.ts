import { describe, expect, it } from 'vitest'
import { parseAnswer, type Segment } from './citations'

const RESOLVABLE = new Set(['C1', 'C3', 'E1', 'E2'])

function textOf(segments: Segment[]): string {
  return segments.map((s) => (s.kind === 'text' ? s.text : `<${s.n}>`)).join('')
}

describe('parseAnswer', () => {
  it('splits markers out of the prose and numbers them', () => {
    const { segments } = parseAnswer('Ada [C1] built it [E1].', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(textOf(segments)).toBe('Ada <1> built it <2>.')
  })

  it('numbers by first appearance, not by label order', () => {
    const { segments, order } = parseAnswer('First [C3], then [C1].', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(textOf(segments)).toBe('First <1>, then <2>.')
    expect(order).toEqual(['C3', 'C1'])
  })

  it('reuses the same number for a repeated label', () => {
    const { segments, order } = parseAnswer('[C1] and again [C1] and [E1].', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(textOf(segments)).toBe('<1> and again <1> and <2>.')
    expect(order).toEqual(['C1', 'E1'])
  })

  it('strips labels the payload does not know', () => {
    const { segments, order } = parseAnswer('Real [C1], invented [C99].', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(textOf(segments)).toBe('Real <1>, invented .')
    expect(order).toEqual(['C1'])
  })

  it('keeps unverified markers while streaming, since nothing is resolvable yet', () => {
    const { segments } = parseAnswer('Ada [C1] built it.', { isStreaming: true })
    expect(textOf(segments)).toBe('Ada <1> built it.')
  })

  describe('partial markers mid-stream', () => {
    it.each(['Ada [', 'Ada [C', 'Ada [C3'])('withholds the partial tail %j', (chunk) => {
      const { segments } = parseAnswer(chunk, { isStreaming: true })
      expect(textOf(segments)).toBe('Ada ')
    })

    it('renders the marker once the closing bracket arrives', () => {
      const { segments } = parseAnswer('Ada [C3]', { isStreaming: true })
      expect(textOf(segments)).toBe('Ada <1>')
    })

    it('does not withhold a bracket that is already complete', () => {
      const { segments } = parseAnswer('Ada [C1] and [', { isStreaming: true })
      expect(textOf(segments)).toBe('Ada <1> and ')
    })

    it('leaves a trailing partial alone once streaming has finished', () => {
      // Not a marker after all — the model just wrote a bracket. Keep it.
      const { segments } = parseAnswer('See [', { isStreaming: false, resolvable: RESOLVABLE })
      expect(textOf(segments)).toBe('See [')
    })
  })

  it('assigns stable numbers across successive streaming snapshots', () => {
    const snapshots = ['Ada [C3] built', 'Ada [C3] built the [C1] engine', 'Ada [C3] built the [C1] engine [C3].']
    const numbersFor = (text: string) =>
      parseAnswer(text, { isStreaming: true })
        .segments.filter((s): s is Extract<Segment, { kind: 'marker' }> => s.kind === 'marker')
        .map((s) => `${s.label}=${s.n}`)

    expect(numbersFor(snapshots[0])).toEqual(['C3=1'])
    expect(numbersFor(snapshots[1])).toEqual(['C3=1', 'C1=2'])
    // C3 keeps 1 and C1 keeps 2 — no renumbering as the answer grows.
    expect(numbersFor(snapshots[2])).toEqual(['C3=1', 'C1=2', 'C3=1'])
  })

  it('handles an answer with no markers at all', () => {
    const { segments, order } = parseAnswer('No citations here.', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(segments).toEqual([{ kind: 'text', text: 'No citations here.' }])
    expect(order).toEqual([])
  })

  it('handles an empty answer', () => {
    const { segments, order } = parseAnswer('', { isStreaming: true })
    expect(segments).toEqual([])
    expect(order).toEqual([])
  })

  // The model groups labels inside one bracket in practice, so this form has to
// work regardless of what the prompt asks for.
  describe('grouped labels in one bracket', () => {
    it('splits a grouped marker into one footnote per label', () => {
      const { segments, order } = parseAnswer('Okonkwo directs it [E1, C1].', {
        isStreaming: false,
        resolvable: RESOLVABLE,
      })
      expect(textOf(segments)).toBe('Okonkwo directs it <1><2>.')
      expect(order).toEqual(['E1', 'C1'])
    })

    it('shares numbering with separately-bracketed labels', () => {
      const { segments, order } = parseAnswer('One [C1] then [E1, C1] again.', {
        isStreaming: false,
        resolvable: RESOLVABLE,
      })
      // C1 keeps 1 in both spots; E1 is the only new label.
      expect(textOf(segments)).toBe('One <1> then <2><1> again.')
      expect(order).toEqual(['C1', 'E1'])
    })

    it('accepts semicolons and irregular spacing', () => {
      const { segments } = parseAnswer('a [C1;E1] b [C3 , E2] c', {
        isStreaming: false,
        resolvable: RESOLVABLE,
      })
      expect(textOf(segments)).toBe('a <1><2> b <3><4> c')
    })

    it('drops only the unknown labels inside a group', () => {
      const { segments, order } = parseAnswer('Mixed [C1, C99].', {
        isStreaming: false,
        resolvable: RESOLVABLE,
      })
      expect(textOf(segments)).toBe('Mixed <1>.')
      expect(order).toEqual(['C1'])
    })

    it.each(['Ada [E1,', 'Ada [E1, ', 'Ada [E1, C', 'Ada [E1, C1'])(
      'withholds the partial grouped tail %j',
      (chunk) => {
        const { segments } = parseAnswer(chunk, { isStreaming: true })
        expect(textOf(segments)).toBe('Ada ')
      },
    )

    it('renders the whole group once its closing bracket arrives', () => {
      const { segments } = parseAnswer('Ada [E1, C1]', { isStreaming: true })
      expect(textOf(segments)).toBe('Ada <1><2>')
    })
  })

  it('ignores bracketed text that is not a citation label', () => {
    const { segments } = parseAnswer('An aside [see below] and [C1].', {
      isStreaming: false,
      resolvable: RESOLVABLE,
    })
    expect(textOf(segments)).toBe('An aside [see below] and <1>.')
  })
})
