import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { UploadPanel } from './UploadPanel'
import { ownDocumentIds } from './ownDocuments'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  localStorage.clear()
})
it('allows local uploads, recovers a transient polling error, and remembers the deduplicated document ID', async () => {
  vi.useFakeTimers()
  const fetch = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({ job_id: 'job-a', document_id: 'temporary-id' }),
      ),
    )
    .mockResolvedValueOnce(new Response('', { status: 503 }))
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: 'done',
          progress: 100,
          document_id: 'existing-id',
        }),
      ),
    )
  vi.stubGlobal('fetch', fetch)
  const complete = vi.fn().mockResolvedValue(undefined)
  render(<UploadPanel onComplete={complete} />)
  await act(async () => {
    fireEvent.change(screen.getByLabelText('Upload document file'), {
      target: {
        files: [new File(['pdf'], 'plan.pdf', { type: 'application/pdf' })],
      },
    })
  })
  expect(fetch).toHaveBeenCalledTimes(1)
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500)
  })
  expect(screen.getByRole('alert')).toHaveTextContent('reconnect')
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500)
  })
  expect(complete).toHaveBeenCalledWith('existing-id')
  expect(ownDocumentIds()).toEqual(['existing-id'])
  expect(localStorage.getItem('openrag:pending-upload')).toBeNull()
  expect(screen.getByRole('status')).toHaveTextContent('Ready to ask questions')
})
