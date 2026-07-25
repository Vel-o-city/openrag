import { describe, expect, it } from 'vitest'
import { stageFromJobStatus } from './UploadPanel'

describe('stageFromJobStatus', () => {
  it('maps done/partial/failed statuses directly', () => {
    expect(stageFromJobStatus('done', 100)).toBe('done')
    expect(stageFromJobStatus('partial', 100)).toBe('partial')
    expect(stageFromJobStatus('failed', 0)).toBe('failed')
  })

  it('maps a running job under 50% progress to extracting', () => {
    expect(stageFromJobStatus('running', 10)).toBe('extracting')
    expect(stageFromJobStatus('running', 49)).toBe('extracting')
  })

  it('maps a running job at or above 50% progress to linking', () => {
    expect(stageFromJobStatus('running', 50)).toBe('linking')
    expect(stageFromJobStatus('running', 95)).toBe('linking')
  })

  it('maps a freshly-queued job to extracting (about to start)', () => {
    expect(stageFromJobStatus('queued', 0)).toBe('extracting')
  })
})
