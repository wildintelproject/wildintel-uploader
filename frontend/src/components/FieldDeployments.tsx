import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { formatDay } from '../dateFormat'
import { btnOutline, inputClass } from '../pages/ImportDeploymentPage'
import type { DeploymentFields, DeploymentUploadState, FieldDeployment } from '../types'
import { pageNumbers } from './CheckFailures'
import { Icon, LegendCard, Ring, StateCard } from './Dashboard'
import RevisionSquares from './RevisionSquares'
import IconButton, { ICON_PATHS } from './IconButton'
import LinkButton from './LinkButton'

/** How many deployments a page has. */
const PER_PAGE = 10

/** Where a deployment is in its life — which says nothing of the camera, that is the visit's, nor of its uploads, which are their own: planned (a card was left, so its deployment is to be made), created (its images are stored) or not created (the camera was stolen, the card is gone: it will not be made — as a visit that could not be made). */
export type Filter = '' | 'planned' | 'created' | 'not_created'
const phaseOf = (d: FieldDeployment): Exclude<Filter, ''> => d.no_images ? 'not_created' : d.images_stored ? 'created' : 'planned'
const matches = (d: FieldDeployment, f: Filter) => !f || phaseOf(d) === f

/** The fields of a deployment the details show, in this order, when it has them. */
const DEPLOYMENT_DETAILS: [keyof DeploymentFields, string][] = [
  ['location_id', 'Location'], ['location_name', 'Location name'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['coordinate_uncertainty', 'Coordinate uncertainty (m)'],
  ['start_date', 'Start'], ['end_date', 'End'], ['setup_by', 'Set up by'], ['camera_id', 'Camera'], ['camera_model', 'Camera model'], ['camera_interval', 'Camera delay (s)'],
  ['camera_height', 'Camera height (m)'], ['camera_depth', 'Camera depth (m)'], ['camera_tilt', 'Camera tilt (°)'], ['camera_heading', 'Camera heading (°)'], ['detection_distance', 'Detection distance (m)'],
  ['timestamp_issues', 'Timestamp issues'], ['bait_use', 'Bait use'], ['feature_type', 'Feature type'], ['habitat', 'Habitat'], ['deployment_groups', 'Deployment groups'], ['tags', 'Tags'], ['comments', 'Notes'],
]
const shownValue = (v: unknown) => (typeof v === 'boolean' ? (v ? 'yes' : 'no') : Array.isArray(v) ? v.join(', ') : String(v))

/** What a destination is called. */
const DESTINATION_NAME: Record<string, string> = { trapper: 'Trapper', agouti: 'Agouti' }
const STATE_NAME: Record<string, string> = { planned: 'planned', done: 'done', failed: 'failed' }

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** The deployments the visits of a research project say, as a book: a square for each revision (collection), the status squares of the one picked, and a table — the one a link of the visit book goes to is highlighted. */
export default function FieldDeployments({ deployments: every, onShowSd, onShowLocation, onShowUploads, highlight, initialFilter = '', onShowVisit, loadDetails, onUpload }: {
  /** Goes to the SD card — its page in the settings, where its state and, if it is archived, why are. */
  onShowSd?: (label: string) => void
  /** Goes to the location — its page in the settings. */
  onShowLocation?: (site: string) => void
  /** Goes to the uploads dashboard, on the uploads of a deployment. */
  onShowUploads?: (deploymentId: string) => void
  deployments: FieldDeployment[]; highlight?: string; initialFilter?: Filter; onShowVisit?: (visit: { session: string; site: string }) => void
  /** Reads what a created deployment says of itself: its details, for its View button. */
  loadDetails?: (deploymentId: string) => Promise<DeploymentFields | null>
  /** Goes to upload the deployment — its revision is what the upload page starts from. */
  onUpload?: (deployment: FieldDeployment) => void
}) {
  // Every card that was left is a deployment to make; the ones whose camera was stolen will not be made (Not created).
  const deployments = every
  // The upload to each uploader in use is its own state, apart from the deployment's: planned from the start, then done or failed.
  const statesOf = (d: FieldDeployment): DeploymentUploadState[] => d.upload_states ?? [
    { destination: 'trapper', state: d.on_trapper ? 'done' : 'planned', kind: d.on_trapper ? (d.uploaded_at ? 'uploaded' : 'synced') : null, uploaded_at: d.uploaded_at ?? null, note: null },
  ]
  const [revision, setRevision] = useState('')
  const [filter, setFilter] = useState<Filter>(initialFilter)
  const [page, setPage] = useState(1)
  const [text, setText] = useState('')
  // a deployment the previous and next buttons go to: it takes the place of the one a link of another page said, and is brought into view
  const [jump, setJump] = useState<string | undefined>(undefined)
  const focus = jump ?? highlight
  // the deployment of the same site in the revision before (-1) or after (1)
  const neighbour = (d: FieldDeployment, step: -1 | 1) => deployments
    .filter((o) => o.site.toLowerCase() === d.site.toLowerCase() && (step < 0 ? o.collection < d.collection : o.collection > d.collection))
    .sort((x, y) => (step < 0 ? y.collection.localeCompare(x.collection) : x.collection.localeCompare(y.collection)))[0]
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
    if (!focus) return
    const target = deployments.find((d) => d.deployment_id === focus)
    if (!target) return
    setRevision(target.collection); setFilter(''); setText('')
    const position = deployments.filter((d) => d.collection === target.collection).findIndex((d) => d.deployment_id === focus)
    setPage(Math.floor(position / PER_PAGE) + 1)
  }, [focus, deployments])
  useEffect(() => { marked.current?.scrollIntoView?.({ block: 'center' }) })

  // of everything that was planned: a deployment that will not be made was planned too
  const percent = inRevision.length > 0 ? Math.round((count('created') / inRevision.length) * 100) : 0
  const SQUARES: { filter: Exclude<Filter, ''>; label: string; note: string; tone: string; badge: string; icon: ReactNode }[] = [
    { filter: 'planned', label: 'Planned', note: 'Images collected: to be created', tone: 'text-zinc-600 dark:text-zinc-300', badge: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>} className="h-5 w-5" /> },
    { filter: 'created', label: 'Created', note: 'Images stored', tone: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300', icon: <Icon path={<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />} className="h-5 w-5" /> },
    { filter: 'not_created', label: 'Not created', note: 'Camera stolen: the card is gone', tone: 'text-red-600 dark:text-red-400', badge: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>} className="h-5 w-5" /> },
  ]

  return (
    <div aria-label="Deployments the visits say" role="region">
      {deployments.length === 0 ? <p className="text-sm text-zinc-500 dark:text-zinc-400">No deployment yet: no visit has left a camera.</p> : (
        <>
          <section aria-label="Revision" className="mb-6">
            <h5 className="text-lg font-semibold mb-1">Revision</h5>
            <RevisionSquares description="A revision is one visit to every site. Pick one to see what is planned and what is done." all={{ label: 'All revisions', note: plural(deployments.length, 'deployment', 'deployments') }} value={revision}
              revisions={revisions.map((r) => ({ id: r, label: r, note: plural(deployments.filter((d) => d.collection === r).length, 'deployment', 'deployments') }))}
              onPick={(id) => { setRevision(id); setFilter(''); setPage(1) }} />
          </section>

          <section aria-label="Deployments by status" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a card to show only those deployments.</p>
            <div className="grid grid-cols-2 lg:grid-cols-[1.6fr_repeat(3,1fr)] gap-3">
              <div className="col-span-2 lg:col-span-1 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4">
                <Ring percent={percent} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{revision ? `Deployments of ${revision}` : 'All the deployments'}</p>
                  <p className="text-2xl font-semibold leading-tight">{count('created')} <span className="text-zinc-400">/ {inRevision.length}</span></p>
                  <div role="progressbar" aria-label="Deployments created" aria-valuemin={0} aria-valuemax={inRevision.length} aria-valuenow={count('created')} className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div className="h-1.5 bg-emerald-500" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{count('created')} created · {count('planned')} to create{count('not_created') > 0 && ` · ${count('not_created')} will not be created`}</p>
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

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Deployments">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Where', 'When', 'SD and photos', 'Creation', 'Upload'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}<th scope="col" className="px-3 py-2.5"><span className="sr-only">What to do</span></th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((d) => (
                  <Fragment key={d.deployment_id}>
                  <tr ref={d.deployment_id === focus ? marked : undefined} aria-current={d.deployment_id === focus ? 'true' : undefined} className={d.deployment_id === focus ? 'bg-blue-50 dark:bg-blue-950/40' : ''}>
                    <td className="px-3 py-3 font-mono text-xs font-semibold">{d.deployment_id}</td>
                    <td className="px-3 py-3 font-mono text-xs">
                      {onShowLocation
                        ? <LinkButton title={`Show the details of the location ${d.site}`} onClick={() => onShowLocation(d.site)}>{d.site}</LinkButton>
                        : d.site}
                    </td>
                    <td className="px-3 py-3">
                      {d.start_session && (onShowVisit
                        ? <LinkButton className="block text-xs font-semibold" aria-label={`Show the visit ${d.start_session} to ${d.site}`} onClick={() => onShowVisit({ session: d.start_session!, site: d.site })}>Visit {d.start_session} · {d.site}</LinkButton>
                        : <span className="block text-xs font-semibold">Visit {d.start_session} · {d.site}</span>)}
                      <span className="block font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</span>
                    </td>
                    <td className="px-3 py-3 text-xs text-zinc-600 dark:text-zinc-400">
                      {d.card && (onShowSd
                        ? <LinkButton className="font-semibold" aria-label={`Show the state of the SD card ${d.card}`} onClick={() => onShowSd(d.card!)}>SD {d.card}</LinkButton>
                        : <>SD {d.card}</>)}
                      {d.card && d.photos_counted != null && ' · '}{d.photos_counted != null && `${d.photos_counted} photos`}
                    </td>
                    <td className="px-3 py-3">
                      {phaseOf(d) === 'not_created'
                        ? <span title="The camera was stolen: the card is gone, so the deployment will not be created" className="rounded-full px-2 py-0.5 text-xs font-semibold bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">Not created</span>
                        : phaseOf(d) === 'planned'
                        ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Planned</span>
                        : <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">Created</span>}
                    </td>
                    <td className="px-3 py-3">
                      {phaseOf(d) === 'created' ? (() => {
                        const states = statesOf(d)
                        const tip = states.map((u) => `${DESTINATION_NAME[u.destination] ?? u.destination}: ${STATE_NAME[u.state] ?? u.state}`).join(' · ')
                        const tick = <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></svg>
                        return states.some((u) => u.state === 'done')
                          ? (onShowUploads
                            ? <button type="button" title={`Uploaded (${tip}). Show its uploads`} aria-label={`Show the uploads of the deployment ${d.deployment_id}`} onClick={() => onShowUploads(d.deployment_id)}
                                      className="inline-flex rounded-full text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">{tick}</button>
                            : <span role="img" title={`Uploaded (${tip})`} aria-label="Uploaded" className="inline-flex text-emerald-600 dark:text-emerald-400">{tick}</span>)
                          : <span role="img" title={`Not uploaded (${tip})`} aria-label="Not uploaded" className="inline-flex text-zinc-400 dark:text-zinc-500">
                              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                            </span>
                      })() : <span className="text-zinc-400">—</span>}
                    </td>
                    <td className="px-3 py-3 whitespace-nowrap">
                      {/* only what can be done with the row: the options that do not apply to it are not there */}
                      <div className="flex items-center justify-end gap-1.5" role="group" aria-label={`Options of the deployment ${d.deployment_id}`}>
                        {(() => {
                          const before = neighbour(d, -1)
                          return before && <IconButton label={`Show the previous deployment of ${d.site} (${before.collection})`} title={`The previous revision of this location: ${before.collection}`} onClick={() => setJump(before.deployment_id)} path={ICON_PATHS.before} />
                        })()}
                        {phaseOf(d) === 'created' && (
                          <IconButton label={`View the deployment ${d.deployment_id}`} title="View the deployment" expanded={opened === d.deployment_id} onClick={() => toggle(d.deployment_id)} path={ICON_PATHS.view} />
                        )}
                        {(() => {
                          const after = neighbour(d, 1)
                          return after && <IconButton label={`Show the next deployment of ${d.site} (${after.collection})`} title={`The next revision of this location: ${after.collection}`} onClick={() => setJump(after.deployment_id)} path={ICON_PATHS.after} />
                        })()}
                        {phaseOf(d) === 'created' && onUpload && statesOf(d).some((u) => u.destination === 'trapper' && u.state !== 'done') && (
                          <IconButton label={`Upload the deployment ${d.deployment_id}`} title={statesOf(d).some((u) => u.state === 'failed') ? 'Upload the images again' : 'Upload the images'} onClick={() => onUpload(d)} path={ICON_PATHS.upload} />
                        )}
                      </div>
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
            <LegendCard title="Creation and uploads" tone="text-violet-600 dark:text-violet-400"><p>A deployment is <em>planned</em> while its card is to be imported and <em>created</em> when its images are stored. <em>Not created</em> is a deployment of a camera that was stolen: the card is gone. Uploading is another thing: each deployment has an upload for every uploader in use, <em>planned</em> from the start, then <em>done</em> or <em>failed</em> — a failed one is tried again.</p></LegendCard>
            <LegendCard title="Filters and search" tone="text-sky-600 dark:text-sky-400"><p>Search by deployment, site, card or camera, and filter by status; pick a revision above.</p></LegendCard>
          </section>
        </>
      )}
    </div>
  )
}
