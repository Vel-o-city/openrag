import type { Citations } from './citations'
import { SourceCard } from './SourceCard'

interface SourcesListProps {
  citations: Citations
  /** Cited labels in order of first appearance in the answer prose. */
  order: string[]
  messageIndex: number
  activeLabel: string | null
  onShowOnGraph: (chunkLabel: string) => void
}

export function sourceCardDomId(messageIndex: number, label: string): string {
  return `cite-${messageIndex}-${label}`
}

/**
 * The sources under an answer. Chunks referenced inline come first, in
 * footnote order; anything retrieved but never pointed at follows below a
 * divider, so the numbering never implies a marker that isn't in the prose.
 */
export function SourcesList({
  citations,
  order,
  messageIndex,
  activeLabel,
  onShowOnGraph,
}: SourcesListProps) {
  if (citations.chunks.length === 0) return null

  const byLabel = new Map(citations.chunks.map((chunk) => [chunk.label, chunk]))
  const referenced = order.map((label) => byLabel.get(label)).filter((chunk) => chunk !== undefined)
  const referencedLabels = new Set(referenced.map((chunk) => chunk.label))
  const unreferenced = citations.chunks.filter((chunk) => !referencedLabels.has(chunk.label))

  return (
    <div className="mt-2 space-y-1.5">
      <p className="text-[0.65rem] uppercase tracking-wide text-neutral-600">
        {citations.precise ? 'Sources' : 'Retrieved context'}
      </p>

      {referenced.map((chunk, i) => (
        <SourceCard
          key={chunk.id}
          chunk={chunk}
          n={i + 1}
          domId={sourceCardDomId(messageIndex, chunk.label)}
          isActive={activeLabel === chunk.label}
          onShowOnGraph={() => onShowOnGraph(chunk.label)}
        />
      ))}

      {unreferenced.length > 0 && (
        <>
          {referenced.length > 0 && (
            <p className="pt-1 text-[0.65rem] text-neutral-600">Also retrieved</p>
          )}
          {unreferenced.map((chunk, i) => (
            <SourceCard
              key={chunk.id}
              chunk={chunk}
              n={referenced.length + i + 1}
              domId={sourceCardDomId(messageIndex, chunk.label)}
              isActive={activeLabel === chunk.label}
              onShowOnGraph={() => onShowOnGraph(chunk.label)}
            />
          ))}
        </>
      )}
    </div>
  )
}
