import { useEffect, useRef, useState } from 'react'
import { AnswerText } from './AnswerText'
import { API_BASE } from './apiBase'
import { parseAnswer, type Citations } from './citations'
import { streamSSE } from './sse'
import type { DocumentInfo } from './App'
import type { OpenSource } from './SourceInspector'

interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
  citations?: Citations
  error?: string
}
interface Props {
  documents: DocumentInfo[]
  loading: boolean
  onOpenSource: (source: OpenSource) => void
}

export function ChatPanel({ documents, loading, onOpenSource }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [activeSource, setActiveSource] = useState('')
  const controller = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => () => controller.current?.abort(), [])
  useEffect(() => {
    if (messages.length)
      bottom.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [messages])
  const hasDeclaration =
    documents.length === 1 &&
    documents[0].is_seed &&
    documents[0].filename === 'universal-declaration-of-human-rights.pdf'
  const suggestions = hasDeclaration
    ? [
        'What does Article 1 say about equality?',
        'What does Article 26 say about the right to education?',
        'Which article protects freedom of opinion and expression?',
      ]
    : [
        'Summarize the key points of this document.',
        'What deadlines or commitments are mentioned?',
        'What does this document say about its main topic?',
      ]
  function updateLast(patch: Partial<ChatMessage>) {
    setMessages((prev) =>
      prev.map((m, index) =>
        index === prev.length - 1 ? { ...m, ...patch } : m,
      ),
    )
  }
  function openCitation(
    citations: Citations,
    label: string,
    number: number | null,
  ) {
    const chunk = citations.chunks.find((c) => c.label === label)
    if (chunk) {
      setActiveSource(chunk.id)
      const document = documents.find((d) => d.id === chunk.document_id)
      onOpenSource({
        chunk,
        number,
        originalUrl: document?.source_url,
        title: document?.title,
      })
    }
  }
  async function sendMessage(question = input.trim(), conversation = messages) {
    if (!question || streaming || !documents.length || loading) return
    const abort = new AbortController()
    controller.current = abort
    const history = conversation
      .filter((m) => m.text && !m.error)
      .slice(-8)
      .map((m) => ({ role: m.role, text: m.text.slice(0, 4000) }))
    setInput('')
    setMessages([
      ...conversation,
      { role: 'user', text: question },
      { role: 'assistant', text: '' },
    ])
    setStreaming(true)
    let text = ''
    let completed = false
    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abort.signal,
        body: JSON.stringify({
          message: question,
          document_ids: documents.map((d) => d.id),
          history,
        }),
      })
      if (response.status === 429)
        throw new Error(
          'The demo chat limit has been reached. Please try again later.',
        )
      if (!response.ok)
        throw new Error('Could not start an answer. Please try again.')
      for await (const event of streamSSE(response)) {
        if (event.event === 'reset') {
          text = ''
          updateLast({ text: '', citations: undefined, error: undefined })
        }
        if (event.event === 'token') {
          text += JSON.parse(event.data).text
          updateLast({ text })
        }
        if (event.event === 'citations')
          updateLast({ citations: JSON.parse(event.data) })
        if (event.event === 'error')
          updateLast({ error: JSON.parse(event.data).message })
        if (event.event === 'done') completed = true
      }
      if (!completed)
        throw new Error(
          'The connection closed before the answer finished. Please try again.',
        )
    } catch (error) {
      updateLast({
        error: abort.signal.aborted
          ? 'Answer stopped.'
          : error instanceof Error
            ? error.message
            : 'Could not connect to the server. Please try again.',
      })
    } finally {
      setStreaming(false)
    }
  }
  return (
    <div className="chat-panel">
      <div className="chat-heading">
        <div>
          <span className="eyebrow">DOCUMENT Q&A</span>
          <h1>Ask. Understand. Verify.</h1>
        </div>
        <div className="scope-badge">
          <i />
          {documents.length
            ? `${documents.length} ${documents.length === 1 ? 'source' : 'sources'} selected`
            : 'Select a source'}
        </div>
      </div>
      <div className="conversation">
        {messages.length === 0 && (
          <div className="welcome">
            <div className="welcome-icon">
              <span>▤</span>
              <i>✦</i>
            </div>
            <span className="eyebrow">FROM DOCUMENTS TO ANSWERS</span>
            <h2>
              Your documents,
              <br />
              <span>with the answers inside.</span>
            </h2>
            <p>
              {hasDeclaration ? (
                <>
                  The Universal Declaration of Human Rights is already loaded.
                  <br className="desktop-break" /> Ask a question and check the
                  official UN source.
                </>
              ) : (
                <>
                  Upload a file, ask a question, and trace the answer
                  <br className="desktop-break" /> back to the exact source
                  passage.
                </>
              )}
            </p>
            <div className="welcome-steps">
              <span>
                <b>1</b>Choose documents
              </span>
              <span>
                <b>2</b>Ask a question
              </span>
              <span>
                <b>3</b>Check the citations
              </span>
            </div>
            <div className="suggestions">
              <span className="eyebrow">
                {hasDeclaration
                  ? 'TRY IT NOW · NO UPLOAD NEEDED'
                  : 'TRY A QUESTION'}
              </span>
              {suggestions.map((question, i) => (
                <button
                  key={question}
                  aria-label={question}
                  disabled={!documents.length || loading}
                  onClick={() => void sendMessage(question)}
                >
                  <span className="suggestion-icon">{['✧', '⌁', '≡'][i]}</span>
                  <span>{question}</span>
                  <span className="suggestion-arrow">↗</span>
                </button>
              ))}
            </div>
            {!documents.length && !loading && (
              <p className="selection-hint">
                Choose a ready document in the library to begin.
              </p>
            )}
          </div>
        )}
        <div className="message-list">
          {messages.map((message, index) => {
            if (message.role === 'user')
              return (
                <div key={index} className="user-message">
                  <div>{message.text}</div>
                  <span className="user-avatar">You</span>
                </div>
              )
            const live = streaming && index === messages.length - 1
            const citations = message.citations
            const resolvable = citations
              ? new Set(Object.keys(citations.labels))
              : live
                ? undefined
                : new Set<string>()
            const { order } = parseAnswer(message.text, {
              isStreaming: live,
              resolvable,
            })
            const chunks = citations
              ? [...citations.chunks].sort(
                  (a, b) =>
                    (order.indexOf(a.label) < 0
                      ? 999
                      : order.indexOf(a.label)) -
                    (order.indexOf(b.label) < 0 ? 999 : order.indexOf(b.label)),
                )
              : []
            return (
              <article className="assistant-message" key={index}>
                <span className="assistant-avatar">or</span>
                <div className="assistant-body">
                  <div className="answer-byline">
                    OpenRAG{' '}
                    <span>
                      {live ? 'Reading your sources…' : 'Document assistant'}
                    </span>
                  </div>
                  {message.text ? (
                    <div className="answer-content">
                      <AnswerText
                        text={message.text}
                        isStreaming={live}
                        resolvable={resolvable}
                        activeLabel={
                          citations?.chunks.find((c) => c.id === activeSource)
                            ?.label ?? null
                        }
                        onMarkerClick={(label) =>
                          citations &&
                          openCitation(
                            citations,
                            label,
                            order.indexOf(label) + 1,
                          )
                        }
                      />
                    </div>
                  ) : (
                    live && (
                      <div className="thinking" role="status">
                        <i />
                        <i />
                        <i />
                        <span>Finding relevant passages</span>
                      </div>
                    )
                  )}
                  {message.error && (
                    <div className="answer-error" role="alert">
                      {message.error}
                      {!streaming &&
                        index === messages.length - 1 &&
                        messages[index - 1]?.role === 'user' && (
                          <button
                            className="retry-answer"
                            onClick={() =>
                              void sendMessage(
                                messages[index - 1].text,
                                messages.slice(0, index - 1),
                              )
                            }
                          >
                            Retry answer ↻
                          </button>
                        )}
                    </div>
                  )}
                  {!!chunks.length && (
                    <div className="answer-sources">
                      <div className="sources-heading">
                        <span>
                          {citations?.precise
                            ? 'SOURCES'
                            : 'RELATED PASSAGES · NO PRECISE CITATIONS'}
                        </span>
                        <span>Click to verify ↗</span>
                      </div>
                      <div className="source-cards">
                        {chunks.map((chunk) => (
                          <button
                            key={chunk.id}
                            aria-label={`${order.includes(chunk.label) ? `Open source ${order.indexOf(chunk.label) + 1}` : 'Open related passage'}: ${chunk.filename}, page ${chunk.page_number}`}
                            className={`source-card ${activeSource === chunk.id ? 'source-active' : ''}`}
                            onClick={() =>
                              openCitation(
                                citations!,
                                chunk.label,
                                order.indexOf(chunk.label) >= 0
                                  ? order.indexOf(chunk.label) + 1
                                  : null,
                              )
                            }
                          >
                            <span className="source-card-top">
                              <b>
                                {order.indexOf(chunk.label) >= 0
                                  ? order.indexOf(chunk.label) + 1
                                  : '↗'}
                              </b>
                              <strong>{chunk.filename}</strong>
                              <small>p. {chunk.page_number}</small>
                            </span>
                            <span className="source-preview">
                              “{chunk.text.slice(0, 130)}
                              {chunk.text.length > 130 ? '…' : ''}”
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {citations?.flagged_urls?.length ? (
                    <p className="answer-error">
                      Links in this answer were not found in the source
                      passages. Verify them independently.
                    </p>
                  ) : null}
                </div>
              </article>
            )
          })}
          <div ref={bottom} />
        </div>
      </div>
      <div className="composer-wrap">
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault()
            void sendMessage()
          }}
        >
          <textarea
            aria-label="Ask about your documents"
            placeholder={
              documents.length
                ? 'Ask anything about your documents…'
                : 'Select a document to start asking questions…'
            }
            rows={1}
            maxLength={4000}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={streaming || !documents.length || loading}
            onKeyDown={(e) => {
              if (
                e.key === 'Enter' &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault()
                void sendMessage()
              }
            }}
          />
          {streaming ? (
            <button
              type="button"
              aria-label="Stop answer"
              className="send-button"
              onClick={() => controller.current?.abort()}
            >
              ■
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Send question"
              className="send-button"
              disabled={!input.trim() || !documents.length || loading}
            >
              ↑
            </button>
          )}
        </form>
        <p className="composer-note">
          Grounded in your selected documents. Click a citation to check the
          evidence.
        </p>
      </div>
    </div>
  )
}
