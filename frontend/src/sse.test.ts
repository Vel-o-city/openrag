import { describe, expect, it } from 'vitest'
import { parseSSEChunk, streamSSE } from './sse'

describe('parseSSEChunk', () => {
  it('parses a single complete event', () => {
    const { events, remainder } = parseSSEChunk('event: token\ndata: {"text":"hi"}\n\n')
    expect(events).toEqual([{ event: 'token', data: '{"text":"hi"}' }])
    expect(remainder).toBe('')
  })

  it('parses multiple complete events in one buffer', () => {
    const buffer = 'event: token\ndata: a\n\nevent: token\ndata: b\n\n'
    const { events, remainder } = parseSSEChunk(buffer)
    expect(events).toEqual([
      { event: 'token', data: 'a' },
      { event: 'token', data: 'b' },
    ])
    expect(remainder).toBe('')
  })

  it('holds back an incomplete trailing block', () => {
    const buffer = 'event: token\ndata: a\n\nevent: token\ndata: b'
    const { events, remainder } = parseSSEChunk(buffer)
    expect(events).toEqual([{ event: 'token', data: 'a' }])
    expect(remainder).toBe('event: token\ndata: b')
  })

  it('defaults to event "message" when no event line is present', () => {
    const { events } = parseSSEChunk('data: just data\n\n')
    expect(events).toEqual([{ event: 'message', data: 'just data' }])
  })

  it('joins multiple data lines within one block', () => {
    const { events } = parseSSEChunk('event: token\ndata: line1\ndata: line2\n\n')
    expect(events).toEqual([{ event: 'token', data: 'line1\nline2' }])
  })

  it('ignores blank blocks from repeated separators', () => {
    const { events } = parseSSEChunk('event: token\ndata: a\n\n\n\n')
    expect(events).toEqual([{ event: 'token', data: 'a' }])
  })

  it('returns no events for an empty buffer', () => {
    const { events, remainder } = parseSSEChunk('')
    expect(events).toEqual([])
    expect(remainder).toBe('')
  })

  it('parses CRLF line endings — the actual wire format from this backend', () => {
    const buffer = 'event: token\r\ndata: {"text":"hi"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n'
    const { events, remainder } = parseSSEChunk(buffer)
    expect(events).toEqual([
      { event: 'token', data: '{"text":"hi"}' },
      { event: 'done', data: '{}' },
    ])
    expect(remainder).toBe('')
  })

  it('holds back an incomplete trailing block with CRLF endings', () => {
    const buffer = 'event: token\r\ndata: a\r\n\r\nevent: token\r\ndata: b'
    const { events, remainder } = parseSSEChunk(buffer)
    expect(events).toEqual([{ event: 'token', data: 'a' }])
    expect(remainder).toBe('event: token\ndata: b')
  })
})

function fakeResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  let i = 0
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]))
        i += 1
      } else {
        controller.close()
      }
    },
  })
  return new Response(stream)
}

describe('streamSSE', () => {
  it('yields events reassembled across chunk boundaries', async () => {
    const response = fakeResponse(['event: token\ndata: hel', 'lo\n\nevent: done\ndata: {}\n\n'])
    const events = []
    for await (const event of streamSSE(response)) events.push(event)

    expect(events).toEqual([
      { event: 'token', data: 'hello' },
      { event: 'done', data: '{}' },
    ])
  })

  it('yields nothing when the response has no body', async () => {
    const response = new Response(null)
    const events = []
    for await (const event of streamSSE(response)) events.push(event)
    expect(events).toEqual([])
  })

  it('yields events from a single CRLF-terminated chunk (this was silently broken)', async () => {
    const response = fakeResponse([
      'event: token\r\ndata: {"text":"hi"}\r\n\r\nevent: citations\r\ndata: {}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n',
    ])
    const events = []
    for await (const event of streamSSE(response)) events.push(event)

    expect(events).toEqual([
      { event: 'token', data: '{"text":"hi"}' },
      { event: 'citations', data: '{}' },
      { event: 'done', data: '{}' },
    ])
  })
})
