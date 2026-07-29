import { toBlocks, type Block, type Inline } from './answerBlocks'
import { parseAnswer } from './citations'

interface AnswerTextProps {
  text: string
  isStreaming: boolean
  resolvable?: Set<string>
  onMarkerClick: (label: string) => void
  activeLabel: string | null
}

/**
 * Renders an answer with its [C3]/[E1] markers turned into footnotes, and the
 * light markdown the model writes turned into real formatting.
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
  const blocks = toBlocks(segments)

  function renderInlines(inlines: Inline[]) {
    return inlines.map((inline, i) => {
      if (inline.kind === 'text') {
        return inline.bold ? (
          <strong key={i} className="font-semibold text-neutral-100">
            {inline.text}
          </strong>
        ) : (
          <span key={i}>{inline.text}</span>
        )
      }

      // A grouped "[E1, C1]" becomes two adjacent superscripts, which run
      // together as "12" without a separator between them.
      const separator = inlines[i - 1]?.kind === 'marker' ? ',' : null

      if (resolvable === undefined) {
        return (
          <sup key={i} className="text-[0.65rem] text-neutral-600">
            {separator}
            <span className={separator ? '' : 'ml-0.5'}>{inline.n}</span>
          </sup>
        )
      }

      return (
        <span key={i} className="align-super text-[0.65rem]">
          {separator && <span className="text-neutral-600">{separator}</span>}
          <button
            onClick={() => onMarkerClick(inline.label)}
            title="Show the source this came from"
            className={`transition-colors ${separator ? '' : 'ml-0.5'} ${
              activeLabel === inline.label
                ? 'text-blue-300'
                : 'text-blue-400 hover:text-blue-200'
            }`}
          >
            {inline.n}
          </button>
        </span>
      )
    })
  }

  // Consecutive bullets share one list, so the gap between items matches the
  // gap inside them rather than reading as separate lists.
  const groups: Block[][] = []
  for (const block of blocks) {
    const previous = groups[groups.length - 1]
    if (block.kind === 'bullet' && previous?.[0]?.kind === 'bullet') previous.push(block)
    else groups.push([block])
  }

  return (
    <div className="space-y-2">
      {groups.map((group, i) => {
        if (group[0].kind === 'bullet') {
          return (
            <ul key={i} className="space-y-1 pl-1">
              {group.map((block, j) => (
                <li key={j} className="flex gap-2">
                  <span aria-hidden className="flex-shrink-0 text-neutral-600">
                    ·
                  </span>
                  <span>{renderInlines(block.inlines)}</span>
                </li>
              ))}
            </ul>
          )
        }

        const block = group[0]
        if (block.kind === 'heading') {
          return (
            <p key={i} className="font-semibold text-neutral-100">
              {renderInlines(block.inlines)}
            </p>
          )
        }

        return <p key={i}>{renderInlines(block.inlines)}</p>
      })}
    </div>
  )
}
