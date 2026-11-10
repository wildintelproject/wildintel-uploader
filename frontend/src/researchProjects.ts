import type { ResearchProject } from './types'
import { api } from './api'

/** Whether a research project is one to work on in the field: only an active one is offered where visits, deployments and uploads are made. A planned one is being prepared
 * and a finished one has no more fieldwork; both are still in Settings. One that was picked already stays in the list. */
export const isWorking = (p: Pick<ResearchProject, 'status'>) => (p.status ?? 'active') === 'active'
export const working = <T extends Pick<ResearchProject, 'status' | 'acronym'>>(projects: T[], keep?: string | null) =>
  projects.filter((p) => isWorking(p) || (!!keep && p.acronym.toLowerCase() === keep.toLowerCase()))

/** Whether a site, a camera or an SD card is one of the app: planned ones are only in Settings (the rest — ready, active — are offered; an archived one is told apart where it matters). */
export const inTheApp = (x: { status?: string | null }) => x.status !== 'planned'

/** The research projects to work on: those the collections folder keeps that are active (plus the one named by `keep`, when it is picked already). */
export async function listWorking(keep?: string | null): Promise<{ results: ResearchProject[] }> {
  const { results } = await api.listResearchProjects()
  return { results: working(results, keep) }
}
