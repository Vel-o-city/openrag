import { useEffect, useRef, useState } from 'react'
import type { CitedChunk } from './citations'
import { isOwnDocument } from './ownDocuments'

interface SourceCardProps {
  chunk: CitedChunk
  n: number
  domId: string
  isActive: boolean
  onShowOnGraph: () => void
}

/**
 * One cited passage: which file, which page, and the text itself.
 *
 * Everything here except `n` is untrusted — it came out of a document a
 * stranger uploaded. It is rendered as React text children only (never
 * dangerouslySetInnerHTML), the filename is never a link, and the passage is
 * framed as a blockquote so it reads as quoted material rather than as
 * something the app is saying.
 */
export function SourceCard({ chunk, n, domId, isActive, onShowOnGraph }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  // Clicking the matching footnote opens this card and brings it into view.
  useEffect(() => {
    if (!isActive) return
    setExpanded(true)
    ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [isActive])

  const isOwn = isOwnDocument(chunk.document_id)

  return (
    <div
      ref={ref}
      id={domId}
      className={`rounded-md border bg-neutral-900/60 p-2 transition-colors ${
        isActive ? 'border-blue-500/60 ring-1 ring-blue-500/40' : 'border-neutral-800'
      }`}
    >
      <div className="flex items-baseline gap-1.5 text-xs">
        <span className="text-neutral-500">{n}.</span>
        <span className="min-w-0 flex-1 truncate font-medium text-neutral-300" title={chunk.filename}>
          {chunk.filename}
        </span>
        <span className="flex-shrink-0 text-neutral-500">page {chunk.page_number}</span>
      </div>

      {isOwn && (
        <span className="mt-1 inline-block rounded bg-blue-500/15 px-1.5 py-0.5 text-[0.65rem] font-medium text-blue-300">
          Your upload
        </span>
      )}

      <blockquote
        className={`mt-1.5 border-l-2 border-neutral-700 pl-2 text-xs italic text-neutral-400 ${
          expanded ? 'max-h-48 overflow-y-auto whitespace-pre-wrap break-words' : 'line-clamp-3'
        }`}
      >
        {chunk.text}
      </blockquote>

      <div className="mt-1.5 flex items-center gap-3 text-[0.65rem]">
        <button
          onClick={() => setExpanded((value) => !value)}
          className="text-neutral-500 underline hover:text-neutral-300"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
        <button onClick={onShowOnGraph} className="text-neutral-500 underline hover:text-neutral-300">
          Show on graph
        </button>
        {chunk.truncated && expanded && (
          <span className="text-neutral-600">clipped from {chunk.char_count.toLocaleString()} chars</span>
        )}
      </div>
    </div>
  )
}
