import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { formatDay } from '../dateFormat'
import { btnOutline, inputClass } from '../pages/ImportDeploymentPage'
import type { DeploymentFields, FieldDeployment } from '../types'
import { pageNumbers } from './CheckFailures'
import { Icon, LegendCard, Ring, StateCard } from './Dashboard'
import RevisionSquares from './RevisionSquares'

/** How many deployments a page has. */
const PER_PAGE = 10

/** Where a deployment is in its life — which says nothing of the camera, that is the visit's: not created (its images are not stored yet), created (its images are stored: the visit is Stored), uploaded (its information is on Trapper), or with no images (the camera was stolen: there are none, and never will be). */
export type Filter = '' | 'not_created' | 'created' | 'uploaded' | 'no_images'
const phaseOf = (d: FieldDeployment): Exclude<Filter, ''> => d.no_images ? 'no_images' : d.on_trapper ? 'uploaded' : d.images_stored ? 'created' : 'not_created'
const matches = (d: FieldDeployment, f: Filter) => !f || phaseOf(d) === f

/** The fields of a deployment the details show, in this order, when it has them. */
const DEPLOYMENT_DETAILS: [keyof DeploymentFields, string][] = [
  ['location_id', 'Location'], ['location_name', 'Location name'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['coordinate_uncertainty', 'Coordinate uncertainty (m)'],
  ['start_date', 'Start'], ['end_date', 'End'], ['setup_by', 'Set up by'], ['camera_id', 'Camera'], ['camera_model', 'Camera model'], ['camera_interval', 'Camera delay (s)'],
  ['camera_height', 'Camera height (m)'], ['camera_depth', 'Camera depth (m)'], ['camera_tilt', 'Camera tilt (°)'], ['camera_heading', 'Camera heading (°)'], ['detection_distance', 'Detection distance (m)'],
  ['timestamp_issues', 'Timestamp issues'], ['bait_use', 'Bait use'], ['feature_type', 'Feature type'], ['habitat', 'Habitat'], ['deployment_groups', 'Deployment groups'], ['tags', 'Tags'], ['comments', 'Notes'],
]
const shownValue = (v: unknown) => (typeof v === 'boolean' ? (v ? 'yes' : 'no') : Array.isArray(v) ? v.join(', ') : String(v))

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** The deployments the visits of a research project say, as a book: a square for each revision (collection), the status squares of the one picked, and a table — the one a link of the visit book goes to is highlighted. */
export default function FieldDeployments({ deployments, highlight, initialFilter = '', belowSummary, onShowVisit, loadDetails }: {
  deployments: FieldDeployment[]; highlight?: string; initialFilter?: Filter; belowSummary?: ReactNode; onShowVisit?: (visit: { session: string; site: string }) => void
  /** Reads what a created deployment says of itself: its details, for its View button. */
  loadDetails?: (deploymentId: string) => Promise<DeploymentFields | null>
}) {
  const [revision, setRevision] = useState('')
  const [filter, setFilter] = useState<Filter>(initialFilter)
  const [page, setPage] = useState(1)
  const [text, setText] = useState('')
  // the deployment whose details are open
  const [opened, setOpened] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, DeploymentFields | null | 'error'>>({})
  function toggle(id: string) {
    if (opened === id) { setOpened(null); return }
    setOpened(id)
    if (loadDetails && !(id in details)) loadDetails(id).then((fields) => setDetails((d) => ({ ...d, [id]: fields }))).catch(() => setDetails((d) => ({ ...d, [id]: 'error' })))
  }
  const revisions = [...new Set(deployments.map((d) => d.collection))].sort((a, b) => b.localeCompare(a))
  const inRevision = revision ? deployments.filter((d) => d.collection === revision) : deployments
  const needle = text.trim().toLowerCase()
  const shown = inRevision.filter((d) => matches(d, filter)).filter((d) => !needle || `${d.deployment_id} ${d.site} ${d.collection} ${d.card ?? ''} ${d.camera_id ?? ''} ${phaseOf(d)}`.replace('_', ' ').toLowerCase().includes(needle))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const count = (f: Filter) => inRevision.filter((d) => matches(d, f)).length

  // the one a link of the visit book goes to is brought into view, on its revision and on its page
  const marked = useRef<HTMLTableRowElement | null>(null)
  useEffect(() => {
    if (!highlight) return
    const target = deployments.find((d) => d.deployment_id === highlight)
    if (!target) return
    setRevision(target.collection); setFilter('')
    const position = deployments.filter((d) => d.collection === target.collection).findIndex((d) => d.deployment_id === highlight)
    setPage(Math.floor(position / PER_PAGE) + 1)
  }, [highlight, deployments])
  useEffect(() => { marked.current?.scrollIntoView?.({ block: 'center' }) })

  const percent = inRevision.length - count('no_images') > 0 ? Math.round(((count('created') + count('uploaded')) / (inRevision.length - count('no_images') || 1)) * 100) : 0
  const SQUARES: { filter: Exclude<Filter, ''>; label: string; note: string; tone: string; badge: string; icon: ReactNode }[] = [
    { filter: 'not_created', label: 'Not created', note: 'Images collected, not stored', tone: 'text-zinc-600 dark:text-zinc-300', badge: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>} className="h-5 w-5" /> },
    { filter: 'created', label: 'Created', note: 'Images stored, not uploaded yet', tone: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300', icon: <Icon path={<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />} className="h-5 w-5" /> },
    { filter: 'uploaded', label: 'Uploaded', note: 'Information uploaded', tone: 'text-blue-600 dark:text-blue-400', badge: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300', icon: <Icon path={<><path d="M20 16.2A4.5 4.5 0 0017.5 8h-1.8A7 7 0 104 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} className="h-5 w-5" /> },
    { filter: 'no_images', label: 'No images', note: 'Camera stolen: nothing collected', tone: 'text-red-600 dark:text-red-400', badge: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300', icon: <Icon path={<><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5v.01" /></>} className="h-5 w-5" /> },
  ]

  return (
    <div aria-label="Deployments the visits say" role="region">
      {deployments.length === 0 ? <p className="text-sm text-zinc-500 dark:text-zinc-400">No deployment yet: no visit has left a camera.</p> : (
        <>
          <section aria-label="Revision" className="mb-6">
            <h5 className="text-lg font-semibold mb-1">Revision</h5>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">A revision is one visit to every site. Pick one to see what is planned and what is done.</p>
            <RevisionSquares all={{ label: 'All revisions', note: plural(deployments.length, 'deployment', 'deployments') }} value={revision}
              revisions={revisions.map((r) => ({ id: r, label: r, note: plural(deployments.filter((d) => d.collection === r).length, 'deployment', 'deployments') }))}
              onPick={(id) => { setRevision(id); setFilter(''); setPage(1) }} />
          </section>

          <section aria-label="Deployments by status" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a card to show only those deployments.</p>
            <div className="grid grid-cols-2 lg:grid-cols-[1.6fr_repeat(4,1fr)] gap-3">
              <div className="col-span-2 lg:col-span-1 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4">
                <Ring percent={percent} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{revision ? `Deployments of ${revision}` : 'All the deployments'}</p>
                  <p className="text-2xl font-semibold leading-tight">{count('created') + count('uploaded')} <span className="text-zinc-400">/ {inRevision.length - count('no_images')}</span></p>
                  <div role="progressbar" aria-label="Deployments created" aria-valuemin={0} aria-valuemax={inRevision.length - count('no_images')} aria-valuenow={count('created') + count('uploaded')} className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div className="h-1.5 bg-emerald-500" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{count('created') + count('uploaded')} created · {count('not_created')} to create{count('no_images') > 0 && ` · ${count('no_images')} with no images`}</p>
                </div>
              </div>
              {SQUARES.map((q) => (
                <StateCard key={q.filter} label={q.label} note={q.note} count={count(q.filter)} tone={q.tone} badge={q.badge} icon={q.icon} pressed={filter === q.filter}
                           onPress={() => { setFilter(filter === q.filter ? '' : q.filter); setPage(1) }} />
              ))}
            </div>
          </section>

          <div role="search" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the deployments" className={`${inputClass} !pl-9`} placeholder="Search by deployment, site, card, camera…" value={text} onChange={(e) => { setText(e.target.value); setPage(1) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Status
              <select aria-label="Status" className={`${inputClass} !w-auto`} value={filter} onChange={(e) => { setFilter(e.target.value as Filter); setPage(1) }}>
                <option value="">All</option>
                {SQUARES.map((q) => <option key={q.filter} value={q.filter}>{q.label}</option>)}
              </select>
            </label>
          </div>

          {belowSummary}

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Deployments">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Where', 'When', 'Card and photos', 'Creation', 'Upload'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}<th scope="col" className="px-3 py-2.5"><span className="sr-only">What to do</span></th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((d) => (
                  <Fragment key={d.deployment_id}>
                  <tr ref={d.deployment_id === highlight ? marked : undefined} aria-current={d.deployment_id === highlight ? 'true' : undefined} className={d.deployment_id === highlight ? 'bg-blue-50 dark:bg-blue-950/40' : ''}>
                    <td className="px-3 py-3 font-mono text-xs font-semibold">{d.deployment_id}</td>
                    <td className="px-3 py-3 font-mono text-xs">{d.site}</td>
                    <td className="px-3 py-3">
                      {d.start_session && (onShowVisit
                        ? <button type="button" className="block text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline" aria-label={`Show the visit ${d.start_session} to ${d.site}`} onClick={() => onShowVisit({ session: d.start_session!, site: d.site })}>Visit {d.start_session} · {d.site}</button>
                        : <span className="block text-xs font-semibold">Visit {d.start_session} · {d.site}</span>)}
                      <span className="block font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</span>
                    </td>
                    <td className="px-3 py-3 text-xs text-zinc-600 dark:text-zinc-400">{[d.card && `Card ${d.card}`, d.photos_counted != null && `${d.photos_counted} photos`].filter(Boolean).join(' · ')}</td>
                    <td className="px-3 py-3">
                      {phaseOf(d) === 'no_images'
                        ? <span title="The camera was stolen: nothing was collected" className="rounded-full px-2 py-0.5 text-xs font-semibold bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">No images</span>
                        : phaseOf(d) === 'not_created'
                        ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not created</span>
                        : <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">Created</span>}
                    </td>
                    <td className="px-3 py-3">
                      {phaseOf(d) === 'uploaded'
                        ? <span title={d.uploaded_at ? `Uploaded on ${d.uploaded_at.slice(0, 10)}` : 'Uploaded: synced from there'} className="rounded-full px-2 py-0.5 text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">Uploaded</span>
                        : phaseOf(d) === 'created'
                        ? <span title="Not uploaded yet" className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not uploaded</span>
                        : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {phaseOf(d) !== 'not_created' && phaseOf(d) !== 'no_images' && (
                        <button type="button" className={`${btnOutline} inline-flex items-center justify-center gap-2`} aria-expanded={opened === d.deployment_id} aria-label={`View the deployment ${d.deployment_id}`} onClick={() => toggle(d.deployment_id)}>
                          <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" className="fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>View
                        </button>
                      )}
                    </td>
                  </tr>
                  {opened === d.deployment_id && (
                    <tr>
                      <td colSpan={7} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4">
                        {details[d.deployment_id] === undefined ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployment…</p>
                          : details[d.deployment_id] === 'error' || details[d.deployment_id] === null ? <p role="alert" className="text-sm text-amber-700 dark:text-amber-400">The details of this deployment could not be read from the collections folder.</p>
                          : (
                            <dl aria-label={`Details of the deployment ${d.deployment_id}`} className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
                              {DEPLOYMENT_DETAILS.filter(([k]) => { const value = (details[d.deployment_id] as DeploymentFields)[k]; return value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0) })
                                .map(([k, label]) => <div key={k} className="flex gap-2"><dt className="text-zinc-500 dark:text-zinc-400">{label}</dt><dd className="font-mono text-xs break-all self-center">{shownValue((details[d.deployment_id] as DeploymentFields)[k])}</dd></div>)}
                            </dl>
                          )}
                      </td>
                    </tr>
                  )}
                  </Fragment>
                ))}
                {shown.length === 0 && <tr><td colSpan={7} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No deployment matches.</td></tr>}
              </tbody>
            </table>
          </div>

          {shown.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
              <span role="status" className="text-zinc-500 dark:text-zinc-400">Showing {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, shown.length)} of {shown.length} deployments</span>
              {pages > 1 && <nav className="flex items-center gap-1" aria-label="Pages">
                <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Previous page" disabled={current === 1} onClick={() => setPage(current - 1)}>‹</button>
                {pageNumbers(current, pages).map((n, i) => n === null
                  ? <span key={`gap${i}`} className="px-1 text-zinc-400">…</span>
                  : <button key={n} type="button" aria-label={`Page ${n}`} aria-current={n === current ? 'page' : undefined} onClick={() => setPage(n)}
                            className={`px-2.5 py-1 rounded ${n === current ? 'bg-blue-600 text-white' : 'border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300'}`}>{n}</button>)}
                <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Next page" disabled={current === pages} onClick={() => setPage(current + 1)}>›</button>
              </nav>}
            </div>
          )}
          <section aria-label="Legend" className="mt-8 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 text-sm">
            <LegendCard title="Overall progress" tone="text-blue-600 dark:text-blue-400"><p>The share of the deployments that are created — their images are stored — over the revision picked or over all of them.</p></LegendCard>
            <LegendCard title="Deployment states" tone="text-emerald-600 dark:text-emerald-400">
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                {SQUARES.map((q) => <Fragment key={q.filter}><dt className={`font-medium ${q.tone}`}>{q.label}</dt><dd>{q.note}</dd></Fragment>)}
              </dl>
            </LegendCard>
            <LegendCard title="Creation and upload" tone="text-violet-600 dark:text-violet-400"><p>A deployment is <em>created</em> when its images are stored (the visit that started it is then Stored) and <em>uploaded</em> when its information is on the platform it is uploaded to. The camera still out, or the card not imported, is the state of the visit, not of the deployment. <em>No images</em> is a deployment closed by a theft: nothing was collected, and it is left out of the progress.</p></LegendCard>
            <LegendCard title="Filters and search" tone="text-sky-600 dark:text-sky-400"><p>Search by deployment, site, card or camera, and filter by status; pick a revision above.</p></LegendCard>
          </section>
        </>
      )}
    </div>
  )
}
