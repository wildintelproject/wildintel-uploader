/** Where the visits of a research project can be taken from, besides being entered by hand — the CSV of the WildINTEL Epicollect project, and the connection to Epicollect5 for the information of a deployment. Each is set up in
 * the Visit sources section of the settings: a new source is one more line here. */
export const VISIT_SOURCES = [{ id: 'wildintel', label: 'WildINTEL Epicollect' }, { id: 'epicollect', label: 'Epicollect5' }] as const

export type VisitSourceId = (typeof VISIT_SOURCES)[number]['id']
