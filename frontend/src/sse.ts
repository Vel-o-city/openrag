export interface SSEEvent {
  event: string
  data: string
}

/**
 * Splits accumulated SSE text into complete `event:`/`data:` blocks
 * (separated by a blank line) plus whatever incomplete trailing text hasn't
 * arrived yet. Pure and buffer-based so a block split across two network
 * chunks parses correctly once the rest arrives.
 *
 * Line endings are normalized to `\n` first — the spec allows `\n`, `\r\n`,
 * or bare `\r`, and this server's responses arrive as `\r\n`.
 */
export function parseSSEChunk(buffer: string): { events: SSEEvent[]; remainder: string } {
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const blocks = normalized.split('\n\n')
  const remainder = blocks.pop() ?? ''

  const events: SSEEvent[] = []
  for (const block of blocks) {
    if (!block.trim()) continue

    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    events.push({ event: eventName, data: dataLines.join('\n') })
  }

  return { events, remainder }
}

export async function* streamSSE(response: Response): AsyncGenerator<SSEEvent> {
  if (!response.body) return

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const { events, remainder } = parseSSEChunk(buffer)
    buffer = remainder
    for (const event of events) yield event
  }
}
