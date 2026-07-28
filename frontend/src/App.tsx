import { useState } from 'react'
import { AppHeader } from './AppHeader'
import { ChatPanel } from './ChatPanel'
import { GraphExplorer } from './GraphExplorer'
import { GraphLegend } from './GraphLegend'
import { GraphProvider } from './GraphContext'
import { StatStrip } from './StatStrip'
import { UploadPanel } from './UploadPanel'

type MobileTab = 'graph' | 'chat'

function App() {
  const [mobileTab, setMobileTab] = useState<MobileTab>('graph')

  // Both panes stay mounted at every width — the graph simulation and the chat
  // history are expensive to rebuild, so mobile hides the inactive one rather
  // than unmounting it. GraphExplorer holds its last size while hidden, since
  // a display:none pane measures 0x0.

  return (
    <GraphProvider>
      <div className="flex h-full w-full flex-col bg-neutral-950 text-neutral-100">
        <AppHeader />

        <nav className="flex flex-shrink-0 border-b border-neutral-800 md:hidden">
          {(['graph', 'chat'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setMobileTab(tab)}
              aria-current={mobileTab === tab}
              className={`flex-1 py-2 text-xs capitalize ${
                mobileTab === tab
                  ? 'border-b-2 border-blue-500 font-medium text-neutral-100'
                  : 'text-neutral-500'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>

        <div className="flex min-h-0 flex-1">
          <div
            className={`relative min-w-0 flex-1 md:block ${
              mobileTab === 'graph' ? 'block' : 'hidden'
            }`}
          >
            <GraphExplorer />
            <StatStrip />
            <GraphLegend />
            <UploadPanel />
          </div>

          <div
            className={`min-h-0 w-full flex-shrink-0 border-neutral-800 md:flex md:w-96 md:border-l ${
              mobileTab === 'chat' ? 'flex' : 'hidden'
            }`}
          >
            <ChatPanel />
          </div>
        </div>
      </div>
    </GraphProvider>
  )
}

export default App
