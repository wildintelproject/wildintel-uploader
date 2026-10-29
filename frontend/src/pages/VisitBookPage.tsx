import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import FieldDeployments from '../components/FieldDeployments'
import { defaultResearchProject } from '../defaultResearchProject'
import type { BookVisit, ClosedVisitTarget, FieldDeployment, LocalResearchProject } from '../types'
import { btnOutline, btnPrimary, inputClass } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
  /** Goes to Import deployment for a closed visit: its research project, and the visit whose card was collected — the deployment is of it. */
  onImportImages?: (target: ClosedVisitTarget) => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  /** Whether the settings are open: the default research project is read again when they are closed, as it may have been changed. */
  settingsOpen?: boolean
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

type View = 'visits' | 'deployments'

/** How many visits a page of the book has. */
const PER_PAGE = 10

/** The visit book of a research project: the visits kept to it, and the deployments they say — closed, and the ones whose camera is still out — with the logs of their collections. */
export default function VisitBookPage({ onBack, onImportImages, onOpenSettings, settingsOpen }: Props) {
  // The book is of the research project the general settings say is the default: the one that is active.
  const [project, setProject] = useState<LocalResearchProject | undefined>(undefined)
  const [defaultAcronym, setDefaultAcronym] = useState<string | null>(null)
  const [view, setView] = useState<View>('visits')
  const [visits, setVisits] = useState<BookVisit[] | null>(null)
  const [opened, setOpened] = useState<string | null>(null)
  const [deployments, setDeployments] = useState<FieldDeployment[] | null>(null)
  const [filter, setFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<'' | 'closed' | 'open' | 'not_done'>('')
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (settingsOpen) return
    let cancelled = false
    void (async () => {
      const acronym = await defaultResearchProject()
      if (cancelled) return
      setDefaultAcronym(acronym)
      try {
        const { results } = await api.listResearchProjects()
        if (!cancelled) setProject(results.find((p) => p.acronym.toLowerCase() === acronym.toLowerCase()))
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the research projects.')
      }
    })()
    return () => { cancelled = true }
  }, [settingsOpen])

  useEffect(() => {
    setVisits(null); setDeployments(null); setError(null); setPage(1); setOpened(null)
    if (!project) return
    let cancelled = false
    api.visitBook(project.acronym)
      .then(({ results }) => { if (!cancelled) setVisits(results) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the visits.') })
    api.fieldDeployments(project.acronym)
      .then(({ results }) => { if (!cancelled) setDeployments(results) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the deployments.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  const needle = filter.trim().toLowerCase()
  const shown = (visits ?? [])
    .filter((v) => !statusFilter || (statusFilter === 'not_done' ? v.not_done : v.deployment_status === statusFilter))
    .filter((v) => !needle || `${v.location_id} ${v.session} ${v.camera_id ?? ''} ${v.sd ?? ''} ${v.trappers ?? ''} ${v.actions.join(' ')} ${v.deployment_id ?? ''} ${v.deployment_status ?? ''} ${v.not_done ? 'not done' : ''}`.toLowerCase().includes(needle))
    // the latest session first; within it the visits made, the newest first, then the ones not made, by site
    .sort((a, b) => b.session.localeCompare(a.session) || Number(a.not_done) - Number(b.not_done) || (a.not_done ? a.location_id.localeCompare(b.location_id) : `${b.date}T${b.time}`.localeCompare(`${a.date}T${a.time}`)))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Visit book</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">The visits kept to a research project, and the deployments they say.</p>

      <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 px-6 py-5 mb-5">
        <h5 className="text-base font-semibold mb-2">Research project</h5>
        {project ? (
          <p className="text-base"><span className="font-mono font-semibold">{project.acronym}</span> — {project.name}</p>
        ) : defaultAcronym === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the settings…</p>
          : defaultAcronym ? <p className="text-sm text-amber-700 dark:text-amber-400">The default research project, <span className="font-mono">{defaultAcronym}</span>, is not in the collections folder.</p>
          : <p className="text-sm text-amber-700 dark:text-amber-400">No default research project is set.</p>}
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          The book is of the default research project.{' '}
          {onOpenSettings
            ? <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline" onClick={() => onOpenSettings('general')}>Change it in the settings</button>
            : 'Change it in Settings › General.'}
        </p>
      </div>

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {project && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex overflow-hidden rounded-lg border border-zinc-300 dark:border-zinc-700" role="tablist" aria-label="Show">
              {([['visits', 'Visits', visits?.filter((v) => !v.not_done).length], ['deployments', 'Deployments', deployments?.length]] as const).map(([id, label, n]) => (
                <button key={id} type="button" role="tab" aria-selected={view === id} onClick={() => setView(id)}
                        className={`px-4 py-2.5 text-sm font-medium border-l first:border-l-0 border-zinc-300 dark:border-zinc-700 ${view === id ? 'bg-blue-600 text-white' : 'text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>{label}{n !== undefined ? ` ${n}` : ''}</button>
              ))}
            </div>
            {view === 'visits' && <select aria-label="Filter by status" className={`${inputClass} !w-40`} value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as typeof statusFilter); setPage(1); setOpened(null) }}>
              <option value="">All the visits</option><option value="closed">Closed</option><option value="open">Open</option><option value="not_done">Not done</option>
            </select>}
            {view === 'visits' && <input aria-label="Filter the visits" className={`${inputClass} !w-64`} placeholder="Site, session, camera, card, who, deployment…" value={filter} onChange={(e) => { setFilter(e.target.value); setPage(1); setOpened(null) }} />}
          </div>

          {view === 'visits' && (
            visits === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the visits…</p> : (
              <>
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
                <table className="w-full text-sm" aria-label="Visits">
                  <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                    <tr>{['Session', 'Where', 'When', 'Status', 'Actions', 'Images stored', ''].map((h, i) => <th key={i} scope="col" className="px-3 py-2.5 text-left font-medium">{h || <span className="sr-only">What to do</span>}</th>)}</tr>
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
                            <td className="px-3 py-2">
                              {v.not_done
                                ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not done</span>
                                : v.deployment_status
                                ? <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${v.deployment_status === 'closed' ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'}`}>{v.deployment_status === 'closed' ? 'Closed' : 'Open'}</span>
                                : <span className="text-zinc-400">—</span>}
                            </td>
                            <td className="px-3 py-2">{v.actions.join(' + ')}</td>
                            <td className="px-3 py-2">
                              {v.not_done ? null : v.deployment_id ? (
                                <span role="img" aria-label={`Images stored: ${v.deployment_id}`} title={v.deployment_id} className="inline-flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                                  <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">{v.deployment_id}</span>
                                </span>
                              ) : v.deployment_status === 'closed' && onImportImages ? (
                                <button type="button" className={`${btnPrimary} !px-2.5 !py-1 !text-xs whitespace-nowrap`} aria-label={`Create the deployment of the visit ${v.session} to ${v.location_id}`} onClick={() => onImportImages({ researchProjectId: project!.acronym, visit: v })}>Create deployment</button>
                              ) : <span role="img" aria-label="Images not stored" title="Not stored: the card has not been collected yet" className="inline-flex text-zinc-400 dark:text-zinc-500">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                                </span>}
                            </td>
                            <td className="px-3 py-2 whitespace-nowrap">
                              {!v.not_done && <div className="flex flex-col gap-1.5 items-stretch">
                                <button type="button" className={`${btnOutline} !px-2.5 !py-1 !text-xs`} aria-expanded={opened === key} aria-label={`Details of the visit ${v.session} to ${v.location_id}`} onClick={() => setOpened(opened === key ? null : key)}>Details</button>
                              </div>}
                            </td>
                          </tr>
                          {opened === key && (
                            <tr>
                              <td colSpan={7} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4">
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
                    {shown.length === 0 && <tr><td colSpan={7} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{visits.length === 0 ? 'No visit has been registered to this research project yet.' : 'No visit matches.'}</td></tr>}
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

          {view === 'deployments' && (
            <>
              {deployments === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p> : <FieldDeployments deployments={deployments} />}
            </>
          )}
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
