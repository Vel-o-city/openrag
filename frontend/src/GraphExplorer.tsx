import { useEffect, useRef, useState } from 'react'
import ForceGraph2D, { type ForceGraphMethods, type NodeObject, type LinkObject } from 'react-force-graph-2d'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const ENTITY_TYPE_COLORS: Record<string, string> = {
  Person: '#f97316',
  Organization: '#38bdf8',
  Location: '#a3e635',
  Event: '#f472b6',
  Concept: '#c084fc',
  Other: '#94a3b8',
}

interface GraphNode extends NodeObject {
  id: string
  name: string
  entity_type: string
  description: string
  mention_count: number
}

interface GraphEdge extends LinkObject {
  source: string
  target: string
  predicate: string
  description: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export function GraphExplorer() {
  const [data, setData] = useState<GraphData>({ nodes: [], edges: [] })
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const fgRef = useRef<ForceGraphMethods<GraphNode, GraphEdge> | undefined>(undefined)

  useEffect(() => {
    fetch(`${API_BASE}/api/graph?limit=1000`)
      .then((res) => res.json())
      .then((json) => setData({ nodes: json.nodes, edges: json.edges }))
      .catch(() => setData({ nodes: [], edges: [] }))
  }, [])

  return (
    <div className="relative h-full w-full">
      <ForceGraph2D
        ref={fgRef}
        graphData={{
          nodes: data.nodes,
          links: data.edges.map((e) => ({ ...e, source: e.source, target: e.target })),
        }}
        backgroundColor="#0a0a0a"
        nodeLabel={(node) => `${(node as GraphNode).name} (${(node as GraphNode).entity_type})`}
        nodeColor={(node) => ENTITY_TYPE_COLORS[(node as GraphNode).entity_type] ?? '#94a3b8'}
        nodeRelSize={5}
        linkLabel={(link) => (link as GraphEdge).predicate}
        linkColor={() => 'rgba(148, 163, 184, 0.35)'}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        onNodeClick={(node) => {
          setSelected(node as GraphNode)
          fgRef.current?.centerAt((node.x ?? 0), (node.y ?? 0), 600)
          fgRef.current?.zoom(4, 600)
        }}
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
