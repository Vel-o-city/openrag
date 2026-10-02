import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from './App'

const documents = ['a', 'b'].map((id) => ({
  id: `doc-${id}`,
  filename: `plan-${id}.pdf`,
  page_count: 1,
  status: 'done',
  is_seed: true,
  chunk_count: 1,
}))
const chunk = {
  id: 'chunk-a',
  label: 'C1',
  text: 'An excerpt.',
  truncated: true,
  char_count: 40,
  page_number: 1,
  document_id: 'doc-a',
  filename: 'plan-a.pdf',
}
const citations = {
  entities: [],
  relationships: [],
  chunks: [chunk],
  documents: [],
  labels: { C1: { kind: 'chunk', id: 'chunk-a', name: null } },
  precise: true,
  flagged_urls: [],
}
const fetch = vi.fn()
beforeEach(() => {
  localStorage.clear()
  fetch.mockReset().mockImplementation((url: string) => {
    if (url.includes('/chunks/'))
      return Promise.resolve(
        new Response(
          JSON.stringify({
            text: 'The complete passage from the selected document.',
          }),
        ),
      )
    if (url.includes('/api/chat'))
      return Promise.resolve(
        new Response(
          `event: token\ndata: {"text":"A grounded answer [C1]."}\n\nevent: citations\ndata: ${JSON.stringify(citations)}\n\nevent: done\ndata: {}\n\n`,
        ),
      )
    return Promise.resolve(new Response(JSON.stringify(documents)))
  })
  vi.stubGlobal('fetch', fetch)
})
afterEach(() => vi.unstubAllGlobals())
it('selects sample files, clears conversation when scope changes, and sends only selected IDs', async () => {
  render(<App />)
  const checkboxes = await screen.findAllByRole('checkbox')
  expect(checkboxes[0]).toBeChecked()
  expect(checkboxes[1]).toBeChecked()
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Question about both files' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  await screen.findByRole('button', { name: 'Citation 1' })
  let requests = fetch.mock.calls.filter(([url]) =>
    String(url).includes('/api/chat'),
  )
  expect(JSON.parse(requests[0][1].body).document_ids).toEqual([
    'doc-a',
    'doc-b',
  ])
  fireEvent.click(checkboxes[1])
  expect(
    screen.queryByText('Question about both files'),
  ).not.toBeInTheDocument()
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Only the first file' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  await waitFor(() =>
    expect(
      fetch.mock.calls.filter(([url]) => String(url).includes('/api/chat')),
    ).toHaveLength(2),
  )
  requests = fetch.mock.calls.filter(([url]) =>
    String(url).includes('/api/chat'),
  )
  expect(JSON.parse(requests[1][1].body)).toEqual({
    message: 'Only the first file',
    document_ids: ['doc-a'],
    history: [],
  })
})
it('opens the complete cited passage from its document and chunk pair', async () => {
  render(<App />)
  await screen.findAllByRole('checkbox')
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Show evidence' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Citation 1' }))
  expect(
    await screen.findByText('The complete passage from the selected document.'),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('dialog', { name: 'Source passage' }),
  ).toBeInTheDocument()
  expect(
    fetch.mock.calls.some(([url]) =>
      String(url).endsWith('/api/documents/doc-a/chunks/chunk-a'),
    ),
  ).toBe(true)
  fireEvent.click(
    screen.getByRole('button', { name: 'Close source' }),
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})
