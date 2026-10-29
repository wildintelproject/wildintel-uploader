import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import { Icon, Ring } from '../components/Dashboard'
import { Breadcrumb } from '../components/TaskCard'
import RevisionSquares from '../components/RevisionSquares'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import type { BookVisit, ClosedVisitTarget } from '../types'
import { btnOutline, inputClass } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
  /** Goes to Import deployment for a closed visit: its research project, and the visit whose card was collected — the deployment is of it. */
  onImportImages?: (target: ClosedVisitTarget) => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  /** Whether the settings are open: the default research project is read again when they are closed, as it may have been changed. */
  settingsOpen?: boolean
  /** Goes to the status of the deployments, on one of them: the link of the tick of the images stored. */
  onShowDeployment?: (deploymentId: string) => void
  /** The visit shown open, on its revision and its page: the one a link of the deployments dashboard goes to. */
  focus?: VisitFocus
}

/** The fields of a visit the details show, in this order, when it has them. */
const DETAILS: [keyof BookVisit, string][] = [
  ['trappers', 'Who went'], ['setup_by', 'Set up by'], ['camera_id', 'Camera'], ['camera_model', 'Camera model'], ['sd', 'SD card left'], ['num_photos', 'Photos counted'], ['status', 'Status of the camera'],
  ['card_batteries_ok', 'Card and batteries'], ['date_time_ok', 'Camera date and time OK'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['camera_interval', 'Camera delay (s)'],
  ['camera_height', 'Camera height (m)'], ['camera_depth', 'Camera depth (m)'], ['camera_tilt', 'Camera tilt (°)'], ['camera_heading', 'Camera heading (°)'], ['detection_distance', 'Detection distance (m)'],
  ['timestamp_issues', 'Timestamp issues'], ['bait_use', 'Bait use'], ['feature_type', 'Feature type'], ['habitat', 'Habitat'], ['deployment_groups', 'Deployment groups'], ['tags', 'Tags'],
  ['comments', 'Notes'], ['when', 'Instant (UTC)'], ['deployment_id', 'Deployment imported'],
]

const shownValue = (v: unknown) => (typeof v === 'boolean' ? (v ? 'yes' : 'no') : Array.isArray(v) ? v.join(', ') : String(v))

/** The columns the book can be sorted by. */
type SortKey = 'session' | 'where' | 'when' | 'status' | 'actions' | 'stored'
const COLUMNS: [SortKey, string][] = [['session', 'Revision'], ['where', 'Where'], ['when', 'When'], ['actions', 'Actions'], ['status', 'Status'], ['stored', 'Images']]

/** What a row says in a column, to sort by it: the rows not made go last whatever the direction (they have no day, no actions…). */
function sortValue(v: BookVisit, key: SortKey): string | number {
  switch (key) {
    case 'session': return v.session
    case 'where': return v.location_id.toLowerCase()
    case 'when': return `${v.date}T${v.time}`
    case 'status': { const i = PHASES.indexOf(phaseOf(v) as Phase); return i < 0 ? PHASES.length : i } // a visit that left no camera goes last
    case 'actions': return v.actions.join(' + ').toLowerCase()
    case 'stored': return v.deployment_id ? 0 : v.deployment_status === 'closed' ? 1 : 2 // stored, to create, not stored
  }
}

/** Where a visit is in its life: planned (not made yet), deployed (it left a camera that is still out), collected (the card was collected: a later visit closed it) and stored (the deployment is made, so its images are kept). A visit that left no camera has none. */
type Phase = 'planned' | 'deployed' | 'collected' | 'stored'
const phaseOf = (v: BookVisit): Phase | null =>
  v.not_done ? 'planned' : v.deployment_status === 'open' ? 'deployed' : v.deployment_status === 'closed' ? (v.deployment_id ? 'stored' : 'collected') : null
const PHASES: Phase[] = ['stored', 'collected', 'deployed', 'planned']
const PHASE_LABEL: Record<Phase, string> = { planned: 'Planned', deployed: 'Deployed', collected: 'Collected', stored: 'Stored' }
const PHASE_BADGE: Record<Phase, string> = {
  planned: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300',
  deployed: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300',
  collected: 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300',
  stored: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300',
}

/** The rows the status cards show: the ones in a phase, or all. */
type StatusFilter = '' | Phase
const matches = (v: BookVisit, f: StatusFilter) => !f || phaseOf(v) === f

/** The visit a link of another page goes to: the revision and the site it was made at. */
export interface VisitFocus { session: string; site: string }

/** The order the book has when no column is chosen: the latest revision first, within it the visits made newest first and then the ones not made, by site. */
const byDefault = (a: BookVisit, b: BookVisit) =>
  b.session.localeCompare(a.session) || Number(a.not_done) - Number(b.not_done) || (a.not_done ? a.location_id.localeCompare(b.location_id) : `${b.date}T${b.time}`.localeCompare(`${a.date}T${a.time}`))
/** The SD card a visit collects: the one the visit before it at the site left in the camera — not the one this visit leaves, which has no photos yet. */
const collectedCard = (visits: BookVisit[], v: BookVisit): string | null => {
  const at = (w: BookVisit) => w.when ?? `${w.date}T${w.time}`
  const before = visits.filter((w) => !w.not_done && w.sd && w.location_id.toLowerCase() === v.location_id.toLowerCase() && at(w) < at(v) && w.actions.some((a) => a === 'Installation' || a === 'Revision'))
  return before.sort((a, b) => at(b).localeCompare(at(a)))[0]?.sd ?? null
}
const keyOf = (v: BookVisit) => `${v.session}|${v.location_id}|${v.date}|${v.time}`

/** How many visits a page of the book has. */
const PER_PAGE = 10

/** The visit book of a research project: the visits kept to it, and the deployments they say — closed, and the ones whose camera is still out — with the logs of their collections. */
export default function VisitBookPage({ onBack, onImportImages, onOpenSettings, settingsOpen, onShowDeployment, focus }: Props) {
  // The book is of the research project the general settings say is the default: the one that is active.
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [visits, setVisits] = useState<BookVisit[] | null>(null)
  const [opened, setOpened] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('')
  // A revision is one visit to every site: the book can be of one of them, or of all.
  const [revision, setRevision] = useState('')
  const [page, setPage] = useState(1)
  // Sorted by a column when one is chosen — pressing it again turns it round —; else the latest revision first.
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const error = projectError ?? loadError

  useEffect(() => {
    setVisits(null); setLoadError(null); setPage(1); setOpened(null); setRevision('')
    if (!project) return
    let cancelled = false
    api.visitBook(project.acronym)
      .then(({ results }) => { if (!cancelled) setVisits(results) })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the visits.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  // How many rows each status square has — over the rows of the revision picked (all of them when none is), whatever the text filter says.
  const everyRow = visits ?? []
  const revisions = [...new Set(everyRow.map((v) => v.session))].sort((x, y) => y.localeCompare(x))
  const rows = revision ? everyRow.filter((v) => v.session === revision) : everyRow
  const count = (f: StatusFilter) => rows.filter((v) => matches(v, f)).length
  const made = rows.filter((v) => !v.not_done).length
  const percent = rows.length ? Math.round((made / rows.length) * 100) : 0
  const SQUARES: { filter: Phase; label: string; note: string; tone: string; badge: string; icon: ReactNode }[] = [
    { filter: 'planned', label: 'Planned', note: 'Not visited yet', tone: 'text-zinc-600 dark:text-zinc-300', badge: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>} className="h-5 w-5" /> },
    { filter: 'deployed', label: 'Deployed', note: 'Camera out, card not collected', tone: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300', icon: <Icon path={<><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5v.01" /></>} className="h-5 w-5" /> },
    { filter: 'collected', label: 'Collected', note: 'Card collected, deployment not made', tone: 'text-violet-600 dark:text-violet-400', badge: 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>} className="h-5 w-5" /> },
    { filter: 'stored', label: 'Stored', note: 'Deployment made, images stored', tone: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300', icon: <Icon path={<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />} className="h-5 w-5" /> },
  ]

  // the visit a link of the deployments dashboard goes to is brought into view: on its revision, on its page, and open
  useEffect(() => {
    if (!focus || !visits) return
    const target = visits.find((v) => !v.not_done && v.session === focus.session && v.location_id.toLowerCase() === focus.site.toLowerCase())
    if (!target) return
    setRevision(target.session); setStatusFilter(''); setFilter(''); setSort(null)
    setPage(Math.floor(visits.filter((v) => v.session === target.session).sort(byDefault).findIndex((v) => keyOf(v) === keyOf(target)) / PER_PAGE) + 1)
    setOpened(keyOf(target))
  }, [focus, visits])

  const needle = filter.trim().toLowerCase()
  const shown = rows
    .filter((v) => matches(v, statusFilter))
    .filter((v) => !needle || `${v.location_id} ${v.session} ${v.camera_id ?? ''} ${v.sd ?? ''} ${v.trappers ?? ''} ${v.actions.join(' ')} ${v.deployment_id ?? ''} ${phaseOf(v) ? PHASE_LABEL[phaseOf(v)!] : ''}`.toLowerCase().includes(needle))
    // by the column chosen — the rows not made last —, else the latest revision first, within it the visits made newest first and then the ones not made, by site
    .sort((a, b) => {
      if (!sort) return byDefault(a, b)
      if (a.not_done !== b.not_done && ['when', 'actions', 'stored'].includes(sort.key)) return Number(a.not_done) - Number(b.not_done)
      const x = sortValue(a, sort.key), y = sortValue(b, sort.key)
      const order = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
      return (sort.descending ? -order : order) || byDefault(a, b)
    })
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <Breadcrumb parent="Manage visits" onParent={onBack} current="Visit dashboard" />
      <header className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
            <Icon path={<><path d="M4 5.5A2.5 2.5 0 016.5 3H19v16H6.5A2.5 2.5 0 004 21.5z" /><path d="M4 18.5A2.5 2.5 0 016.5 16H19" /></>} className="h-6 w-6" />
          </span>
          <div>
            <h4 className="text-xl font-semibold leading-tight">Visit dashboard</h4>
            <p className="text-zinc-500 dark:text-zinc-400 text-sm">The visits kept to a research project.</p>
          </div>
        </div>
        <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The book" onOpenSettings={onOpenSettings} />
      </header>

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {project && (
        <>
          {visits !== null && revisions.length > 0 && (
            <section aria-label="Revision" className="mb-6">
              <h5 className="text-lg font-semibold mb-1">Revision</h5>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">A revision is one visit to every site. Pick one to see what is planned and what is done.</p>
              <RevisionSquares all={{ label: 'All revisions', note: `${everyRow.filter((v) => !v.not_done).length} of ${everyRow.length} done` }} value={revision}
                revisions={revisions.map((r) => { const of = everyRow.filter((v) => v.session === r); return { id: r, label: r, note: `${of.filter((v) => !v.not_done).length} of ${of.length} done` } })}
                onPick={(id) => { setRevision(id); setStatusFilter(''); setPage(1); setOpened(null) }} />
            </section>
          )}
          {visits !== null && (
            <section aria-label="Visits by status" className="mb-5">
              <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a card to show only those visits.</p>
              <div className="grid grid-cols-2 lg:grid-cols-[1.6fr_1fr_1fr_1fr_1fr] gap-3">
                <div className="col-span-2 lg:col-span-1 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4">
                  <Ring percent={percent} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">Visits completed</p>
                    <p className="text-2xl font-semibold leading-tight">{made} <span className="text-zinc-400">/ {rows.length}</span></p>
                    <div role="progressbar" aria-label="Visits done" aria-valuemin={0} aria-valuemax={rows.length} aria-valuenow={made} className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                      <div className="bg-emerald-500" style={{ width: `${rows.length ? ((count('collected') + count('stored')) / rows.length) * 100 : 0}%` }} />
                      <div className="bg-amber-500" style={{ width: `${rows.length ? (count('deployed') / rows.length) * 100 : 0}%` }} />
                    </div>
                    <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{made} of {rows.length} visits done ({percent}%) · {rows.length - made} pending</p>
                  </div>
                </div>
                {SQUARES.map((s) => (
                  <button key={s.label} type="button" aria-label={s.label} aria-pressed={statusFilter === s.filter}
                          onClick={() => { setStatusFilter(statusFilter === s.filter ? '' : s.filter); setPage(1); setOpened(null) }}
                          className={`rounded-2xl border px-4 py-4 text-left transition-colors ${statusFilter === s.filter ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'}`}>
                    <span aria-hidden="true" className={`mb-2 flex h-9 w-9 items-center justify-center rounded-full ${s.badge}`}>{s.icon}</span>
                    <span className={`block text-3xl font-semibold leading-tight ${s.tone}`}>{count(s.filter)}</span>
                    <span className={`block text-sm font-semibold ${s.tone}`}>{s.label}</span>
                    <span className="block text-xs text-zinc-500 dark:text-zinc-400">{s.note}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          <div role="search" className="mb-2 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the visits" className={`${inputClass} !pl-9`} placeholder="Search by site, revision, camera, card, who, deployment…" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); setOpened(null) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Status
              <select aria-label="Status" className={`${inputClass} !w-auto`} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as StatusFilter); setPage(1); setOpened(null) }}>
                <option value="">All</option>
                {SQUARES.map((s) => <option key={s.filter} value={s.filter}>{s.label}</option>)}
              </select>
            </label>
          </div>

          {(
            visits === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the visits…</p> : (
              <>
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
                <table className="w-full text-sm" aria-label="Visits">
                  <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                    <tr>
                      {COLUMNS.map(([key, label]) => (
                        <th key={key} scope="col" aria-sort={sort?.key === key ? (sort.descending ? 'descending' : 'ascending') : 'none'} className="px-3 py-2.5 text-left font-medium">
                          <button type="button" className="inline-flex items-center gap-1 font-medium hover:text-zinc-900 dark:hover:text-zinc-100" onClick={() => { setSort(sort?.key === key ? { key, descending: !sort.descending } : { key, descending: false }); setPage(1); setOpened(null) }}>
                            {label}<span aria-hidden="true" className="text-[10px]">{sort?.key === key ? (sort.descending ? '▼' : '▲') : ''}</span>
                          </button>
                        </th>
                      ))}
                      <th scope="col" className="px-3 py-2.5"><span className="sr-only">What to do</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                    {onPage.map((v) => {
                      const key = keyOf(v)
                      return (
                        <Fragment key={key}>
                          <tr ref={focus && opened === key ? (el) => el?.scrollIntoView?.({ block: 'center' }) : undefined}>
                            <td className="px-3 py-2 font-mono">{v.session}</td>
                            <td className="px-3 py-2 font-mono">{v.location_id}</td>
                            <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{v.not_done ? <span className="font-sans text-zinc-400">—</span> : `${v.date} ${v.time.slice(0, 5)}`}</td>
                            <td className="px-3 py-2">{v.actions.join(' + ')}</td>
                            <td className="px-3 py-2">
                              {phaseOf(v)
                                ? <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${PHASE_BADGE[phaseOf(v)!]}`}>{PHASE_LABEL[phaseOf(v)!]}</span>
                                : <span className="text-zinc-400">—</span>}
                            </td>
                            <td className="px-3 py-2">
                              {v.not_done ? null : v.deployment_id ? (
                                <button type="button" className={`${btnOutline} inline-flex items-center gap-1.5 !px-2.5 !py-1 !text-xs whitespace-nowrap text-emerald-700 dark:text-emerald-300`} aria-label={`Details of the deployment ${v.deployment_id}`} onClick={() => onShowDeployment?.(v.deployment_id!)}>
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>Show image details
                                </button>
                              ) : v.deployment_status === 'closed' && onImportImages ? (
                                <button type="button" className={`${btnOutline} !px-2.5 !py-1 !text-xs whitespace-nowrap`} aria-label={`Create the deployment of the visit ${v.session} to ${v.location_id}`} onClick={() => onImportImages({ researchProjectId: project!.acronym, visit: v })}>Create deployment</button>
                              ) : <span role="img" aria-label="Images not stored" title="Not stored: the card has not been collected yet" className="inline-flex text-zinc-400 dark:text-zinc-500">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                                </span>}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {!v.not_done && <div className="flex flex-col gap-1.5 items-stretch">
                                <button type="button" className={`${btnOutline} inline-flex items-center justify-center gap-2`} aria-expanded={opened === key} aria-label={`View the visit ${v.session} to ${v.location_id}`} onClick={() => setOpened(opened === key ? null : key)}>
                                  <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" className="fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>View
                                </button>
                              </div>}
                            </td>
                          </tr>
                          {opened === key && (
                            <tr>
                              <td colSpan={7} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4">
                                <dl aria-label={`Details of the visit ${v.session} to ${v.location_id}`} className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
                                  <div className="flex gap-2"><dt className="text-zinc-500 dark:text-zinc-400">Actions</dt><dd>{v.actions.join(' + ')}</dd></div>
                                  {DETAILS.filter(([k]) => { const value = v[k]; return value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0) })
                                    .map(([k, label]) => <div key={k} className="flex gap-2"><dt className="text-zinc-500 dark:text-zinc-400">{k === 'num_photos' && collectedCard(everyRow, v) ? `Photos collected from the SD card previously installed (${collectedCard(everyRow, v)})` : label}</dt><dd className="font-mono text-xs break-all self-center">{shownValue(v[k])}</dd></div>)}
                                </dl>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                    {shown.length === 0 && <tr><td colSpan={7} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{visits.length === 0 ? 'No visit has been registered to this research project yet.' : 'No visit matches.'}</td></tr>}
                  </tbody>
                </table>
              </div>
              {shown.length > 0 && (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
                  <span role="status" className="text-zinc-500 dark:text-zinc-400">Showing {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, shown.length)} of {shown.length} visits</span>
                  {pages > 1 && <nav className="flex items-center gap-1" aria-label="Pages">
                    <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Previous page" disabled={current === 1} onClick={() => { setPage(current - 1); setOpened(null) }}>‹</button>
                    {pageNumbers(current, pages).map((n, i) => n === null
                      ? <span key={`gap${i}`} className="px-1 text-zinc-400">…</span>
                      : <button key={n} type="button" aria-label={`Page ${n}`} aria-current={n === current ? 'page' : undefined} onClick={() => { setPage(n); setOpened(null) }}
                                className={`px-2.5 py-1 rounded ${n === current ? 'bg-blue-600 text-white' : 'border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300'}`}>{n}</button>)}
                    <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Next page" disabled={current === pages} onClick={() => { setPage(current + 1); setOpened(null) }}>›</button>
                  </nav>}
                </div>
              )}
              </>
            )
          )}
        </>
      )}

      <section aria-label="Legend" className="mt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 text-sm">
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 p-4">
          <h5 className="mb-1.5 font-semibold text-blue-600 dark:text-blue-400">Overall progress</h5>
          <p className="text-zinc-500 dark:text-zinc-400">The share of the visits done, over the revision picked or over all of them, with the ones still pending.</p>
        </div>
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 p-4">
          <h5 className="mb-1.5 font-semibold text-emerald-600 dark:text-emerald-400">Visit states</h5>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {SQUARES.map((s) => <Fragment key={s.filter}><dt className={`font-medium ${s.tone}`}>{s.label}</dt><dd className="text-zinc-500 dark:text-zinc-400">{s.note}</dd></Fragment>)}
          </dl>
        </div>
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 p-4">
          <h5 className="mb-1.5 font-semibold text-violet-600 dark:text-violet-400">Data states</h5>
          <p className="text-zinc-500 dark:text-zinc-400"><span className="font-medium text-zinc-700 dark:text-zinc-200">Images</span>: once the deployment of the visit is made its images are stored — the visit is Stored — and <em>Show image details</em> opens that deployment.</p>
        </div>
        <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 p-4">
          <h5 className="mb-1.5 font-semibold text-sky-600 dark:text-sky-400">Filters and search</h5>
          <p className="text-zinc-500 dark:text-zinc-400">Search by site, revision, camera or card, and filter by status; pick a revision above.</p>
        </div>
      </section>

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
