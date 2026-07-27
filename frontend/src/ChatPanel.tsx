import { useRef, useState } from 'react'
import { AnswerText } from './AnswerText'
import { API_BASE } from './apiBase'
import { parseAnswer, type Citations } from './citations'
import { useGraph } from './GraphContext'
import { SourcesList } from './SourcesList'
import { streamSSE } from './sse'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  citations?: Citations
}

/**
 * The graph fetch is capped well below the node ceiling, so an entity the
 * answer cited may not be in the loaded graph. The payload carries its name
 * for exactly this case — falling back to a uuid fragment is a last resort.
 */
function entityNameFromLabels(citations: Citations, entityId: string): string {
  for (const target of Object.values(citations.labels)) {
    if (target.kind === 'entity' && target.id === entityId && target.name) return target.name
  }
  return entityId.slice(0, 8)
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeLabel, setActiveLabel] = useState<string | null>(null)
  const { focusNodes, clearFocus, nodeById } = useGraph()
  const bottomRef = useRef<HTMLDivElement>(null)

  /**
   * A footnote click opens its source card. Entity markers additionally
   * highlight that node on the graph; chunk markers can't, since a chunk
   * isn't a graph node.
   */
  function handleMarkerClick(citations: Citations | undefined, label: string) {
    setActiveLabel(label)
    const target = citations?.labels[label]
    if (target?.kind === 'entity') focusNodes([target.id])
  }

  function updateLastMessage(patch: Partial<ChatMessage>) {
    setMessages((prev) => {
      const next = [...prev]
      next[next.length - 1] = { ...next[next.length - 1], ...patch }
      return next
    })
  }

  async function sendMessage() {
    const question = input.trim()
    if (!question || isStreaming) return

    setInput('')
    clearFocus()
    setActiveLabel(null)
    setMessages((prev) => [...prev, { role: 'user', text: question }, { role: 'assistant', text: '' }])
    setIsStreaming(true)

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question }),
      })

      if (response.status === 429) {
        updateLastMessage({ text: "You've hit the chat rate limit — try again in a bit." })
        return
      }
      if (!response.ok) {
        throw new Error(`Chat request failed (${response.status})`)
      }

      let assistantText = ''
      for await (const event of streamSSE(response)) {
        if (event.event === 'token') {
          const { text } = JSON.parse(event.data) as { text: string }
          assistantText += text
          updateLastMessage({ text: assistantText })
        } else if (event.event === 'citations') {
          const citations = JSON.parse(event.data) as Citations
          updateLastMessage({ citations })
          if (citations.entities.length > 0) focusNodes(citations.entities)
        }
      }
    } catch {
      updateLastMessage({ text: "Something went wrong reaching the graph — try again in a moment." })
    } finally {
      setIsStreaming(false)
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <div className="flex h-full w-96 flex-shrink-0 flex-col border-l border-neutral-800 bg-neutral-950">
      <div className="border-b border-neutral-800 px-4 py-3">
        <h2 className="text-sm font-semibold text-neutral-100">Chat with the graph</h2>
        <p className="text-xs text-neutral-500">Grounded answers with clickable, graph-synced citations.</p>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <p className="text-sm text-neutral-500">Ask a question about what's in the graph.</p>
        )}
        {messages.map((message, i) => {
          if (message.role === 'user') {
            return (
              <div key={i} className="text-right">
                <div className="inline-block rounded-lg bg-blue-600/20 px-3 py-2 text-left text-sm text-blue-100">
                  {message.text}
                </div>
              </div>
            )
          }

          const isLast = i === messages.length - 1
          const stillStreaming = isStreaming && isLast
          const resolvable = message.citations ? new Set(Object.keys(message.citations.labels)) : undefined
          const { order } = parseAnswer(message.text, { isStreaming: stillStreaming, resolvable })

          return (
            <div key={i} className="text-left">
              <div className="inline-block rounded-lg bg-neutral-900 px-3 py-2 text-left text-sm text-neutral-100">
                {message.text ? (
                  <AnswerText
                    text={message.text}
                    isStreaming={stillStreaming}
                    resolvable={resolvable}
                    activeLabel={activeLabel}
                    onMarkerClick={(label) => handleMarkerClick(message.citations, label)}
                  />
                ) : (
                  stillStreaming && '…'
                )}
              </div>

              {message.citations && (
                <SourcesList
                  citations={message.citations}
                  order={order}
                  messageIndex={i}
                  activeLabel={activeLabel}
                  onShowOnGraph={() => focusNodes(message.citations!.entities)}
                />
              )}

              {message.citations && message.citations.entities.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {message.citations.entities.map((id) => {
                    const name = nodeById(id)?.name ?? entityNameFromLabels(message.citations!, id)
                    return (
                      <button
                        key={id}
                        onClick={() => focusNodes([id])}
                        className="rounded-full border border-neutral-700 px-2 py-0.5 text-xs text-neutral-400 hover:border-neutral-500 hover:text-neutral-200"
                      >
                        {name}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault()
          sendMessage()
        }}
        className="flex gap-2 border-t border-neutral-800 p-3"
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about the graph…"
          className="flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder:text-neutral-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
          disabled={isStreaming}
        />
        <button
          type="submit"
          disabled={isStreaming || !input.trim()}
          className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </div>
  )
}
