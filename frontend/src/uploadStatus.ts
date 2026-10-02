export type Stage =
  | 'idle'
  | 'uploading'
  | 'extracting'
  | 'linking'
  | 'done'
  | 'partial'
  | 'failed'
export function stageFromJobStatus(status: string, progress: number): Stage {
  if (status === 'done' || status === 'partial' || status === 'failed')
    return status
  return progress >= 50 ? 'linking' : 'extracting'
}
