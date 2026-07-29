import { useEffect, useState } from 'react'
import { HOW_IT_WORKS_HASH, HowItWorks } from './HowItWorks'

const REPO_URL = 'https://github.com/Vel-o-city/openrag'

/**
 * A visitor landing cold sees a force graph and a chat box with no explanation
 * of what either is for. The header carries the pitch; "How it works" carries
 * the rest so the pitch stays one line.
 */
export function AppHeader() {
  const [showHowItWorks, setShowHowItWorks] = useState(
    () => window.location.hash === HOW_IT_WORKS_HASH,
  )

  // Deep-linkable so the explainer can be sent straight to someone, and so
  // back/forward behave once it's open.
  useEffect(() => {
    const sync = () => setShowHowItWorks(window.location.hash === HOW_IT_WORKS_HASH)
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  function close() {
    setShowHowItWorks(false)
    if (window.location.hash === HOW_IT_WORKS_HASH) {
      history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }

  return (
    <>
      <header className="flex h-12 flex-shrink-0 items-center justify-between gap-3 border-b border-neutral-800 bg-neutral-950 px-4 md:h-14">
        <div className="flex min-w-0 items-baseline gap-2">
          <h1 className="text-sm font-semibold tracking-tight text-neutral-100">OpenRAG</h1>
          <p className="hidden truncate text-xs text-neutral-500 sm:block">
            A public knowledge graph built live from documents visitors upload — every answer cites
            the page it came from.
          </p>
        </div>

        <div className="flex flex-shrink-0 items-center gap-1">
          <a
            href={HOW_IT_WORKS_HASH}
            onClick={() => setShowHowItWorks(true)}
            className="rounded-md px-2.5 py-1 text-xs text-neutral-400 hover:bg-neutral-900 hover:text-neutral-100"
          >
            How it works
          </a>
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

      {showHowItWorks && <HowItWorks onClose={close} />}
    </>
  )
}
