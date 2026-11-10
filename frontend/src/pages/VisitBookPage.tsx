import { Fragment, useEffect, useState, type ReactNode } from 'react'
import { api } from '../api'
import { Icon, StateCard } from '../components/Dashboard'
import { ActiveFilters, ChevronCell, DashboardHeader, DetailLine, DetailsRow, DownloadButton, HELP_ICONS, HelpButton, HelpCard, HelpDrawer, MetricsSection, ProgressCard, RevisionSelection, RowOptions, TABLE, TableCard, TableFooter, TableToolbar } from '../components/DashboardParts'
import { Breadcrumb } from '../components/TaskCard'
import IconButton, { ICON_PATHS } from '../components/IconButton'
import LinkButton from '../components/LinkButton'
import EditVisitDialog from '../components/EditVisitDialog'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import type { BookVisit, ClosedVisitTarget } from '../types'
import { btnOutline } from './ImportDeploymentPage'
import { download } from '../csvFile'

interface Props {
  onBack: () => void
  /** Goes to Import deployment for a closed visit: its research project, and the visit whose card was collected — the deployment is of it. */
  onImportImages?: (target: ClosedVisitTarget) => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general' | 'locations', researchProjectId?: string, item?: string) => void
  /** Whether the settings are open: the default research project is read again when they are closed, as it may have been changed. */
  settingsOpen?: boolean
  /** Goes to the status of the deployments, on one of them: the link of the tick of the images stored. */
  onShowDeployment?: (deploymentId: string) => void
  /** The visit shown open, on its revision and its page: the one a link of the deployments dashboard goes to. */
  focus?: VisitFocus
  /** Goes to register the visit of a location that is planned: its research project and the location. */
  onCreateVisit?: (target: { researchProjectId: string; site: string }) => void
}

