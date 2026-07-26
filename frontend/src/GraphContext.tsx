import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { API_BASE } from './apiBase'

const NEW_NODE_HIGHLIGHT_MS = 4000

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
  newNodeIds: Set<string>
  refreshGraph: () => Promise<void>
}

const GraphContext = createContext<GraphContextValue | null>(null)

async function fetchGraph(): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const res = await fetch(`${API_BASE}/api/graph?limit=1000`)
  const json = await res.json()
  return { nodes: json.nodes ?? [], edges: json.edges ?? [] }
}

/**
 * Fetches the graph once and lifts it — along with the "currently focused"
 * node-id set — to app level. Node click, chat citations, and upload
 * completion all just call focusNodes()/refreshGraph(); this is the one
 * place that decides what's highlighted.
 */
export function GraphProvider({ children }: { children: ReactNode }) {
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [edges, setEdges] = useState<GraphEdge[]>([])
  const [focusedIds, setFocusedIds] = useState<Set<string>>(new Set())
  const [newNodeIds, setNewNodeIds] = useState<Set<string>>(new Set())
  const nodesRef = useRef<GraphNode[]>([])

  useEffect(() => {
    nodesRef.current = nodes
  }, [nodes])

  useEffect(() => {
    fetchGraph()
      .then(({ nodes, edges }) => {
        setNodes(nodes)
        setEdges(edges)
      })
      .catch(() => {
        setNodes([])
        setEdges([])
      })
  }, [])

  const refreshGraph = useCallback(async () => {
    const previousIds = new Set(nodesRef.current.map((node) => node.id))
    const { nodes: freshNodes, edges: freshEdges } = await fetchGraph()

    setNodes(freshNodes)
    setEdges(freshEdges)

    const addedIds = freshNodes.filter((node) => !previousIds.has(node.id)).map((node) => node.id)
    if (addedIds.length > 0) {
      setNewNodeIds(new Set(addedIds))
      setTimeout(() => setNewNodeIds(new Set()), NEW_NODE_HIGHLIGHT_MS)
    }
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
      newNodeIds,
      refreshGraph,
    }),
    [nodes, edges, focusedIds, nodesById, newNodeIds, refreshGraph],
  )

  return <GraphContext.Provider value={value}>{children}</GraphContext.Provider>
}

export function useGraph(): GraphContextValue {
  const ctx = useContext(GraphContext)
  if (!ctx) throw new Error('useGraph must be used within a GraphProvider')
  return ctx
}
