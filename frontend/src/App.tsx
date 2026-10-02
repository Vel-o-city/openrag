import { useEffect, useRef, useState } from 'react'
import { API_BASE } from './apiBase'
import { ChatPanel } from './ChatPanel'
import { ownDocumentIds } from './ownDocuments'
import { UploadPanel } from './UploadPanel'
import { SourceInspector, type OpenSource } from './SourceInspector'

export interface DocumentInfo {
  id: string
  filename: string
  page_count: number
  status: string
  is_seed: boolean
  chunk_count: number
}

export default function App() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [source, setSource] = useState<OpenSource | null>(null)
  const initialized = useRef(false)
  const catalogAbort = useRef<AbortController | null>(null)

  async function loadDocuments(uploadedId?: string) {
    catalogAbort.current?.abort()
    const controller = new AbortController()
    catalogAbort.current = controller
    setLoading(true)
    setError('')
    if (uploadedId) {
      setSelected([uploadedId])
      setSource(null)
      initialized.current = true
    }
    try {
      const params = new URLSearchParams()
      ownDocumentIds().forEach((id) => params.append('document_ids', id))
      const response = await fetch(`${API_BASE}/api/documents?${params}`, {
        signal: controller.signal,
      })
      if (!response.ok) throw new Error('unavailable')
      const items = (await response.json()) as DocumentInfo[]
      if (!Array.isArray(items)) throw new Error('invalid library')
      setDocuments(items)
      const ready = items.filter(
        (d) => ['done', 'partial'].includes(d.status) && d.chunk_count > 0,
      )
      const firstLoad = !initialized.current
      setSelected((prev) =>
        uploadedId
          ? [uploadedId]
          : firstLoad
            ? ready.filter((d) => d.is_seed).map((d) => d.id)
            : prev.filter((id) => ready.some((d) => d.id === id)),
      )
      initialized.current = true
      if (uploadedId) {
        setLibraryOpen(false)
        setSource(null)
      }
    } catch {
      if (!controller.signal.aborted)
        setError(
          'The document library is taking longer to connect. The demo server may be waking up.',
        )
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }
  useEffect(() => {
    void loadDocuments()
    return () => catalogAbort.current?.abort()
  }, [])
  function toggleDocument(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id],
    )
    setSource(null)
  }
  return (
    <div className="workspace">
      <header className="topbar">
        <a className="brand" href="/" aria-label="OpenRAG home">
          <span className="brand-mark">
            o<span>r</span>
          </span>
          OpenRAG<span className="brand-tag">DOCUMENT ASSISTANT</span>
        </a>
        <div className="topbar-actions">
          <span className="demo-tag">
            <i />
            Live portfolio demo
          </span>
          <a
            className="github-link"
            href="https://github.com/Vel-o-city/openrag"
            target="_blank"
            rel="noreferrer"
          >
            View code ↗
          </a>
        </div>
      </header>
      <div className="mobile-toolbar">
        <button onClick={() => setLibraryOpen(!libraryOpen)}>
          ☰ Documents <span>{selected.length}</span>
        </button>
        <span>Answers with sources</span>
      </div>
      {libraryOpen && (
        <button
          className="drawer-backdrop"
          aria-label="Close documents"
          onClick={() => setLibraryOpen(false)}
        />
      )}
      <aside className={`library ${libraryOpen ? 'library-open' : ''}`}>
        <div className="library-heading">
          <div>
            <span className="eyebrow">YOUR WORKSPACE</span>
            <h2>Documents</h2>
          </div>
          <button
            className="icon-button"
            title="Refresh documents"
            aria-label="Refresh documents"
            onClick={() => void loadDocuments()}
          >
            ↻
          </button>
        </div>
        <UploadPanel onComplete={(id) => loadDocuments(id)} />
        <div className="library-list">
          <div className="list-heading">
            <span>Choose your sources</span>
            <span>{selected.length} selected</span>
          </div>
          <p className="scope-note">
            Answers use only the selected files. Changing sources starts a new
            chat.
          </p>
          {loading && (
            <p className="library-notice" role="status">
              Connecting to your documents…
            </p>
          )}
          {error && (
            <div className="library-error" role="alert">
              {error}
              <button onClick={() => void loadDocuments()}>Try again</button>
            </div>
          )}
          {!loading && !error && documents.length === 0 && (
            <p className="library-notice">Upload a document to get started.</p>
          )}
          {(['uploads', 'samples'] as const).map((group) => {
            const items = documents.filter((d) =>
              group === 'samples' ? d.is_seed : !d.is_seed,
            )
            if (!items.length) return null
            return (
              <section key={group}>
                <h3 className="group-heading">
                  {group === 'samples' ? 'SAMPLE DOCUMENTS' : 'YOUR UPLOADS'}
                  <span>{items.length}</span>
                </h3>
                {items.map((doc) => {
                  const ready =
                    ['done', 'partial'].includes(doc.status) &&
                    doc.chunk_count > 0
                  return (
                    <label
                      key={doc.id}
                      className={`document-row ${selected.includes(doc.id) ? 'document-selected' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected.includes(doc.id)}
                        disabled={
                          !ready ||
                          (!selected.includes(doc.id) && selected.length >= 20)
                        }
                        onChange={() => toggleDocument(doc.id)}
                      />
                      <span className="file-icon">
                        {doc.filename.toLowerCase().endsWith('.pdf')
                          ? 'PDF'
                          : 'IMG'}
                      </span>
                      <span className="document-description">
                        <strong title={doc.filename}>
                          {doc.filename
                            .replace(/\.pdf$/i, '')
                            .replace(/_/g, ' ')}
                        </strong>
                        <small>
                          {doc.page_count}{' '}
                          {doc.page_count === 1 ? 'page' : 'pages'}{' '}
                          <span>·</span>{' '}
                          {doc.status === 'partial'
                            ? 'Some pages indexed'
                            : ready
                              ? 'Ready to ask'
                              : doc.status}
                        </small>
                      </span>
                    </label>
                  )
                })}
              </section>
            )
          })}
          {documents.some((d) => d.is_seed) && (
            <p className="sample-note">
              Samples describe fictional organizations. Try them before
              uploading a file.
            </p>
          )}
        </div>
        <div className="library-footer">
          <span>ⓘ</span>
          <p>
            This is a public demo. Upload only non-sensitive files. Documents
            may be removed as the demo fills up.
          </p>
        </div>
      </aside>
      <main className="main-panel">
        <ChatPanel
          key={[...selected].sort().join(',')}
          documents={documents.filter((d) => selected.includes(d.id))}
          loading={loading}
          onOpenSource={setSource}
        />
      </main>
      {source && (
        <SourceInspector source={source} onClose={() => setSource(null)} />
      )}
    </div>
  )
}
