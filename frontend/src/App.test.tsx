import { render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

// jsdom has no real canvas backend, and this component's only job here is to
// mount without crashing — the graph rendering itself isn't unit-test territory.
vi.mock('react-force-graph-2d', () => ({
  default: () => null,
}))

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        json: () => Promise.resolve({ nodes: [], edges: [], entities: 0, relationships: 0, documents: 0 }),
      }),
    )
  })

  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container.firstChild).not.toBeNull()
  })
})
