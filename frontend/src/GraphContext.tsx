import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface GraphNode {
  id: string
  name: string
  entity_type: string
  description: string
  mention_count: number
}

export interface GraphEdge {
  source: string
  target: string
  predicate: string
  description: string
}

interface GraphContextValue {
  nodes: GraphNode[]
  edges: GraphEdge[]
  focusedIds: Set<string>
  focusNodes: (ids: string[]) => void
  clearFocus: () => void
  nodeById: (id: string) => GraphNode | undefined
}

const GraphContext = createContext<GraphContextValue | null>(null)

/**
 * Fetches the graph once and lifts it — along with the "currently focused"
 * node-id set — to app level. Node click, chat citations, and (eventually)
 * upload completion all just call focusNodes(); this is the one place that
 * decides what's highlighted.
 */
export function GraphProvider({ children }: { children: ReactNode }) {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [focusedIds, setFocusedIds] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetch(`${API_BASE}/api/graph?limit=1000`)
      .then((res) => res.json())
      .then((json) => {
        setNodes(json.nodes ?? [])
        setEdges(json.edges ?? [])
      })
      .catch(() => {
        setNodes([])
        setEdges([])
      })
  }, [])

  const nodesById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes])

  const value = useMemo<GraphContextValue>(
    () => ({
      nodes,
      edges,
      focusedIds,
      focusNodes: (ids: string[]) => setFocusedIds(new Set(ids)),
      clearFocus: () => setFocusedIds(new Set()),
      nodeById: (id: string) => nodesById.get(id),
    }),
    [nodes, edges, focusedIds, nodesById],
  )

  return <GraphContext.Provider value={value}>{children}</GraphContext.Provider>
}

export function useGraph(): GraphContextValue {
  const ctx = useContext(GraphContext)
  if (!ctx) throw new Error('useGraph must be used within a GraphProvider')
  return ctx
}
