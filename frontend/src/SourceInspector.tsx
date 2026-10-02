import { useEffect, useState } from 'react'
import { API_BASE } from './apiBase'
import type { CitedChunk } from './citations'

export interface OpenSource {
  chunk: CitedChunk
  number: number | null
  originalUrl?: string
  title?: string
}
export function SourceInspector({
  source,
  onClose,
}: {
  source: OpenSource
  onClose: () => void
}) {
  const [text, setText] = useState(source.chunk.text)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const abort = new AbortController()
    setText(source.chunk.text)
    setError('')
    setLoading(true)
    void fetch(
      `${API_BASE}/api/documents/${encodeURIComponent(source.chunk.document_id)}/chunks/${encodeURIComponent(source.chunk.id)}`,
      { signal: abort.signal },
    )
      .then(async (response) => {
        if (!response.ok) throw new Error()
        const passage = await response.json()
        setText(passage.text)
      })
      .catch(() => {
        if (!abort.signal.aborted)
          setError(
            'The full passage could not be loaded. The answer’s saved excerpt is shown below.',
          )
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false)
      })
    return () => abort.abort()
  }, [source.chunk])
  useEffect(() => {
    function escape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [onClose])
  return (
    <>
      <button
        className="source-backdrop"
        aria-label="Close source passage"
        onClick={onClose}
      />
      <aside
        className="source-inspector"
        aria-label="Source passage"
        role="dialog"
        aria-modal="true"
        onKeyDown={(e) => {
          if (e.key !== 'Tab') return
          const controls =
            e.currentTarget.querySelectorAll<HTMLElement>('button, a[href]')
          const first = controls[0]
          const last = controls[controls.length - 1]
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault()
            last.focus()
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault()
            first.focus()
          }
        }}
      >
        <div className="inspector-heading">
          <span className="eyebrow">CHECK THE EVIDENCE</span>
          <button
            autoFocus
            className="icon-button"
            aria-label="Close source"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <h2>{source.number ? `Source ${source.number}` : 'Related passage'}</h2>
        <div className="inspector-document">
          <span className="file-icon">FILE</span>
          <div>
            <strong>{source.title || source.chunk.filename}</strong>
            <small>Page {source.chunk.page_number}</small>
          </div>
        </div>

        {source.originalUrl && (
          <a
            className="original-source-link"
            href={`${source.originalUrl}#page=${source.chunk.page_number}`}
            target="_blank"
            rel="noreferrer"
          >
            Verify page {source.chunk.page_number} in the official PDF ↗
          </a>
        )}
        <div className="passage-label">
          <span>EXTRACTED SOURCE PASSAGE</span>
          {loading && <span role="status">Loading…</span>}
        </div>
        {error && <p className="answer-error">{error}</p>}
        <blockquote className="full-passage">{text}</blockquote>
        <p className="inspector-note">
          This is text extracted from the document, including OCR for scanned
          pages. Check the original file when formatting or transcription
          matters.
        </p>
      </aside>
    </>
  )
}
