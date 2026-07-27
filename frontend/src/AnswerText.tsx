import { parseAnswer } from './citations'

interface AnswerTextProps {
  text: string
  isStreaming: boolean
  resolvable?: Set<string>
  onMarkerClick: (label: string) => void
  activeLabel: string | null
}

/**
 * Renders an answer with its [C3]/[E1] markers turned into footnotes.
 *
 * While streaming, markers render as dimmed non-interactive superscripts
 * carrying the number they will keep once the citations event lands — so
 * becoming clickable is a colour change, not a reflow.
 */
export function AnswerText({
  text,
  isStreaming,
  resolvable,
  onMarkerClick,
  activeLabel,
}: AnswerTextProps) {
  const { segments } = parseAnswer(text, { isStreaming, resolvable })

  return (
    <>
      {segments.map((segment, i) =>
        segment.kind === 'text' ? (
          <span key={i} className="whitespace-pre-wrap">
            {segment.text}
          </span>
        ) : resolvable === undefined ? (
          <sup key={i} className="ml-0.5 text-[0.65rem] text-neutral-600">
            {segment.n}
          </sup>
        ) : (
          <button
            key={i}
            onClick={() => onMarkerClick(segment.label)}
            title="Show the source this came from"
            className={`ml-0.5 align-super text-[0.65rem] transition-colors ${
              activeLabel === segment.label
                ? 'text-blue-300'
                : 'text-blue-400 hover:text-blue-200'
            }`}
          >
            {segment.n}
          </button>
        ),
      )}
    </>
  )
}
