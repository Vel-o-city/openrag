import { useEffect, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods } from 'react-force-graph-2d'
import { colorForEntityType } from './entityColors'
import { useGraph, type GraphEdge, type GraphNode } from './GraphContext'

const DIMMED_NODE_COLOR = 'rgba(148, 163, 184, 0.15)'
const HIGHLIGHTED_LINK_COLOR = 'rgba(96, 165, 250, 0.9)'
const DIMMED_LINK_COLOR = 'rgba(148, 163, 184, 0.08)'
const DEFAULT_LINK_COLOR = 'rgba(148, 163, 184, 0.35)'
const NEW_NODE_RING_COLOR = 'rgba(250, 204, 21, 0.9)'

const FOCUS_PADDING = 120
/** Focusing one node has no extent to fit, so cap how far in the camera goes. */
const MAX_FOCUS_ZOOM = 2.5
const FOCUS_ANIMATION_MS = 600

function endpointId(end: string | GraphNode): string {
  return typeof end === 'string' ? end : end.id
}

/** The simulation writes x/y onto the node objects it was handed. */
type PositionedNode = GraphNode & { x?: number; y?: number }

function isPositioned(node: PositionedNode): node is GraphNode & { x: number; y: number } {
  return typeof node.x === 'number' && typeof node.y === 'number'
}

export function GraphExplorer() {
  const { nodes, edges, focusedIds, focusNodes, newNodeIds } = useGraph()
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphEdge> | undefined>(undefined)
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      // On mobile the inactive pane is display:none, which reports 0x0.
      // Feeding that to the canvas throws away the simulation's layout, so
      // hold the last real size until the pane is visible again.
      if (width === 0 || height === 0) return
      setSize({ width, height })
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (focusedIds.size === 0) return
    // Let the graph's simulation settle a beat before measuring node
    // positions, or the camera fits against stale coordinates.
    const timeout = setTimeout(() => {
      const fg = fgRef.current
      if (!fg) return

      const focused = (nodes as PositionedNode[]).filter(
        (node) => focusedIds.has(node.id) && isPositioned(node),
      ) as (GraphNode & { x: number; y: number })[]
      if (focused.length === 0) return

      const xs = focused.map((node) => node.x)
      const ys = focused.map((node) => node.y)
      const [minX, maxX] = [Math.min(...xs), Math.max(...xs)]
      const [minY, maxY] = [Math.min(...ys), Math.max(...ys)]

      // Computing the fit ourselves rather than calling zoomToFit lets the
      // ceiling apply to the animation's target. zoomToFit would animate all
      // the way in on a single node and then need yanking back out.
      const availableWidth = Math.max(size.width - FOCUS_PADDING * 2, 1)
      const availableHeight = Math.max(size.height - FOCUS_PADDING * 2, 1)
      const fitZoom = Math.min(
        availableWidth / Math.max(maxX - minX, 1),
        availableHeight / Math.max(maxY - minY, 1),
      )

      fg.centerAt((minX + maxX) / 2, (minY + maxY) / 2, FOCUS_ANIMATION_MS)
      fg.zoom(Math.min(fitZoom, MAX_FOCUS_ZOOM), FOCUS_ANIMATION_MS)
    }, 50)
    return () => clearTimeout(timeout)
  }, [focusedIds, nodes, size.width, size.height])

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
          return colorForEntityType(n.entity_type)
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
        nodeCanvasObjectMode={() => 'after'}
        nodeCanvasObject={(node, ctx) => {
          const n = node as GraphNode & { x?: number; y?: number }
          if (!newNodeIds.has(n.id) || n.x === undefined || n.y === undefined) return
          ctx.beginPath()
          ctx.arc(n.x, n.y, 9, 0, 2 * Math.PI)
          ctx.strokeStyle = NEW_NODE_RING_COLOR
          ctx.lineWidth = 2
          ctx.stroke()
        }}
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
