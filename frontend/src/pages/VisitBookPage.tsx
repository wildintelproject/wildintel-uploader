import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import type { BookVisit, ClosedVisitTarget } from '../types'
import { btnOutline, btnPrimary, inputClass } from './ImportDeploymentPage'

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
type SortKey = 'session' | 'where' | 'when' | 'status' | 'actions' | 'stored' | 'trapper'
const COLUMNS: [SortKey, string][] = [['session', 'Revision'], ['where', 'Where'], ['when', 'When'], ['actions', 'Actions'], ['status', 'Status'], ['stored', 'Images stored'], ['trapper', 'On Trapper']]

/** What a row says in a column, to sort by it: the rows not made go last whatever the direction (they have no day, no actions…). */
function sortValue(v: BookVisit, key: SortKey): string | number {
  switch (key) {
    case 'session': return v.session
    case 'where': return v.location_id.toLowerCase()
    case 'when': return `${v.date}T${v.time}`
    case 'status': return v.not_done ? 2 : v.deployment_status === 'closed' ? 0 : v.deployment_status === 'open' ? 1 : 3
    case 'actions': return v.actions.join(' + ').toLowerCase()
    case 'stored': return v.deployment_id ? 0 : v.deployment_status === 'closed' ? 1 : 2 // stored, to create, not stored
    case 'trapper': return v.on_trapper ? 0 : 1
  }
}

/** The rows the status squares show: all, the ones not made, the open ones, the closed ones, and the closed ones whose deployment is not created yet. */
type StatusFilter = '' | 'not_done' | 'open' | 'closed' | 'to_create'
const matches = (v: BookVisit, f: StatusFilter) => !f || (f === 'not_done' ? v.not_done : f === 'to_create' ? v.deployment_status === 'closed' && !v.deployment_id : v.deployment_status === f)

/** How many visits a page of the book has. */
const PER_PAGE = 10

