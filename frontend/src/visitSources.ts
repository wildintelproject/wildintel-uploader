/** Where the visits of a research project can be taken from, besides being entered by hand — Epicollect5 is the only one set up in the settings for now. Each is set up in
 * the Visit sources section of the settings: a new source is one more line here. */
export const VISIT_SOURCES = [{ id: 'epicollect', label: 'Epicollect5' }] as const

export type VisitSourceId = (typeof VISIT_SOURCES)[number]['id']
