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
      {segments.map((segment, i) => {
        if (segment.kind === 'text') {
          return (
            <span key={i} className="whitespace-pre-wrap">
              {segment.text}
            </span>
          )
        }

        // A grouped "[E1, C1]" becomes two adjacent superscripts, which run
        // together as "12" without a separator between them.
        const separator = segments[i - 1]?.kind === 'marker' ? ',' : null

        if (resolvable === undefined) {
          return (
            <sup key={i} className="text-[0.65rem] text-neutral-600">
              {separator}
              <span className={separator ? '' : 'ml-0.5'}>{segment.n}</span>
            </sup>
          )
        }

        return (
          <span key={i} className="align-super text-[0.65rem]">
            {separator && <span className="text-neutral-600">{separator}</span>}
            <button
              onClick={() => onMarkerClick(segment.label)}
              title="Show the source this came from"
              className={`transition-colors ${separator ? '' : 'ml-0.5'} ${
                activeLabel === segment.label
                  ? 'text-blue-300'
                  : 'text-blue-400 hover:text-blue-200'
              }`}
            >
              {segment.n}
            </button>
          </span>
        )
      })}
    </>
  )
}
