import { useState } from 'react'
import { HowItWorks } from './HowItWorks'

const REPO_URL = 'https://github.com/Vel-o-city/openrag'

/**
 * A visitor landing cold sees a force graph and a chat box with no explanation
 * of what either is for. The header carries the one-line pitch; "How it works"
 * carries the rest so the pitch stays short.
 */
export function AppHeader() {
  const [showHowItWorks, setShowHowItWorks] = useState(false)

  return (
    <>
      <header className="flex flex-shrink-0 items-center justify-between gap-3 border-b border-neutral-800 bg-neutral-950 px-4 py-2.5">
        <div className="min-w-0">
          <h1 className="text-sm font-semibold tracking-tight text-neutral-100">
            OpenRAG
            <span className="ml-2 hidden text-xs font-normal text-neutral-500 sm:inline">
              a knowledge graph you can see, extend, and chat with
            </span>
          </h1>
        </div>

        <div className="flex flex-shrink-0 items-center gap-1">
          <button
            onClick={() => setShowHowItWorks(true)}
            className="rounded-md px-2.5 py-1 text-xs text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"
          >
            How it works
          </button>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="rounded-md px-2.5 py-1 text-xs text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"
          >
            GitHub
          </a>
        </div>
      </header>

      {showHowItWorks && <HowItWorks onClose={() => setShowHowItWorks(false)} />}
    </>
  )
}
