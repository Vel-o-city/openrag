import { GraphExplorer } from './GraphExplorer'
import { StatStrip } from './StatStrip'

function App() {
  return (
    <div className="relative h-full w-full bg-neutral-950 text-neutral-100">
      <GraphExplorer />
      <StatStrip />
    </div>
  )
}

export default App
