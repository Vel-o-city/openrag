import { useEffect, useRef } from 'react'

/** Linkable from a portfolio/profile, so the explainer can be sent directly. */
export const HOW_IT_WORKS_HASH = '#how-it-works'

const STEPS = [
  {
    title: 'Upload a PDF or image',
    body: 'Text is extracted — images go through vision OCR — then split into passages and embedded. Nothing is hidden: the passage behind a citation is the exact text the model was given.',
  },
  {
    title: 'Entities become a graph',
    body: 'People, organisations, locations, events and concepts are pulled out along with the relationships between them. Names for the same thing are resolved together rather than duplicated, so one entity can carry mentions from several documents.',
  },
  {
    title: 'Ask a question',
    body: 'Retrieval runs over both the graph and the passage embeddings, so an answer can follow relationships as well as match wording.',
  },
  {
    title: 'Check the answer',
    body: 'Every claim carries a footnote. Click one to see the source passage with its filename and page, and to light up the node it came from on the graph.',
  },
]

const TRADE_OFFS = [
  'Neo4j’s native vector index instead of a second vector database — one store serves both graph traversal and similarity search.',
  'pypdf and pypdfium2 over PyMuPDF, whose AGPL-3.0 licence would reach this whole repo once publicly deployed.',
  'Fully-managed free tiers over a self-hosted VM. The two costs are visible and mitigated: the API spins down when idle, and the database auto-pauses after 72h, both kept warm by scheduled pings.',
  'Uploads need no login, which maximises “try it right now” but means abuse, cost and prompt-injection safeguards had to exist from the first commit rather than be added later.',
]

const LIMITS = [
  'No authentication — one shared public instance, not multi-tenant.',
  'Moderation is a manual flag plus periodic pruning, not automated scanning.',
  'Rate limiting is per-IP, so a shared NAT is throttled collectively.',
  'Answers are only as good as what visitors have uploaded.',
]

export function HowItWorks({ onClose }: { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)

  // showModal() brings Escape handling, focus trapping and the backdrop for
  // free, none of which a div-based overlay gets without extra code.
  useEffect(() => {
    const dialog = ref.current
    if (!dialog?.open) dialog?.showModal()
  }, [])

  // m-auto is what centres a top-layer dialog: Tailwind's preflight zeroes the
  // UA stylesheet's `margin: auto`, which otherwise pins it to the top-left.
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        // The backdrop is part of the dialog element, so a click landing
        // outside the inner panel is a backdrop click.
        if (event.target === ref.current) ref.current?.close()
      }}
      aria-label="How OpenRAG works"
      className="m-auto max-h-[85vh] w-[min(34rem,calc(100vw-2rem))] rounded-xl border border-neutral-800 bg-neutral-900 p-0 text-neutral-100 backdrop:bg-black/70 open:flex open:flex-col"
    >
      <div className="flex items-start justify-between gap-4 border-b border-neutral-800 px-5 py-4">
        <h2 className="text-base font-semibold">How this works</h2>
        <button
          onClick={() => ref.current?.close()}
          className="-mr-1 rounded px-2 text-lg leading-none text-neutral-500 hover:text-neutral-200"
          aria-label="Close"
        >
          ×
        </button>
      </div>

      <div className="overflow-y-auto px-5 py-4">
        <ol className="space-y-3">
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

        <Section title="Design decisions" items={TRADE_OFFS} />
        <Section title="Known limitations" items={LIMITS} />

        <p className="mt-5 border-t border-neutral-800 pt-3 text-xs leading-relaxed text-neutral-500">
          This is one shared public graph — anything you upload is visible to everyone, so don't
          upload anything private. A few documents are pinned as a starting point; the rest is
          whatever visitors have added.
        </p>
      </div>
    </dialog>
  )
}

function Section({ title, items }: { title: string; items: string[] }) {
  return (
    <>
      <h3 className="mt-5 text-[0.65rem] uppercase tracking-wide text-neutral-500">{title}</h3>
      <ul className="mt-2 space-y-1.5">
        {items.map((item) => (
          <li key={item} className="flex gap-2 text-xs leading-relaxed text-neutral-400">
            <span aria-hidden className="text-neutral-600">
              ·
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </>
  )
}
