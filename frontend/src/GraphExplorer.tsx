import { useEffect, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { useGraph, type GraphEdge, type GraphNode } from './GraphContext'

const ENTITY_TYPE_COLORS: Record<string, string> = {
  Person: '#f97316',
  Organization: '#38bdf8',
  Location: '#a3e635',
  Event: '#f472b6',
  Concept: '#c084fc',
  Other: '#94a3b8',
}

const DIMMED_NODE_COLOR = 'rgba(148, 163, 184, 0.15)'
const HIGHLIGHTED_LINK_COLOR = 'rgba(96, 165, 250, 0.9)'
const DIMMED_LINK_COLOR = 'rgba(148, 163, 184, 0.08)'
const DEFAULT_LINK_COLOR = 'rgba(148, 163, 184, 0.35)'

function endpointId(end: string | GraphNode): string {
  return typeof end === 'string' ? end : end.id
}

export function GraphExplorer() {
  const { nodes, edges, focusedIds, focusNodes } = useGraph()
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphEdge> | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ width, height })
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (focusedIds.size === 0) return
    // Let the graph's simulation settle a beat before measuring node
    // positions for zoomToFit, or it fits against stale coordinates.
    const timeout = setTimeout(() => {
      fgRef.current?.zoomToFit(600, 120, (node) => focusedIds.has((node as GraphNode).id))
    }, 50)
    return () => clearTimeout(timeout)
  }, [focusedIds])

  const isDimmed = (id: string) => focusedIds.size > 0 && !focusedIds.has(id)
  const isCitedLink = (link: GraphEdge) =>
    focusedIds.has(endpointId(link.source)) && focusedIds.has(endpointId(link.target))

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <ForceGraph2D
        ref={fgRef}
        width={size.width}
        height={size.height}
        graphData={{ nodes, links: edges.map((edge) => ({ ...edge })) }}
        backgroundColor="#0a0a0a"
        nodeLabel={(node) => `${(node as GraphNode).name} (${(node as GraphNode).entity_type})`}
        nodeColor={(node) => {
          const n = node as GraphNode
          if (isDimmed(n.id)) return DIMMED_NODE_COLOR
          return ENTITY_TYPE_COLORS[n.entity_type] ?? '#94a3b8'
        }}
        nodeRelSize={5}
        linkLabel={(link) => (link as GraphEdge).predicate}
        linkColor={(link) => {
          const l = link as GraphEdge
          if (focusedIds.size === 0) return DEFAULT_LINK_COLOR
          return isCitedLink(l) ? HIGHLIGHTED_LINK_COLOR : DIMMED_LINK_COLOR
        }}
        linkWidth={(link) => (isCitedLink(link as GraphEdge) ? 2 : 1)}
        linkDirectionalParticles={(link) => (isCitedLink(link as GraphEdge) ? 4 : 0)}
        linkDirectionalParticleWidth={3}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        onNodeClick={(node) => {
          const n = node as GraphNode
          setSelected(n)
          focusNodes([n.id])
        }}
        onBackgroundClick={() => setSelected(null)}
      />

      {selected && (
        <div className="absolute right-4 top-4 w-72 rounded-lg border border-neutral-800 bg-neutral-900/95 p-4 text-neutral-100 shadow-xl">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-xs uppercase tracking-wide text-neutral-500">{selected.entity_type}</p>
              <h3 className="text-sm font-semibold">{selected.name}</h3>
            </div>
            <button
              className="text-neutral-500 hover:text-neutral-300"
              onClick={() => setSelected(null)}
            >
              ✕
            </button>
          </div>
          <p className="mt-2 text-sm text-neutral-400">{selected.description}</p>
          <p className="mt-2 text-xs text-neutral-600">{selected.mention_count} mention(s)</p>
        </div>
      )}
    </div>
  )
}
