import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isOwnDocument, ownDocumentIds, rememberOwnDocument } from './ownDocuments'

const STORAGE_KEY = 'openrag:own-docs'

describe('ownDocuments', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useRealTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('remembers and recognises a document', () => {
    rememberOwnDocument('doc-1')
    expect(isOwnDocument('doc-1')).toBe(true)
    expect(isOwnDocument('doc-2')).toBe(false)
  })

  it('ignores an empty id', () => {
    rememberOwnDocument('')
    expect(ownDocumentIds()).toEqual([])
  })

  it('does not duplicate a re-uploaded document', () => {
    rememberOwnDocument('doc-1')
    rememberOwnDocument('doc-1')
    expect(ownDocumentIds()).toEqual(['doc-1'])
  })

  it('caps the list at 20, dropping the oldest', () => {
    for (let i = 0; i < 25; i++) rememberOwnDocument(`doc-${i}`)

    const ids = ownDocumentIds()
    expect(ids).toHaveLength(20)
    expect(ids).toContain('doc-24')
    expect(ids).not.toContain('doc-4')
  })

  it('forgets entries older than 30 days', () => {
    const thirtyOneDaysAgo = Date.now() - 31 * 24 * 60 * 60 * 1000
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ id: 'stale', at: thirtyOneDaysAgo }]))

    expect(isOwnDocument('stale')).toBe(false)
  })

  it('keeps entries inside the 30-day window', () => {
    const yesterday = Date.now() - 24 * 60 * 60 * 1000
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ id: 'fresh', at: yesterday }]))

    expect(isOwnDocument('fresh')).toBe(true)
  })

  it('survives a throwing setItem, as in Safari private mode', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError')
    })

    expect(() => rememberOwnDocument('doc-1')).not.toThrow()
  })

  it('survives corrupt stored JSON', () => {
    localStorage.setItem(STORAGE_KEY, 'not json at all')
    expect(ownDocumentIds()).toEqual([])
    expect(() => rememberOwnDocument('doc-1')).not.toThrow()
  })

  it('ignores stored entries of the wrong shape', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([{ nope: true }, 'string', null]))
    expect(ownDocumentIds()).toEqual([])
  })

  it('ignores a stored value that is not an array', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: 'doc-1' }))
    expect(ownDocumentIds()).toEqual([])
  })
})