/** The fields of a visit the details show, in this order, when it has them. */
const DETAILS: [keyof BookVisit, string][] = [
  ['trappers', 'Who went'], ['setup_by', 'Set up by'], ['camera_id', 'Camera'], ['camera_model', 'Camera model'], ['sd', 'SD card left'], ['num_photos', 'Photos counted'], ['camera_status', 'Status of the camera'],
  ['card_batteries_ok', 'Card and batteries'], ['date_time_ok', 'Camera date and time OK'], ['calibration', 'Camera calibrated'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['camera_interval', 'Camera delay (s)'],
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

/** Where a visit is in its life: planned (not made yet), deployed (it left a camera that is still out), collected (the card was collected: a later visit closed it), stolen (the camera was
 * stolen, so no images) and not visited (the visit could not be made). Whether the images are stored is told by the Images column, not by the state. A visit that left no camera has no state. */
type Phase = 'planned' | 'deployed' | 'collected' | 'stolen' | 'not_visited' | 'unknown'
const phaseOf = (v: BookVisit): Phase | null =>
  v.state !== undefined ? v.state : v.not_done ? 'planned' : v.not_visited ? 'not_visited' : v.deployment_status === 'open' ? 'deployed' : v.deployment_status === 'closed' ? (v.deployment_no_images ? 'stolen' : 'collected') : null
const PHASES: Phase[] = ['collected', 'stolen', 'deployed', 'not_visited', 'unknown', 'planned']
const PHASE_LABEL: Record<Phase, string> = { planned: 'Planned', deployed: 'Deployed', collected: 'Collected', stolen: 'Stolen', not_visited: 'Not visited', unknown: 'Unknown' }
const PHASE_BADGE: Record<Phase, string> = {
  planned: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300',
  deployed: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300',
  collected: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300',
  stolen: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
  not_visited: 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200',
  unknown: 'bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300',
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

/** The visit's wall clock as ISO 8601 with its offset from UTC (2024-09-04T13:10+02:00): the offset is what the instant kept (UTC) differs from the wall clock of the location. Without the instant, the wall clock alone. */
function isoWithOffset(v: BookVisit): string {
  const local = `${v.date}T${v.time.slice(0, 5)}`
  if (!v.when) return local
  const minutes = Math.round((Date.parse(`${v.date}T${v.time.length > 5 ? v.time : `${v.time}:00`}Z`) - Date.parse(v.when)) / 60000)
  if (Number.isNaN(minutes)) return local
  const abs = Math.abs(minutes)
  return `${local}${minutes < 0 ? '-' : '+'}${String(Math.floor(abs / 60)).padStart(2, '0')}:${String(abs % 60).padStart(2, '0')}`
}

/** The days a revision went from and to — its first and its last visit made, as the wall clock of their locations says —, or nothing when none was made. The end is only
 * told when the revision is complete (no visit left planned): one still going has its end open ("2024-09-04 → …"). */
function spanOf(visits: BookVisit[]): string | undefined {
  const days = visits.filter((v) => !v.not_done && v.date).map((v) => v.date).sort()
  if (days.length === 0) return undefined
  const first = days[0], last = days[days.length - 1]
  if (visits.some((v) => v.not_done)) return `${first} → …`
  return first === last ? first : `${first} → ${last}`
}

/** How many visits a page of the book has. */
const PER_PAGE = 10

/** The visit book of a research project: the visits kept to it, and the deployments they say — closed, and the ones whose camera is still out — with the logs of their collections. */
export default function VisitBookPage({ onBack, onImportImages, onOpenSettings, settingsOpen, onShowDeployment, focus, onCreateVisit }: Props) {
  // The legend and the help: a panel at the right, opened from the header.
  const [helpOpen, setHelpOpen] = useState(false)
  // The revisions and the status cards fold away, to leave the table alone.
  const [revisionsOpen, setRevisionsOpen] = useState(true)
  const [metricsOpen, setMetricsOpen] = useState(true)
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
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const error = projectError ?? loadError ?? exportError

  /** The visits of the research project as a CSV file that Register visits › CSV reads back. */
  async function exportVisits() {
    if (!project) return
    setExporting(true); setExportError(null)
    try {
      const { csv, filename } = await api.exportVisitsCsv(project.acronym)
      download(filename, csv)
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Could not export the visits.')
    } finally {
      setExporting(false)
    }
  }
  // The visit being edited, or the unknown one being filled in.
  const [editing, setEditing] = useState<BookVisit | null>(null)
  const [reloads, setReloads] = useState(0)
  useEffect(() => {
    setVisits(null); setLoadError(null); setPage(1); setOpened(null); setRevision('')
  }, [project?.acronym])
  useEffect(() => {
    if (!project) return
    let cancelled = false
    api.visitBook(project.acronym)
      .then(({ results }) => { if (!cancelled) setVisits(results) })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the visits.') })
    return () => { cancelled = true }
  }, [project?.acronym, reloads]) // eslint-disable-line react-hooks/exhaustive-deps

  // How many rows each status square has — over the rows of the revision picked (all of them when none is), whatever the text filter says.
  const everyRow = visits ?? []
  const revisions = [...new Set(everyRow.map((v) => v.session))].sort((x, y) => y.localeCompare(x))
  const rows = revision ? everyRow.filter((v) => v.session === revision) : everyRow
  const count = (f: StatusFilter) => rows.filter((v) => matches(v, f)).length
  // a visit that could not be made is settled: it counts as completed — what is pending is what is still planned
  const made = rows.filter((v) => !v.not_done && !v.unknown).length
  const percent = rows.length ? Math.round((made / rows.length) * 100) : 0
  const SQUARES: { filter: Phase; label: string; note: string; tone: string; badge: string; icon: ReactNode }[] = [
    { filter: 'planned', label: 'Planned', note: 'Not visited yet', tone: 'text-zinc-600 dark:text-zinc-300', badge: 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>} className="h-5 w-5" /> },
    { filter: 'deployed', label: 'Deployed', note: 'Camera out, card not collected', tone: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300', icon: <Icon path={<><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5v.01" /></>} className="h-5 w-5" /> },
    { filter: 'collected', label: 'Collected', note: 'Card collected', tone: 'text-emerald-600 dark:text-emerald-400', badge: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></>} className="h-5 w-5" /> },
    { filter: 'stolen', label: 'Stolen', note: 'Camera stolen, no images', tone: 'text-red-600 dark:text-red-400', badge: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M5.6 5.6l12.8 12.8" /></>} className="h-5 w-5" /> },
    { filter: 'not_visited', label: 'Not visited', note: 'The visit could not be made', tone: 'text-slate-600 dark:text-slate-300', badge: 'bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>} className="h-5 w-5" /> },
  ]

  // a visit is brought into view: on its revision, on its page, and open
  function showVisit(target: BookVisit) {
    setRevision(target.session); setStatusFilter(''); setFilter(''); setSort(null)
    setPage(Math.floor((visits ?? []).filter((v) => v.session === target.session).sort(byDefault).findIndex((v) => keyOf(v) === keyOf(target)) / PER_PAGE) + 1)
    setOpened(keyOf(target))
  }
  // the visit a link of the deployments dashboard goes to
  useEffect(() => {
    if (!focus || !visits) return
    const target = visits.find((v) => !v.not_done && v.session === focus.session && v.location_id.toLowerCase() === focus.site.toLowerCase())
    if (target) showVisit(target)
  }, [focus, visits]) // eslint-disable-line react-hooks/exhaustive-deps
  // the visit that was made to the same location in the closest revision after the one of a row
  const nextOf = (v: BookVisit) => everyRow
    .filter((w) => !w.not_done && w.location_id.toLowerCase() === v.location_id.toLowerCase() && w.session > v.session)
    .sort((a, b) => a.session.localeCompare(b.session) || `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`))[0]
  // the visit that was made to the same location in the closest revision before the one of a row
  const previousOf = (v: BookVisit) => everyRow
    .filter((w) => !w.not_done && w.location_id.toLowerCase() === v.location_id.toLowerCase() && w.session < v.session)
    .sort((a, b) => b.session.localeCompare(a.session) || `${b.date}T${b.time}`.localeCompare(`${a.date}T${a.time}`))[0]

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
      <DashboardHeader icon={<><path d="M4 5.5A2.5 2.5 0 016.5 3H19v16H6.5A2.5 2.5 0 004 21.5z" /><path d="M4 18.5A2.5 2.5 0 016.5 16H19" /></>} title="Visit dashboard" description="The visits kept to a research project."
        actions={<>
          {project && visits !== null && visits.length > 0 && (
            <DownloadButton busy={exporting} onClick={() => void exportVisits()} title="Download the visits of this research project as a CSV file, to import them again in Register visits › CSV file">{exporting ? 'Exporting…' : 'Export visits (CSV)'}</DownloadButton>
          )}
          <HelpButton expanded={helpOpen} onClick={() => setHelpOpen(true)} />
        </>}
        aside={<DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The book" onOpenSettings={onOpenSettings} />} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {project && (
        <>
          {visits !== null && revisions.length > 0 && (
            <RevisionSelection open={revisionsOpen} onToggle={() => setRevisionsOpen(!revisionsOpen)} hint="Select one to filter planned & completed visits"
              all={{ label: 'All revisions', note: `${everyRow.filter((v) => !v.not_done).length} of ${everyRow.length} done`, percent: everyRow.length ? Math.round((everyRow.filter((v) => !v.not_done).length / everyRow.length) * 100) : 0 }} value={revision}
              revisions={revisions.map((r) => { const of = everyRow.filter((v) => v.session === r); return { id: r, label: r, note: `${of.filter((v) => !v.not_done).length} of ${of.length} done`, dates: spanOf(of), complete: of.length > 0 && of.every((v) => !v.not_done) } })}
              onPick={(id) => { setRevision(id); setStatusFilter(''); setPage(1); setOpened(null) }} />
          )}
          {visits !== null && (
            <MetricsSection label="Visits by status" open={metricsOpen} onToggle={() => setMetricsOpen(!metricsOpen)} hint="Click a card to filter the table by status">
              <ProgressCard percent={percent} done={made} total={rows.length} barLabel="Visits done" caption={`${rows.length - made} pending ${rows.length - made === 1 ? 'visit' : 'visits'}`}
                segments={[
                  { width: rows.length ? ((count('collected') + count('stolen')) / rows.length) * 100 : 0, className: 'bg-emerald-500' },
                  { width: rows.length ? (count('deployed') / rows.length) * 100 : 0, className: 'bg-amber-500' },
                  { width: rows.length ? (count('not_visited') / rows.length) * 100 : 0, className: 'bg-slate-400' },
                ]} />
              {SQUARES.map((q) => (
                <StateCard key={q.label} label={q.label} note={q.note} count={count(q.filter)} tone={q.tone} badge={q.badge} icon={q.icon} pressed={statusFilter === q.filter}
                           onPress={() => { setStatusFilter(statusFilter === q.filter ? '' : q.filter); setPage(1); setOpened(null) }} />
              ))}
            </MetricsSection>
          )}

          <TableCard label="Visits table">
          <TableToolbar searchLabel="Filter the visits" placeholder="Search by site, revision, camera, card, who, deployment…" text={filter} onText={(t) => { setFilter(t); setPage(1); setOpened(null) }}
            choice={{ label: 'Status', value: statusFilter, onChange: (v) => { setStatusFilter(v as StatusFilter); setPage(1); setOpened(null) }, options: SQUARES.map((q) => ({ value: q.filter, label: q.label })) }}
            onReset={() => { setFilter(''); setStatusFilter(''); setRevision(''); setSort(null); setPage(1); setOpened(null) }} />
          {visits !== null && (
            <ActiveFilters filters={[{ label: `Revision: ${revision || 'All'}`, tone: 'blue' }, { label: `Status: ${statusFilter ? PHASE_LABEL[statusFilter] : 'All'}`, tone: 'green' }]} summary={`${shown.length} of ${everyRow.length} visits match`} />
          )}

          {(
            visits === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the visits…</p> : (
              <>
              <div className="overflow-x-auto">
                <table className={TABLE.table} aria-label="Visits">
                  <thead className={TABLE.head}>
                    <tr>
                      <th scope="col" className="w-10 px-2 py-3"><span className="sr-only">Details</span></th>
                      {COLUMNS.map(([key, label]) => (
                        <th key={key} scope="col" aria-sort={sort?.key === key ? (sort.descending ? 'descending' : 'ascending') : 'none'} className={TABLE.th}>
                          <button type="button" className="inline-flex items-center gap-1 font-semibold uppercase tracking-wider hover:text-zinc-900 dark:hover:text-zinc-100" onClick={() => { setSort(sort?.key === key ? { key, descending: !sort.descending } : { key, descending: false }); setPage(1); setOpened(null) }}>
                            {label}
                            <svg aria-hidden="true" viewBox="0 0 24 24" className={`h-3.5 w-3.5 fill-none stroke-current ${sort?.key === key ? 'text-blue-500' : 'text-zinc-400 dark:text-zinc-600'}`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              {sort?.key === key ? (sort.descending ? <path d="M12 5v14M6 13l6 6 6-6" /> : <path d="M12 19V5M6 11l6-6 6 6" />) : <path d="M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4" />}
                            </svg>
                          </button>
                        </th>
                      ))}
                      <th scope="col" className="px-4 py-3"><span className="sr-only">What to do</span></th>
                    </tr>
                  </thead>
                  <tbody className={TABLE.body}>
                    {onPage.map((v) => {
                      const key = keyOf(v)
                      return (
                        <Fragment key={key}>
                          <tr ref={focus && opened === key ? (el) => el?.scrollIntoView?.({ block: 'center' }) : undefined} className={TABLE.row(opened === key)}>
                            <ChevronCell open={opened === key} available={!v.not_done && !v.unknown} label={`the details of the visit ${v.session} to ${v.location_id}`} onToggle={() => setOpened(opened === key ? null : key)} />
                            <td className="px-4 py-3 font-mono font-semibold text-zinc-900 dark:text-zinc-200">{v.session}</td>
                            <td className="px-4 py-3 font-mono">
                              {onOpenSettings && project
                                ? <LinkButton title={`Show the details of the location ${v.location_id}`} className="font-mono" onClick={() => onOpenSettings('locations', project.acronym, v.location_id)}>{v.location_id}</LinkButton>
                                : v.location_id}
                            </td>
                            <td className="px-4 py-3 font-mono text-[11px] whitespace-nowrap text-zinc-600 dark:text-zinc-300">{v.not_done || v.unknown || phaseOf(v) === 'not_visited' ? <span className="font-sans text-zinc-400">—</span> : isoWithOffset(v)}</td>
                            <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300">{v.actions.length === 0 && !v.not_done ? '—' : v.actions.join(' + ')}</td>
                            <td className="px-4 py-3">
                              {phaseOf(v)
                                ? <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${PHASE_BADGE[phaseOf(v)!]}`}><span aria-hidden="true" className="inline-flex [&>svg]:h-3 [&>svg]:w-3">{SQUARES.find((q) => q.filter === phaseOf(v))?.icon}</span>{PHASE_LABEL[phaseOf(v)!]}</span>
                                : <span className="text-zinc-400">—</span>}
                            </td>
                            <td className="px-4 py-3">
                              {v.not_done || v.unknown ? null : v.deployment_id ? (
                                <button type="button" title="Show image details" className="inline-flex rounded-full text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500" aria-label={`Details of the deployment ${v.deployment_id}`} onClick={() => onShowDeployment?.(v.deployment_id!)}>
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M8 12.5l3 3 5-6" /></svg>
                                </button>
                              ) : <span role="img" aria-label="Images not stored" title={v.deployment_no_images ? 'No images: the camera was stolen' : 'Not stored: the card has not been collected yet'} className="inline-flex text-zinc-400 dark:text-zinc-500">
                                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                                </span>}
                            </td>
                            <td className="px-4 py-3 whitespace-nowrap">
                              {/* only what can be done with the row: the options that do not apply to it are not there */}
                              <RowOptions label={`Options of the visit ${v.session} to ${v.location_id}`}>
                                {(() => {
                                  const before = previousOf(v)
                                  return before && (
                                    <IconButton compact label={`Show the previous visit to ${v.location_id} (${before.session})`} title={`The previous revision of this location: ${before.session}`}
                                      onClick={() => showVisit(before)} path={ICON_PATHS.before} />
                                  )
                                })()}
                                {!v.not_done && !v.unknown && (
                                  <IconButton compact label={`Edit the visit ${v.session} to ${v.location_id}`} title={v.locked ? 'It starts or closes an imported deployment: it cannot be edited' : 'Edit the visit'} disabled={v.locked}
                                    onClick={() => setEditing(v)} path={<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>} />
                                )}
                                {v.unknown && (
                                  <IconButton compact label={`Fill in the visit ${v.session} to ${v.location_id}`} title="Nothing is known of this visit: fill it in"
                                    onClick={() => setEditing(v)} path={<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" /></>} />
                                )}
                                {!v.not_done && !v.unknown && (
                                  <IconButton compact label={`View the visit ${v.session} to ${v.location_id}`} title="View the visit" expanded={opened === key}
                                    onClick={() => setOpened(opened === key ? null : key)} path={ICON_PATHS.view} />
                                )}
                                {(() => {
                                  const after = nextOf(v)
                                  return after && (
                                    <IconButton compact label={`Show the next visit to ${v.location_id} (${after.session})`} title={`The next revision of this location: ${after.session}`}
                                      onClick={() => showVisit(after)} path={ICON_PATHS.after} />
                                  )
                                })()}
                                {v.not_done && onCreateVisit && (
                                  <IconButton compact label={`Create the visit ${v.session} to ${v.location_id}`} title="Create the visit"
                                    onClick={() => onCreateVisit({ researchProjectId: project!.acronym, site: v.location_id })} path={<><path d="M12 21s-7-6.2-7-11a7 7 0 1114 0c0 4.8-7 11-7 11z" /><circle cx="12" cy="10" r="2.5" /></>} />
                                )}
                                {!v.not_done && !v.deployment_id && v.deployment_status === 'closed' && !v.deployment_no_images && onImportImages && (
                                  <IconButton compact label={`Create the deployment of the visit ${v.session} to ${v.location_id}`} title="Create the deployment"
                                    onClick={() => onImportImages({ researchProjectId: project!.acronym, visit: v })} path={<><path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 011 1v9a1 1 0 01-1 1H4a1 1 0 01-1-1V9a1 1 0 011-1z" /><circle cx="12" cy="13" r="3.5" /></>} />
                                )}
                              </RowOptions>
                            </td>
                          </tr>
                          {opened === key && (
                            <DetailsRow colSpan={8}>
                              <dl aria-label={`Details of the visit ${v.session} to ${v.location_id}`} className="grid grid-cols-1 gap-x-8 gap-y-2 text-xs md:grid-cols-2">
                                <DetailLine name="Actions">{v.actions.length === 0 ? 'None: the visit could not be made' : v.actions.join(' + ')}</DetailLine>
                                {DETAILS.flatMap(([k, label]) => {
                                  const photos = v.num_photos
                                  const taken = photos !== null && photos !== undefined ? collectedCard(everyRow, v) : null
                                  const rows: JSX.Element[] = []
                                  const line = (key: string, name: string, value: string) => {
                                    if (key === 'comments') return <div key={key} className="pt-1 md:col-span-2"><dt className="mb-1 font-medium text-zinc-500 dark:text-zinc-400">{name}</dt><dd className="rounded-lg border border-zinc-200 dark:border-zinc-800/80 bg-zinc-50 dark:bg-zinc-950 p-2 italic text-zinc-700 dark:text-zinc-300">{value}</dd></div>
                                    const okay = (key === 'card_batteries_ok' || key === 'status') && value.toLowerCase() === 'ok'
                                    const kind = okay ? 'good' : ['trappers', 'setup_by', 'status', 'card_batteries_ok', 'date_time_ok', 'camera_model'].includes(key) ? 'plain' : 'mono'
                                    return <DetailLine key={key} name={name} kind={kind}>{key === 'trappers' && <Icon path={<><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0116 0" /></>} className="mr-1.5 inline h-3 w-3 text-blue-500" />}{value}</DetailLine>
                                  }
                                  // the card is the one the visit before it left: when no visit before it is known (the revisions before are unknown), it is told, not left out
                                  if (k === 'sd' && photos !== null && photos !== undefined) rows.push(line('taken', 'SD card collected', taken ? `${taken} (${photos})` : 'unknown: no visit before it is known'))
                                  if (k === 'num_photos' && taken) return rows
                                  const value = v[k]
                                  if (value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0)) rows.push(line(k, label, shownValue(value)))
                                  return rows
                                })}
                              </dl>
                            </DetailsRow>
                          )}
                        </Fragment>
                      )
                    })}
                    {shown.length === 0 && <tr><td colSpan={8} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{visits.length === 0 ? 'No visit has been registered to this research project yet.' : 'No visit matches.'}</td></tr>}
                  </tbody>
                </table>
              </div>
              {shown.length > 0 && (
                <TableFooter from={(current - 1) * PER_PAGE + 1} to={Math.min(current * PER_PAGE, shown.length)} total={shown.length} noun="visits" page={current} pages={pages} onPage={(n) => { setPage(n); setOpened(null) }} />
              )}
              </>
            )
          )}
          </TableCard>
        </>
      )}

      {helpOpen && (
        <HelpDrawer onClose={() => setHelpOpen(false)}>
          <HelpCard title="Overall progress" tone="text-blue-600 dark:text-blue-400" icon={HELP_ICONS.progress}><p>The share of the visits done, over the revision picked or over all of them, with the ones still pending.</p></HelpCard>
          <HelpCard title="Visit states" tone="text-emerald-600 dark:text-emerald-400" icon={HELP_ICONS.tags}>
            <dl className="space-y-2">
              {[...SQUARES.map((q) => ({ key: q.filter, label: q.label, note: q.note, badge: q.badge })), { key: 'unknown', label: 'Unknown', note: 'Nothing is known of it: a revision before the first visit kept to a site', badge: PHASE_BADGE.unknown }].map((q) => (
                <div key={q.key} className="flex items-baseline gap-3">
                  <dt className={`shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold ${q.badge}`}>{q.label}</dt>
                  <dd>{q.note}</dd>
                </div>
              ))}
            </dl>
          </HelpCard>
          <HelpCard title="Data states" tone="text-violet-600 dark:text-violet-400" icon={HELP_ICONS.images}><p><span className="font-medium text-zinc-700 dark:text-zinc-200">Images</span>: once the deployment of the visit is made its images are stored, whatever the state of the visit, and its tick opens the details of that deployment in the deployments dashboard. A visit whose camera was stolen is <em>Stolen</em>: there are no images, and nothing to create.</p></HelpCard>
          <HelpCard title="Filters and search" tone="text-sky-600 dark:text-sky-400" icon={HELP_ICONS.filter}><p>Search by site, revision, camera or card, and filter by status; pick a revision above.</p></HelpCard>
        </HelpDrawer>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
      {editing && project && (
        <EditVisitDialog projectId={project.acronym} visit={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); setOpened(null); setReloads((n) => n + 1) }} />
      )}
    </div>
  )
}
