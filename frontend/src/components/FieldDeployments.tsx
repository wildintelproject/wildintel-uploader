import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react'
import { formatDay } from '../dateFormat'
import type { DeploymentFields, DeploymentUploadState, FieldDeployment } from '../types'
import { Icon, StateCard } from './Dashboard'
import { ActiveFilters, ChevronCell, DetailLine, DetailsRow, HELP_ICONS, HelpCard, HelpDrawer, MetricsSection, ProgressCard, RevisionSelection, RowOptions, TABLE, TableCard, TableFooter, TableToolbar } from './DashboardParts'
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
export default function FieldDeployments({ deployments: every, onShowSd, onShowLocation, onShowUploads, highlight, initialFilter = '', onShowVisit, loadDetails, onUpload, onCreate, helpOpen = false, onCloseHelp }: {
  /** The help and the legend are open: the panel that says them is this component's, as it knows the states. */
  helpOpen?: boolean
  onCloseHelp?: () => void
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
  /** Goes to create the deployment — to import its images — of one that is planned and whose card was already collected. */
  onCreate?: (deployment: FieldDeployment) => void
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
  // The revisions and the status cards fold away, to leave the table alone.
  const [revisionsOpen, setRevisionsOpen] = useState(true)
  const [metricsOpen, setMetricsOpen] = useState(true)
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
          <RevisionSelection open={revisionsOpen} onToggle={() => setRevisionsOpen(!revisionsOpen)} hint="Select one to filter its deployments"
            all={{ label: 'All revisions', note: plural(deployments.length, 'deployment', 'deployments'), percent: deployments.length > 0 ? Math.round((deployments.filter((d) => phaseOf(d) === 'created').length / deployments.length) * 100) : 0 }} value={revision}
            revisions={revisions.map((r) => ({ id: r, label: r, note: plural(deployments.filter((d) => d.collection === r).length, 'deployment', 'deployments') }))}
            onPick={(id) => { setRevision(id); setFilter(''); setPage(1) }} />

          <MetricsSection label="Deployments by status" open={metricsOpen} onToggle={() => setMetricsOpen(!metricsOpen)} hint="Click a card to filter the table by status">
            <ProgressCard percent={percent} done={count('created')} total={inRevision.length} barLabel="Deployments created" segments={[{ width: percent, className: 'bg-emerald-500' }]}
                          caption={`${count('created')} created · ${count('planned')} to create${count('not_created') > 0 ? ` · ${count('not_created')} will not be created` : ''}`} />
            {SQUARES.map((q) => (
              <StateCard key={q.filter} label={q.label} note={q.note} count={count(q.filter)} tone={q.tone} badge={q.badge} icon={q.icon} pressed={filter === q.filter}
                         onPress={() => { setFilter(filter === q.filter ? '' : q.filter); setPage(1) }} />
            ))}
          </MetricsSection>

          <TableCard label="Deployments table">
            <TableToolbar searchLabel="Filter the deployments" placeholder="Search by deployment, site, card, camera…" text={text} onText={(t) => { setText(t); setPage(1) }}
              choice={{ label: 'Status', value: filter, onChange: (v) => { setFilter(v as Filter); setPage(1) }, options: SQUARES.map((q) => ({ value: q.filter, label: q.label })) }}
              onReset={() => { setText(''); setFilter(''); setRevision(''); setPage(1) }} />
            <ActiveFilters filters={[{ label: `Revision: ${revision || 'All'}`, tone: 'blue' }, { label: `Status: ${filter ? SQUARES.find((q) => q.filter === filter)?.label : 'All'}`, tone: 'green' }]} summary={`${shown.length} of ${deployments.length} deployments match`} />

            <div className="overflow-x-auto">
              <table className={TABLE.table} aria-label="Deployments">
                <thead className={TABLE.head}>
                  <tr><th scope="col" className="w-10 px-2 py-3"><span className="sr-only">Details</span></th>{['Deployment', 'Where', 'When', 'SD and photos', 'Creation', 'Upload'].map((h) => <th key={h} scope="col" className={TABLE.th}>{h}</th>)}<th scope="col" className="px-4 py-3"><span className="sr-only">What to do</span></th></tr>
                </thead>
                <tbody className={TABLE.body}>
                  {onPage.map((d) => (
                    <Fragment key={d.deployment_id}>
                    <tr ref={d.deployment_id === focus ? marked : undefined} aria-current={d.deployment_id === focus ? 'true' : undefined} className={`${TABLE.row(opened === d.deployment_id)} ${d.deployment_id === focus ? 'bg-blue-50 dark:bg-blue-950/40' : ''}`}>
                      <ChevronCell open={opened === d.deployment_id} available={phaseOf(d) === 'created'} label={`the details of the deployment ${d.deployment_id}`} onToggle={() => toggle(d.deployment_id)} />
                      <td className={`${TABLE.cell} font-mono text-xs font-semibold`}>{d.deployment_id}</td>
                      <td className={`${TABLE.cell} font-mono text-xs`}>
                        {onShowLocation
                          ? <LinkButton title={`Show the details of the location ${d.site}`} onClick={() => onShowLocation(d.site)}>{d.site}</LinkButton>
                          : d.site}
                      </td>
                      <td className={TABLE.cell}>
                        {d.start_session && (onShowVisit
                          ? <LinkButton className="block text-xs font-semibold" aria-label={`Show the visit ${d.start_session} to ${d.site}`} onClick={() => onShowVisit({ session: d.start_session!, site: d.site })}>Visit {d.start_session} · {d.site}</LinkButton>
                          : <span className="block text-xs font-semibold">Visit {d.start_session} · {d.site}</span>)}
                        <span className="block font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</span>
                      </td>
                      <td className={`${TABLE.cell} text-xs text-zinc-600 dark:text-zinc-400`}>
                        {d.card && (onShowSd
                          ? <LinkButton className="font-semibold" aria-label={`Show the state of the SD card ${d.card}`} onClick={() => onShowSd(d.card!)}>SD {d.card}</LinkButton>
                          : <>SD {d.card}</>)}
                        {d.card && d.photos_counted != null && ' · '}{d.photos_counted != null && `${d.photos_counted} photos`}
                      </td>
                      <td className={TABLE.cell}>
                        {phaseOf(d) === 'not_created'
                          ? <span title="The camera was stolen: the card is gone, so the deployment will not be created" className="rounded-full px-2.5 py-1 text-xs font-semibold bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300">Not created</span>
                          : phaseOf(d) === 'planned'
                          ? <span className="rounded-full px-2.5 py-1 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Planned</span>
                          : <span className="rounded-full px-2.5 py-1 text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">Created</span>}
                      </td>
                      <td className={TABLE.cell}>
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
                      <td className={`${TABLE.cell} whitespace-nowrap`}>
                        {/* only what can be done with the row: the options that do not apply to it are not there */}
                        <RowOptions label={`Options of the deployment ${d.deployment_id}`}>
                          {(() => {
                            const before = neighbour(d, -1)
                            return before && <IconButton compact label={`Show the previous deployment of ${d.site} (${before.collection})`} title={`The previous revision of this location: ${before.collection}`} onClick={() => setJump(before.deployment_id)} path={ICON_PATHS.before} />
                          })()}
                          {phaseOf(d) === 'created' && (
                            <IconButton compact label={`View the deployment ${d.deployment_id}`} title="View the deployment" expanded={opened === d.deployment_id} onClick={() => toggle(d.deployment_id)} path={ICON_PATHS.view} />
                          )}
                          {(() => {
                            const after = neighbour(d, 1)
                            return after && <IconButton compact label={`Show the next deployment of ${d.site} (${after.collection})`} title={`The next revision of this location: ${after.collection}`} onClick={() => setJump(after.deployment_id)} path={ICON_PATHS.after} />
                          })()}
                          {/* the card was collected and the images are not stored: the deployment can be made now */}
                          {phaseOf(d) === 'planned' && d.status === 'closed' && onCreate && (
                            <IconButton compact label={`Create the deployment ${d.deployment_id}`} title="Create the deployment" onClick={() => onCreate(d)}
                                        path={<><path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z" /><circle cx="12" cy="13" r="3.5" /></>} />
                          )}
                          {phaseOf(d) === 'created' && onUpload && statesOf(d).some((u) => u.destination === 'trapper' && u.state !== 'done') && (
                            <IconButton compact label={`Upload the deployment ${d.deployment_id}`} title={statesOf(d).some((u) => u.state === 'failed') ? 'Upload the images again' : 'Upload the images'} onClick={() => onUpload(d)} path={ICON_PATHS.upload} />
                          )}
                        </RowOptions>
                      </td>
                    </tr>
                    {opened === d.deployment_id && (
                      <DetailsRow colSpan={8}>
                        {details[d.deployment_id] === undefined ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployment…</p>
                          : details[d.deployment_id] === 'error' || details[d.deployment_id] === null ? <p role="alert" className="text-sm text-amber-700 dark:text-amber-400">The details of this deployment could not be read from the collections folder.</p>
                          : (
                            <dl aria-label={`Details of the deployment ${d.deployment_id}`} className="grid grid-cols-1 gap-x-8 gap-y-2 text-xs md:grid-cols-2">
                              {DEPLOYMENT_DETAILS.filter(([k]) => { const value = (details[d.deployment_id] as DeploymentFields)[k]; return value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0) })
                                .map(([k, label]) => <DetailLine key={k} name={label} kind={k === 'comments' ? 'plain' : 'mono'}>{shownValue((details[d.deployment_id] as DeploymentFields)[k])}</DetailLine>)}
                            </dl>
                          )}
                      </DetailsRow>
                    )}
                    </Fragment>
                  ))}
                  {shown.length === 0 && <tr><td colSpan={8} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No deployment matches.</td></tr>}
                </tbody>
              </table>
            </div>

            {shown.length > 0 && (
              <TableFooter from={(current - 1) * PER_PAGE + 1} to={Math.min(current * PER_PAGE, shown.length)} total={shown.length} noun="deployments" page={current} pages={pages} onPage={setPage} />
            )}
          </TableCard>

          {helpOpen && onCloseHelp && (
            <HelpDrawer onClose={onCloseHelp}>
              <HelpCard title="Overall progress" tone="text-blue-600 dark:text-blue-400" icon={HELP_ICONS.progress}><p>The share of the deployments that are created — their images are stored — over the revision picked or over all of them.</p></HelpCard>
              <HelpCard title="Deployment states" tone="text-emerald-600 dark:text-emerald-400" icon={HELP_ICONS.tags}>
                <dl className="space-y-2">
                  {SQUARES.map((q) => <div key={q.filter} className="flex items-baseline gap-3"><dt className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold ${q.badge}`}>{q.label}</dt><dd>{q.note}</dd></div>)}
                </dl>
              </HelpCard>
              <HelpCard title="Creation and uploads" tone="text-violet-600 dark:text-violet-400" icon={HELP_ICONS.upload}><p>A deployment is <em>planned</em> while its card is to be imported and <em>created</em> when its images are stored. <em>Not created</em> is a deployment of a camera that was stolen: the card is gone. Uploading is another thing: each deployment has an upload for every uploader in use, <em>planned</em> from the start, then <em>done</em> or <em>failed</em> — a failed one is tried again.</p></HelpCard>
              <HelpCard title="Filters and search" tone="text-sky-600 dark:text-sky-400" icon={HELP_ICONS.filter}><p>Search by deployment, site, card or camera, and filter by status; pick a revision above.</p></HelpCard>
            </HelpDrawer>
          )}
        </>
      )}
    </div>
  )
}
