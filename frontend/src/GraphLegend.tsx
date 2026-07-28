import { useState } from 'react'
import { ENTITY_TYPE_COLORS } from './entityColors'

/**
 * Without this the node colours mean nothing to a visitor. Sits bottom-right:
 * the stats pill holds top-left, the upload panel bottom-left, and the node
 * detail card top-right.
 */
export function GraphLegend() {
  const [expanded, setExpanded] = useState(false)
  const types = Object.entries(ENTITY_TYPE_COLORS)

  return (
    <div className="absolute bottom-4 right-4 rounded-lg border border-neutral-800 bg-neutral-900/80 px-3 py-2 backdrop-blur">
      <button
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 text-[0.65rem] uppercase tracking-wide text-neutral-500 hover:text-neutral-300"
        aria-expanded={expanded}
      >
        <span className="hidden sm:inline">Entity types</span>
        <span className="flex gap-1 sm:hidden">
          {types.map(([type, color]) => (
            <span
              key={type}
              className="h-2 w-2 rounded-full"
              style={{ backgroundColor: color }}
              title={type}
            />
          ))}
        </span>
        <span className="hidden sm:inline">{expanded ? '−' : '+'}</span>
      </button>

      <ul className={`mt-1.5 gap-x-3 gap-y-1 ${expanded ? 'grid grid-cols-2' : 'hidden sm:grid sm:grid-cols-2'}`}>
        {types.map(([type, color]) => (
          <li key={type} className="flex items-center gap-1.5 text-[0.7rem] text-neutral-400">
            <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
            {type}
          </li>
        ))}
      </ul>
    </div>
  )
}
