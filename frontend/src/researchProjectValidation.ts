/** The rules of Trapper's own "Add research project" form: name (required,
 * up to 255 characters), acronym (required, 3 to 10), an event interval
 * (required, a whole number, 0 or more), abstract/methods/description of up
 * to 2000 characters each. */
import type { ResearchProjectDraft } from './types'

export const RESEARCH_PROJECT_LIMITS = { name: 255, acronymMin: 3, acronymMax: 10, text: 2000 } as const

/** The acronym names the research project's folder, so it can only hold what a folder name safely can. */
export const ACRONYM_PATTERN = /^[0-9A-Za-z][0-9A-Za-z_.-]*$/

export interface ResearchProjectErrors {
  name?: string
  acronym?: string
  event_interval?: string
  abstract?: string
  methods?: string
  description?: string
}

export function validateResearchProject(p: ResearchProjectDraft): ResearchProjectErrors {
  const errors: ResearchProjectErrors = {}
  const { name, acronymMin, acronymMax, text } = RESEARCH_PROJECT_LIMITS

  if (!p.name.trim()) errors.name = 'Required'
  else if (p.name.length > name) errors.name = `At most ${name} characters.`

  const acronym = p.acronym.trim()
  if (!acronym) errors.acronym = 'Required'
  else if (acronym.length < acronymMin || acronym.length > acronymMax) errors.acronym = `Must have between ${acronymMin} and ${acronymMax} characters.`
  else if (!ACRONYM_PATTERN.test(acronym)) errors.acronym = 'Only letters, digits, "_", "-" and "." (starting with a letter or digit), as it names a folder.'

  if (p.event_interval == null) errors.event_interval = 'Required'
  else if (!Number.isInteger(p.event_interval) || p.event_interval < 0) errors.event_interval = 'Must be a whole number, 0 or more.'

  for (const key of ['abstract', 'methods', 'description'] as const) {
    if (p[key].length > text) errors[key] = `At most ${text} characters.`
  }

  return errors
}

/** Errors worth showing beside a field — everything but "left empty". */
export function shownProjectErrors(errors: ResearchProjectErrors): ResearchProjectErrors {
  const keep = (message?: string) => (message && message !== 'Required' ? message : undefined)
  return {
    name: keep(errors.name), acronym: keep(errors.acronym), event_interval: keep(errors.event_interval),
    abstract: keep(errors.abstract), methods: keep(errors.methods), description: keep(errors.description),
  }
}
