import { ChatPanel } from './ChatPanel'
import { GraphExplorer } from './GraphExplorer'
import { GraphProvider } from './GraphContext'
import { StatStrip } from './StatStrip'

function App() {
  return (
    <GraphProvider>
      <div className="flex h-full w-full bg-neutral-950 text-neutral-100">
        <div className="relative min-w-0 flex-1">
          <GraphExplorer />
          <StatStrip />
        </div>
        <ChatPanel />
      </div>
    </GraphProvider>
  )
}

export default App