/** The visit book of a research project: the visits kept to it, and the deployments they say — closed, and the ones whose camera is still out — with the logs of their collections. */
export default function VisitBookPage({ onBack, onImportImages, onOpenSettings, settingsOpen, onShowDeployment }: Props) {
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
  const SQUARES: { filter: StatusFilter; label: string; note: string; tone: string }[] = [
    { filter: '', label: 'All the visits', note: revision ? 'planned for this revision' : 'planned for this project', tone: 'text-zinc-900 dark:text-zinc-100' },
    { filter: 'not_done', label: 'Not done', note: 'no visit yet', tone: 'text-zinc-500 dark:text-zinc-400' },
    { filter: 'open', label: 'Open', note: 'camera visited, card not collected', tone: 'text-amber-600 dark:text-amber-400' },
    { filter: 'closed', label: 'Closed', note: 'card collected', tone: 'text-emerald-600 dark:text-emerald-400' },
    { filter: 'to_create', label: 'No deployment yet', note: 'closed, ready to create', tone: 'text-blue-600 dark:text-blue-400' },
  ]

  const needle = filter.trim().toLowerCase()
  const shown = rows
    .filter((v) => matches(v, statusFilter))
    .filter((v) => !needle || `${v.location_id} ${v.session} ${v.camera_id ?? ''} ${v.sd ?? ''} ${v.trappers ?? ''} ${v.actions.join(' ')} ${v.deployment_id ?? ''} ${v.deployment_status ?? ''} ${v.not_done ? 'not done' : ''}`.toLowerCase().includes(needle))
    // by the column chosen — the rows not made last —, else the latest revision first, within it the visits made newest first and then the ones not made, by site
    .sort((a, b) => {
      const byDefault = () => b.session.localeCompare(a.session) || Number(a.not_done) - Number(b.not_done) || (a.not_done ? a.location_id.localeCompare(b.location_id) : `${b.date}T${b.time}`.localeCompare(`${a.date}T${a.time}`))
      if (!sort) return byDefault()
      if (a.not_done !== b.not_done && ['when', 'actions', 'stored', 'trapper'].includes(sort.key)) return Number(a.not_done) - Number(b.not_done)
      const x = sortValue(a, sort.key), y = sortValue(b, sort.key)
      const order = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
      return (sort.descending ? -order : order) || byDefault()
    })
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Visit book</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">The visits kept to a research project.</p>

      <DefaultResearchProject project={project} defaultAcronym={defaultAcronym} of="The book" onOpenSettings={onOpenSettings} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {project && (
        <>
          {visits !== null && revisions.length > 0 && (
            <section aria-label="Revision" className="mb-6">
              <h5 className="text-lg font-semibold mb-1">Revision</h5>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">A revision is one visit to every site. Pick one to see what is planned and what is done.</p>
              <div className="flex flex-wrap gap-3">
                {[{ id: '', label: 'All revisions', of: everyRow }, ...revisions.map((r) => ({ id: r, label: r, of: everyRow.filter((v) => v.session === r) }))].map((r) => (
                  <button key={r.label} type="button" aria-pressed={revision === r.id} onClick={() => { setRevision(r.id); setStatusFilter(''); setPage(1); setOpened(null) }}
                          className={`rounded-xl border px-5 py-3 text-left transition-colors ${revision === r.id ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'}`}>
                    <span className="block font-mono text-lg font-semibold">{r.label}</span>
                    <span className="block text-sm text-zinc-500 dark:text-zinc-400">{r.of.filter((v) => !v.not_done).length} of {r.of.length} done</span>
                  </button>
                ))}
              </div>
            </section>
          )}
          {visits !== null && (
            <section aria-label="Visits by status" className="mb-5">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <h5 className="text-lg font-semibold">{revision ? `Revision ${revision}: visits by status` : 'Visits by status'}</h5>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">Pick a square to show only those visits.</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                {SQUARES.map((s) => (
                  <button key={s.label} type="button" aria-pressed={statusFilter === s.filter}
                          onClick={() => { setStatusFilter(statusFilter === s.filter ? '' : s.filter); setPage(1); setOpened(null) }}
                          className={`rounded-xl border px-4 py-3 text-left transition-colors ${statusFilter === s.filter ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'}`}>
                    <span className="block text-xs font-semibold text-zinc-600 dark:text-zinc-300">{s.label}</span>
                    <span className={`block text-3xl font-semibold leading-tight ${s.tone}`}>{count(s.filter)}</span>
                    <span className="block text-xs text-zinc-500 dark:text-zinc-400">{s.note}</span>
                  </button>
                ))}
              </div>
              <div role="progressbar" aria-label="Visits done" aria-valuemin={0} aria-valuemax={rows.length} aria-valuenow={made} className="mt-3 flex h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                <div className="bg-emerald-500" style={{ width: `${rows.length ? (count('closed') / rows.length) * 100 : 0}%` }} />
                <div className="bg-amber-500" style={{ width: `${rows.length ? (count('open') / rows.length) * 100 : 0}%` }} />
              </div>
              <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">{made} of {rows.length} visits done ({rows.length ? Math.round((made / rows.length) * 100) : 0}%)</p>
            </section>
          )}

          {<div className="mb-3 flex justify-end">
            <input aria-label="Filter the visits" className={`${inputClass} !w-64`} placeholder="Site, revision, camera, card, who, deployment…" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); setOpened(null) }} />
          </div>}

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
                      const key = `${v.session}|${v.location_id}|${v.date}|${v.time}`
                      return (
                        <Fragment key={key}>
                          <tr>
                            <td className="px-3 py-2 font-mono">{v.session}</td>
                            <td className="px-3 py-2 font-mono">{v.location_id}</td>
                            <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{v.not_done ? <span className="font-sans text-zinc-400">—</span> : `${v.date} ${v.time.slice(0, 5)}`}</td>
                            <td className="px-3 py-2">{v.actions.join(' + ')}</td>
                            <td className="px-3 py-2">
                              {v.not_done
                                ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not done</span>
                                : v.deployment_status
                                ? <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${v.deployment_status === 'closed' ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'}`}>{v.deployment_status === 'closed' ? 'Closed' : 'Open'}</span>
                                : <span className="text-zinc-400">—</span>}
                            </td>
                            <td className="px-3 py-2">
                              {v.not_done ? null : v.deployment_id ? (
                                <span className="inline-flex items-center gap-2">
                                  <span role="img" aria-label="Images stored" className="inline-flex text-emerald-600 dark:text-emerald-400">
                                    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                                  </span>
                                  <button type="button" className="text-xs text-blue-600 dark:text-blue-400 hover:underline" aria-label={`Details of the deployment ${v.deployment_id}`} onClick={() => onShowDeployment?.(v.deployment_id!)}>Deployment details</button>
                                </span>
                              ) : v.deployment_status === 'closed' && onImportImages ? (
                                <button type="button" className={`${btnPrimary} !px-2.5 !py-1 !text-xs whitespace-nowrap`} aria-label={`Create the deployment of the visit ${v.session} to ${v.location_id}`} onClick={() => onImportImages({ researchProjectId: project!.acronym, visit: v })}>Create deployment</button>
                              ) : <span role="img" aria-label="Images not stored" title="Not stored: the card has not been collected yet" className="inline-flex text-zinc-400 dark:text-zinc-500">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                                </span>}
                            </td>
                            <td className="px-3 py-2">
                              {v.not_done ? null : v.on_trapper ? (
                                <span role="img" aria-label="On Trapper" title={v.uploaded_at ? `Uploaded to Trapper on ${v.uploaded_at.slice(0, 10)}` : 'On Trapper: synced from there'} className="inline-flex text-emerald-600 dark:text-emerald-400">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                                </span>
                              ) : (
                                <span role="img" aria-label="Not on Trapper" title="Not uploaded to Trapper" className="inline-flex text-zinc-400 dark:text-zinc-500">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                                </span>
                              )}
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
                              <td colSpan={8} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4">
                                <dl aria-label={`Details of the visit ${v.session} to ${v.location_id}`} className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
                                  <div className="flex gap-2"><dt className="text-zinc-500 dark:text-zinc-400">Actions</dt><dd>{v.actions.join(' + ')}</dd></div>
                                  {DETAILS.filter(([k]) => { const value = v[k]; return value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0) })
                                    .map(([k, label]) => <div key={k} className="flex gap-2"><dt className="text-zinc-500 dark:text-zinc-400">{label}</dt><dd className="font-mono text-xs break-all self-center">{shownValue(v[k])}</dd></div>)}
                                </dl>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                    {shown.length === 0 && <tr><td colSpan={8} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{visits.length === 0 ? 'No visit has been registered to this research project yet.' : 'No visit matches.'}</td></tr>}
                  </tbody>
                </table>
              </div>
              {shown.length > PER_PAGE && (
                <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
                  <span role="status" className="text-zinc-500 dark:text-zinc-400">Visits {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, shown.length)} of {shown.length}</span>
                  <nav className="flex items-center gap-1" aria-label="Pages">
                    <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Previous page" disabled={current === 1} onClick={() => { setPage(current - 1); setOpened(null) }}>‹</button>
                    {pageNumbers(current, pages).map((n, i) => n === null
                      ? <span key={`gap${i}`} className="px-1 text-zinc-400">…</span>
                      : <button key={n} type="button" aria-label={`Page ${n}`} aria-current={n === current ? 'page' : undefined} onClick={() => { setPage(n); setOpened(null) }}
                                className={`px-2.5 py-1 rounded ${n === current ? 'bg-blue-600 text-white' : 'border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300'}`}>{n}</button>)}
                    <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Next page" disabled={current === pages} onClick={() => { setPage(current + 1); setOpened(null) }}>›</button>
                  </nav>
                </div>
              )}
              </>
            )
          )}
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
