import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'
import type { DocumentInfo } from './App'

const docs: DocumentInfo[] = [
  {
    id: 'doc-a',
    filename: 'plan.pdf',
    page_count: 2,
    status: 'done',
    is_seed: false,
    chunk_count: 2,
  },
]
const chunk = {
  id: 'chunk-a',
  label: 'C1',
  text: 'The deadline is 12 October.',
  truncated: false,
  char_count: 27,
  page_number: 2,
  document_id: 'doc-a',
  filename: 'plan.pdf',
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
function response(text = 'The deadline is 12 October [C1].', done = true) {
  return new Response(
    `event: token\ndata: ${JSON.stringify({ text })}\n\nevent: citations\ndata: ${JSON.stringify(citations)}\n\n${done ? 'event: done\ndata: {}\n\n' : ''}`,
    { status: 200 },
  )
}
afterEach(() => vi.unstubAllGlobals())
describe('document chat', () => {
  it('sends document scope, includes follow-up history, and opens the right citation passage', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(response()))
    vi.stubGlobal('fetch', fetch)
    const open = vi.fn()
    render(<ChatPanel documents={docs} loading={false} onOpenSource={open} />)
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'When is the deadline?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    const citation = await screen.findByRole('button', { name: 'Citation 1' })
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({
      message: 'When is the deadline?',
      document_ids: ['doc-a'],
      history: [],
    })
    fireEvent.click(citation)
    expect(open).toHaveBeenCalledWith({
      chunk,
      number: 1,
      originalUrl: undefined,
      title: undefined,
    })
    await waitFor(() => expect(screen.getByRole('textbox')).not.toBeDisabled())
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Which month?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    const body = JSON.parse(fetch.mock.calls[1][1].body)
    expect(body.document_ids).toEqual(['doc-a'])
    expect(body.history).toEqual([
      { role: 'user', text: 'When is the deadline?' },
      { role: 'assistant', text: 'The deadline is 12 October [C1].' },
    ])
  })
  it('keeps the answer and shows an explicit interruption if the stream closes early', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response('A partial answer.', false)),
    )
    render(
      <ChatPanel documents={docs} loading={false} onOpenSource={vi.fn()} />,
    )
    fireEvent.change(screen.getByRole('textbox'), {
      target: { value: 'Summarize' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'connection closed',
    )
    expect(screen.getByText('A partial answer.')).toBeInTheDocument()
  })
  it('does not allow unscoped questions', () => {
    render(<ChatPanel documents={[]} loading={false} onOpenSource={vi.fn()} />)
    expect(screen.getByRole('textbox')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled()
  })
})

it('replaces interrupted model output on reset instead of combining different answers', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          `event: token\ndata: {"text":"Discarded attempt."}\n\nevent: reset\ndata: {}\n\nevent: token\ndata: {"text":"The final answer [C1]."}\n\nevent: citations\ndata: ${JSON.stringify(citations)}\n\nevent: done\ndata: {}\n\n`,
        ),
      ),
  )
  render(<ChatPanel documents={docs} loading={false} onOpenSource={vi.fn()} />)
  fireEvent.change(screen.getByRole('textbox'), {
    target: { value: 'Test retry' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }))
  await screen.findByRole('button', { name: 'Citation 1' })
  expect(screen.queryByText('Discarded attempt.')).not.toBeInTheDocument()
  expect(screen.getByText('The final answer')).toBeInTheDocument()
})
