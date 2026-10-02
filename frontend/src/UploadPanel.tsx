import { useEffect, useRef, useState } from 'react'
import { API_BASE } from './apiBase'
import { rememberOwnDocument } from './ownDocuments'
import { TurnstileWidget } from './TurnstileWidget'

import { stageFromJobStatus, type Stage } from './uploadStatus'

const JOB_KEY = 'openrag:pending-upload'
interface PendingJob {
  job_id: string
  filename: string
  at: number
}
function saveJob(job: PendingJob | null) {
  try {
    if (job) localStorage.setItem(JOB_KEY, JSON.stringify(job))
    else localStorage.removeItem(JOB_KEY)
  } catch {
    /* Storage may be unavailable. */
  }
}
function pendingJob(): PendingJob | null {
  try {
    const job = JSON.parse(localStorage.getItem(JOB_KEY) ?? 'null')
    return typeof job?.job_id === 'string' &&
      typeof job?.filename === 'string' &&
      Date.now() - job.at < 86400000
      ? job
      : null
  } catch {
    return null
  }
}
function delay(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const stop = () => {
      clearTimeout(timer)
      reject(new DOMException('Cancelled', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal.removeEventListener('abort', stop)
      resolve()
    }, 1500)
    signal.addEventListener('abort', stop, { once: true })
  })
}
export function UploadPanel({
  onComplete,
}: {
  onComplete: (id: string) => Promise<void>
}) {
  const [stage, setStage] = useState<Stage>('idle')
  const [progress, setProgress] = useState(0)
  const [filename, setFilename] = useState('')
  const [error, setError] = useState('')
  const [token, setToken] = useState<string | null>(null)
  const [widgetKey, setWidgetKey] = useState(0)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const controller = useRef<AbortController | null>(null)
  const completeRef = useRef(onComplete)
  completeRef.current = onComplete
  const busyRef = useRef(false)
  const requiresVerification = !!import.meta.env.VITE_TURNSTILE_SITE_KEY
  const busy = ['uploading', 'extracting', 'linking'].includes(stage)

  async function poll(job: PendingJob, abort: AbortController) {
    let failures = 0
    let expired = false
    for (let attempt = 0; attempt < 400; attempt++) {
      await delay(abort.signal)
      try {
        const response = await fetch(
          `${API_BASE}/api/jobs/${encodeURIComponent(job.job_id)}`,
          { signal: abort.signal },
        )
        if (response.status === 404) {
          expired = true
          saveJob(null)
          throw new Error(
            'This upload session expired. Please upload the file again.',
          )
        }
        if (!response.ok) throw new Error('Waiting to reconnect to the upload…')
        const result = await response.json()
        failures = 0
        setError('')
        setProgress(result.progress ?? 0)
        setStage(stageFromJobStatus(result.status, result.progress ?? 0))
        if (['done', 'partial'].includes(result.status)) {
          if (!result.document_id)
            throw new Error('The processed document could not be found.')
          rememberOwnDocument(result.document_id)
          saveJob(null)
          await completeRef.current(result.document_id)
          return
        }
        if (result.status === 'failed') {
          saveJob(null)
          setError(
            result.error || 'Could not read this file. Try a clearer document.',
          )
          return
        }
      } catch (err) {
        if (abort.signal.aborted) throw err
        failures++
        setError(
          err instanceof Error
            ? err.message
            : 'Waiting to reconnect to the upload…',
        )
        if (failures >= 20 || expired) throw err
      }
    }
    throw new Error(
      'Processing is taking longer than expected. Refresh to reconnect; your upload may still finish.',
    )
  }
  useEffect(() => {
    const job = pendingJob()
    if (job) {
      const abort = new AbortController()
      controller.current = abort
      busyRef.current = true
      setFilename(job.filename)
      setStage('extracting')
      void poll(job, abort)
        .catch((err) => {
          if (!abort.signal.aborted) {
            setStage('failed')
            setError(
              err instanceof Error ? err.message : 'Could not reconnect.',
            )
          }
        })
        .finally(() => {
          if (controller.current === abort) busyRef.current = false
        })
    }
    return () => controller.current?.abort()
  }, [])
  async function handleFile(file?: File) {
    if (!file || busyRef.current) return
    if (!/\.(pdf|png|jpe?g|webp)$/i.test(file.name)) {
      setError('Choose a PDF, PNG, JPG, or WebP file.')
      return
    }
    if (!file.size || file.size > 20 * 1024 * 1024) {
      setError('Choose a non-empty file up to 20 MB.')
      return
    }
    if (requiresVerification && !token) {
      setError('Complete the verification below before uploading.')
      return
    }
    controller.current?.abort()
    const abort = new AbortController()
    controller.current = abort
    busyRef.current = true
    setFilename(file.name)
    setStage('uploading')
    setProgress(0)
    setError('')
    const form = new FormData()
    form.append('file', file)
    if (token) form.append('turnstile_token', token)
    try {
      const response = await fetch(`${API_BASE}/api/documents`, {
        method: 'POST',
        body: form,
        signal: abort.signal,
      })
      if (response.status === 429)
        throw new Error(
          'The demo upload limit has been reached. Please try again later.',
        )
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(
          typeof body?.detail === 'string'
            ? body.detail
            : 'Could not upload the file. Please try again.',
        )
      }
      const result = await response.json()
      const job = {
        job_id: result.job_id,
        filename: file.name,
        at: Date.now(),
      }
      saveJob(job)
      setStage('extracting')
      await poll(job, abort)
    } catch (err) {
      if (!abort.signal.aborted) {
        setStage('failed')
        setError(
          err instanceof Error
            ? err.message
            : 'Could not reach the server. Please try again.',
        )
      }
    } finally {
      if (controller.current === abort) busyRef.current = false
      setToken(null)
      setWidgetKey((key) => key + 1)
      if (input.current) input.current.value = ''
    }
  }
  return (
    <div
      className="upload-panel"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        void handleFile(e.dataTransfer.files[0])
      }}
    >
      <button
        className={`upload-button ${dragging ? 'upload-dragging' : ''}`}
        disabled={busy}
        onClick={() => input.current?.click()}
      >
        <span>＋</span>
        {busy ? 'Processing document…' : 'Upload a document'}
        <span>↑</span>
      </button>
      <input
        aria-label="Upload document file"
        ref={input}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.webp"
        hidden
        onChange={(e) => void handleFile(e.target.files?.[0])}
      />
      <p className="upload-hint">
        PDF, PNG, JPG, WebP · 20 MB · 20 pages
        <br />
        Drop a file here to upload
      </p>
      {requiresVerification && !busy && (
        <TurnstileWidget
          key={widgetKey}
          onVerify={setToken}
          onExpire={() => setToken(null)}
        />
      )}
      {stage !== 'idle' && (
        <div className={`upload-status upload-${stage}`} role="status">
          <strong>
            {stage === 'done'
              ? 'Ready to ask questions'
              : stage === 'partial'
                ? 'Ready · some pages could not be read'
                : stage === 'failed'
                  ? 'Upload needs attention'
                  : stage === 'uploading'
                    ? 'Uploading…'
                    : `Reading and indexing · ${progress}%`}
          </strong>
          <span title={filename}>{filename}</span>
          {busy && (
            <progress
              aria-label="Document processing progress"
              max={100}
              value={progress}
            />
          )}
        </div>
      )}
      {error && (
        <p className="upload-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
