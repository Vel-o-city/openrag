import { useEffect, useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

interface Stats {
  entities: number
  relationships: number
  documents: number
}

export function StatStrip() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/stats`)
      .then((res) => res.json())
      .then(setStats)
      .catch(() => setStats(null))
  }, [])

  if (!stats) return null

  return (
    <div className="pointer-events-none absolute left-4 top-4 rounded-full border border-neutral-800 bg-neutral-900/80 px-4 py-1.5 text-xs text-neutral-300 backdrop-blur">
      {stats.entities} nodes · {stats.relationships} edges · {stats.documents} document
      {stats.documents === 1 ? '' : 's'}
    </div>
  )
}
