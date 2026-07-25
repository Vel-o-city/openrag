import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement ResizeObserver; GraphExplorer uses one to size the
// force-graph canvas to its container.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as unknown as { ResizeObserver: typeof ResizeObserverStub }).ResizeObserver = ResizeObserverStub
