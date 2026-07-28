/** The entity types the extraction prompt is allowed to emit. */
export const ENTITY_TYPE_COLORS: Record<string, string> = {
  Person: '#f97316',
  Organization: '#38bdf8',
  Location: '#a3e635',
  Event: '#f472b6',
  Concept: '#c084fc',
  Other: '#94a3b8',
}

export const FALLBACK_ENTITY_COLOR = '#94a3b8'

export function colorForEntityType(entityType: string): string {
  return ENTITY_TYPE_COLORS[entityType] ?? FALLBACK_ENTITY_COLOR
}
