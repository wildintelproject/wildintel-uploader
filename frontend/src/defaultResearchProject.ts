import { api } from './api'

/** The acronym of the research project the general settings say comes filled in — empty when there is none, or the settings can't be read. */
export async function defaultResearchProject(): Promise<string> {
  try {
    return (await api.getSettings())?.GENERAL?.default_research_project?.trim() || ''
  } catch {
    return ''
  }
}
