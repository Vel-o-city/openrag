import { useEffect } from 'react'

const STEPS = [
  {
    title: 'Upload a PDF or image',
    body: 'Text is extracted, split into passages, and embedded. Nothing is hidden — the passage a citation points to is the exact text the model was given.',
  },
  {
    title: 'Entities become a graph',
    body: 'People, organisations, locations, events and concepts are pulled out along with the relationships between them, then merged into the shared graph. Names that refer to the same thing are resolved together rather than duplicated.',
  },
  {
    title: 'Ask a question',
    body: 'Retrieval runs over both the graph and the passage embeddings, so an answer can follow relationships as well as match wording.',
  },
  {
    title: 'Check the answer',
    body: 'Every claim carries a footnote. Click one to see the source passage, its filename and page — and to light up the node it came from on the graph.',
  },
]

export function HowItWorks({ onClose }: { onClose: () => void }) {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="max-h-full w-full max-w-lg overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900 p-5 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="How OpenRAG works"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-base font-semibold text-neutral-100">How this works</h2>
          <button
            onClick={onClose}
            className="rounded px-2 text-lg leading-none text-neutral-500 hover:text-neutral-200"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <ol className="mt-4 space-y-3">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flex gap-3">
              <span className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-neutral-800 text-[0.7rem] font-medium text-neutral-400">
                {i + 1}
              </span>
              <div>
                <p className="text-sm font-medium text-neutral-200">{step.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-neutral-500">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="mt-4 border-t border-neutral-800 pt-3 text-xs leading-relaxed text-neutral-500">
          This is one shared public graph — anything you upload is visible to everyone, so don't
          upload anything private. A few documents are pinned as a starting point; the rest is
          whatever visitors have added.
        </p>
      </div>
    </div>
  )
}
