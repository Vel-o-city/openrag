import { useEffect, useRef, useState } from 'react'
import { API_BASE } from './apiBase'
import { useGraph } from './GraphContext'
import { TurnstileWidget } from './TurnstileWidget'

const POLL_INTERVAL_MS = 1500
const MAX_POLL_ATTEMPTS = 80 // ~2 minutes

type Stage = 'idle' | 'uploading' | 'extracting' | 'linking' | 'done' | 'partial' | 'failed' | 'throttled'

const STAGE_LABELS: Record<Stage, string> = {
  idle: '',
  uploading: 'Uploading…',
  extracting: 'Extracting…',
  linking: 'Linking into the graph…',
  done: 'Done — new nodes are live in the graph.',
  partial: 'Mostly done — a few pages needed extra care.',
  failed: 'Something went wrong processing that file.',
  throttled: "You've hit the upload limit.",
}

export function stageFromJobStatus(status: string, progress: number): Stage {
  if (status === 'done') return 'done'
  if (status === 'partial') return 'partial'
  if (status === 'failed') return 'failed'
  return progress >= 50 ? 'linking' : 'extracting'
}

export function UploadPanel() {
  const [expanded, setExpanded] = useState(false)
  const [stage, setStage] = useState<Stage>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryAfter, setRetryAfter] = useState<number | null>(null)
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const [widgetKey, setWidgetKey] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const cancelledRef = useRef(false)
  const { refreshGraph } = useGraph()

  useEffect(() => {
    if (retryAfter === null) return undefined
    if (retryAfter <= 0) {
      setRetryAfter(null)
      return undefined
    }
    const timeout = setTimeout(() => setRetryAfter((seconds) => (seconds ?? 1) - 1), 1000)
    return () => clearTimeout(timeout)
  }, [retryAfter])

  function reset() {
    cancelledRef.current = true
    setStage('idle')
    setErrorMessage(null)
    setTurnstileToken(null)
    setWidgetKey((key) => key + 1)
  }

  async function pollJob(jobId: string, attempt = 0) {
    if (cancelledRef.current) return

    if (attempt >= MAX_POLL_ATTEMPTS) {
      setStage('failed')
      setErrorMessage('Timed out waiting for processing to finish.')
      return
    }

    const response = await fetch(`${API_BASE}/api/jobs/${jobId}`)
    if (cancelledRef.current) return
    if (!response.ok) {
      setStage('failed')
      setErrorMessage('Lost track of that upload — please try again.')
      return
    }

    const job = await response.json()
    const nextStage = stageFromJobStatus(job.status, job.progress ?? 0)
    setStage(nextStage)

    if (job.status === 'done' || job.status === 'partial') {
      await refreshGraph()
      setTimeout(reset, 3000)
      return
    }
    if (job.status === 'failed') {
      setErrorMessage(job.error ?? null)
      return
    }

    setTimeout(() => pollJob(jobId, attempt + 1), POLL_INTERVAL_MS)
  }

  async function uploadFile(file: File) {
    cancelledRef.current = false
    setStage('uploading')
    setErrorMessage(null)

    const formData = new FormData()
    formData.append('file', file)
    if (turnstileToken) formData.append('turnstile_token', turnstileToken)

    try {
      const response = await fetch(`${API_BASE}/api/documents`, { method: 'POST', body: formData })

      if (response.status === 429) {
        const retryAfterHeader = response.headers.get('Retry-After')
        setStage('throttled')
        setRetryAfter(retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : 60)
        return
      }
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        setStage('failed')
        setErrorMessage(body?.detail ?? `Upload failed (${response.status}).`)
        return
      }

      const { job_id: jobId } = await response.json()
      setStage('extracting')
      setTimeout(() => pollJob(jobId), POLL_INTERVAL_MS)
    } catch {
      setStage('failed')
      setErrorMessage('Could not reach the server — please try again.')
    }
  }

  function handleFile(file: File | undefined) {
    if (!file || stage === 'uploading' || stage === 'extracting' || stage === 'linking') return
    if (!turnstileToken) {
      setErrorMessage('Please complete the verification widget first.')
      return
    }
    uploadFile(file)
  }

  const isBusy = stage === 'uploading' || stage === 'extracting' || stage === 'linking'
  const isTerminal = stage === 'done' || stage === 'partial' || stage === 'failed' || stage === 'throttled'

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="absolute bottom-4 left-4 rounded-full border border-neutral-700 bg-neutral-900/90 px-4 py-2 text-sm font-medium text-neutral-100 shadow-lg hover:border-neutral-500"
      >
        + Upload a document
      </button>
    )
  }

  return (
    <div className="absolute bottom-4 left-4 w-80 rounded-lg border border-neutral-800 bg-neutral-900/95 p-4 text-neutral-100 shadow-xl">
      <div className="flex items-start justify-between">
        <h3 className="text-sm font-semibold">Add to the shared graph</h3>
        <button
          className="text-neutral-500 hover:text-neutral-300"
          onClick={() => {
            setExpanded(false)
            reset()
          }}
        >
          ✕
        </button>
      </div>

      <p className="mt-1 text-xs text-neutral-500">
        PDFs and images become part of this public, shared knowledge graph — don't upload anything sensitive.
      </p>

      {!isBusy && !isTerminal && (
        <>
          <div className="mt-3">
            <TurnstileWidget key={widgetKey} onVerify={setTurnstileToken} onExpire={() => setTurnstileToken(null)} />
          </div>

          <div
            onDragOver={(event) => {
              event.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault()
              setIsDragging(false)
              handleFile(event.dataTransfer.files[0])
            }}
            onClick={() => fileInputRef.current?.click()}
            className={`mt-3 flex h-24 cursor-pointer items-center justify-center rounded-md border-2 border-dashed text-center text-xs transition-colors ${
              isDragging
                ? 'border-blue-400 bg-blue-500/10 text-blue-200'
                : 'border-neutral-700 text-neutral-500 hover:border-neutral-600'
            }`}
          >
            Drag a PDF or image here, or click to browse
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={(event) => handleFile(event.target.files?.[0])}
          />
        </>
      )}

      {(isBusy || isTerminal) && (
        <div className="mt-3">
          <p
            className={
              stage === 'failed' || stage === 'throttled' ? 'text-sm text-red-400' : 'text-sm text-neutral-200'
            }
          >
            {STAGE_LABELS[stage]}
          </p>
          {isBusy && (
            <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-neutral-800">
              <div className="h-full w-1/2 animate-pulse rounded-full bg-blue-500" />
            </div>
          )}
          {errorMessage && <p className="mt-1 text-xs text-neutral-500">{errorMessage}</p>}
          {stage === 'throttled' && retryAfter !== null && (
            <p className="mt-1 text-xs text-neutral-500">Try again in {retryAfter}s — feel free to explore or chat meanwhile.</p>
          )}
          {isTerminal && (
            <button onClick={reset} className="mt-2 text-xs text-neutral-400 underline hover:text-neutral-200">
              Upload another
            </button>
          )}
        </div>
      )}
    </div>
  )
}
