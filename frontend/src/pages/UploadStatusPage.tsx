import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import { Icon, LegendCard, Ring, StateCard } from '../components/Dashboard'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import RevisionSquares from '../components/RevisionSquares'
import IconButton, { ICON_PATHS } from '../components/IconButton'
import LinkButton from '../components/LinkButton'
import UploadList from '../components/UploadList'
import { MENU_ICONS, PageHeader } from '../components/TaskCard'
import { formatDay } from '../dateFormat'
import type { DeploymentUploadState, FieldDeployment, UploadStateName, UploadTarget } from '../types'
import { destinationLabel } from '../uploadDestinations'
import { btnOutline, inputClass } from './ImportDeploymentPage'
import type { VisitFocus } from './VisitBookPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general' | 'locations', researchProjectId?: string, item?: string) => void
  settingsOpen?: boolean
  /** Goes to the visit dashboard, on a visit: the one that started a deployment. */
  onShowVisit?: (visit: VisitFocus) => void
  /** Goes to the Deployments dashboard, on a deployment: its details. */
  onShowDeployment?: (deploymentId: string) => void
  /** Goes to upload a deployment: the research project and the revision it is of. */
  onUpload?: (target: UploadTarget) => void
  /** What the search starts with — a deployment, when the page is reached from its link in the deployments dashboard. */
  search?: string
}

/** How many uploads a page has. */
const PER_PAGE = 10

const plural = (n: number) => `${n} ${n === 1 ? 'upload' : 'uploads'}`

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`

/** One upload: a deployment going to an uploader, and where that is. */
interface UploadRow { deployment: FieldDeployment; upload: DeploymentUploadState }

const STATE_LABEL: Record<UploadStateName, string> = { planned: 'Planned', done: 'Done', failed: 'Failed' }
const STATE_BADGE: Record<UploadStateName, string> = {
  planned: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300',
  done: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
  failed: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
}

/** The dashboard of the uploads of the default research project: each deployment is to be uploaded to every uploader in use — that is an upload, planned from the start —, and
 * it ends done or failed; a failed one is tried again. A deployment that will not be made (the camera was stolen) has none. */
export default function UploadStatusPage({ onBack, onOpenSettings, settingsOpen, onShowVisit, onShowDeployment, onUpload, search }: Props) {
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [deployments, setDeployments] = useState<FieldDeployment[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState('')
  // the uploads of one uploader, or '' for all of them
  const [uploader, setUploader] = useState('')
  // the uploads in one state, or '' for all of them
  const [state, setState] = useState<'' | UploadStateName>('')
  const [text, setText] = useState(search ?? '')
  const [page, setPage] = useState(1)
  // the upload whose details are open
  const [opened, setOpened] = useState<string | null>(null)
  const error = projectError ?? loadError

  useEffect(() => {
    setDeployments(null); setLoadError(null); setRevision('')
    if (!project) return
    let cancelled = false
    api.fieldDeployments(project.acronym)
      .then(({ results }) => { if (!cancelled) setDeployments(results) })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the uploads.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  // the uploads there are: every deployment that will be made, times every uploader in use
  const every: UploadRow[] = (deployments ?? []).filter((d) => !d.no_images).flatMap((d) => (d.upload_states ?? []).map((u) => ({ deployment: d, upload: u })))
  const revisions = [...new Set(every.map((r) => r.deployment.collection))].sort((a, b) => b.localeCompare(a))
  const uploaders = [...new Set(every.map((r) => r.upload.destination))]
  // the cards and the table follow the revision and the uploader picked
  const own = every.filter((r) => (!revision || r.deployment.collection === revision) && (!uploader || r.upload.destination === uploader))
  const count = (s: UploadStateName) => own.filter((r) => r.upload.state === s).length
  const percent = own.length ? Math.round((count('done') / own.length) * 100) : 0
  const needle = text.trim().toLowerCase()
  const shown = own
    .filter((r) => !state || r.upload.state === state)
    .filter((r) => !needle || `${r.deployment.deployment_id} ${r.deployment.site} ${r.deployment.collection} ${destinationLabel(r.upload.destination)} ${STATE_LABEL[r.upload.state]}`.toLowerCase().includes(needle))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const key = (r: UploadRow) => `${r.deployment.deployment_id}/${r.upload.destination}`

  const SQUARES: { state: UploadStateName; note: string; tone: string; badge: string; icon: React.ReactNode }[] = [
    { state: 'planned', note: 'Still to be uploaded', tone: 'text-amber-600 dark:text-amber-400', badge: 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300', icon: <Icon path={<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>} className="h-5 w-5" /> },
    { state: 'done', note: 'Uploaded', tone: 'text-blue-600 dark:text-blue-400', badge: 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300', icon: <Icon path={<><path d="M20 16.2A4.5 4.5 0 0017.5 8h-1.8A7 7 0 104 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} className="h-5 w-5" /> },
    { state: 'failed', note: 'Tried and failed: try again', tone: 'text-red-600 dark:text-red-400', badge: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300', icon: <Icon path={<><path d="M12 3l10 18H2z" /><path d="M12 10v4M12 17.5v.01" /></>} className="h-5 w-5" /> },
  ]

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <PageHeader icon={MENU_ICONS.upload} title="Uploads dashboard" description="The uploads of the deployments to each uploader in use, and their current status."
        parent="Manage uploads" onParent={onBack}
        aside={project !== undefined || defaultAcronym !== null ? <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The dashboard" onOpenSettings={onOpenSettings} /> : undefined} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && deployments === null && <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p>}

      {deployments !== null && (
        <>
          {revisions.length > 0 && (
            <section aria-label="Revision" className="mb-6">
              <h5 className="text-lg font-semibold mb-1">Revision</h5>
              <RevisionSquares description="A revision is one visit to every site. Pick one to see its uploads and where each is." all={{ label: 'All revisions', note: plural(every.length) }} value={revision}
                revisions={revisions.map((r) => ({ id: r, label: r, note: plural(every.filter((x) => x.deployment.collection === r).length) }))}
                onPick={(id) => { setRevision(id); setPage(1) }} />
            </section>
          )}

          <section aria-label="Uploads by status" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a card to show only those uploads.</p>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-[1.6fr_repeat(3,1fr)]">
              <div className="col-span-2 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4 lg:col-span-1">
                <Ring percent={percent} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{revision ? `Uploads of ${revision}` : 'All the uploads'}{uploader ? ` to ${destinationLabel(uploader)}` : ''}</p>
                  <p className="text-2xl font-semibold leading-tight">{count('done')} <span className="text-zinc-400">/ {own.length}</span></p>
                  <div role="progressbar" aria-label="Uploads done" aria-valuemin={0} aria-valuemax={own.length} aria-valuenow={count('done')} className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div className="h-1.5 bg-blue-500" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{count('done')} done · {count('planned')} planned · {count('failed')} failed</p>
                </div>
              </div>
              {SQUARES.map((q) => (
                <StateCard key={q.state} label={STATE_LABEL[q.state]} note={q.note} count={count(q.state)} tone={q.tone} badge={q.badge} icon={q.icon}
                           pressed={state === q.state} onPress={() => { setState(state === q.state ? '' : q.state); setPage(1) }} />
              ))}
            </div>
          </section>

          <div role="search" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the uploads" className={`${inputClass} !pl-9`} placeholder="Search by deployment, site, revision, uploader, status…" value={text} onChange={(e) => { setText(e.target.value); setPage(1) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Uploader
              <select aria-label="Uploader" className={`${inputClass} !w-auto`} value={uploader} onChange={(e) => { setUploader(e.target.value); setPage(1) }}>
                <option value="">All</option>
                {uploaders.map((u) => <option key={u} value={u}>{destinationLabel(u)}</option>)}
              </select>
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Uploads">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Where', 'When', 'Uploader', 'Status'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}<th scope="col" className="px-3 py-2.5"><span className="sr-only">What to do</span></th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((r) => {
                  const d = r.deployment
                  return (
                    <Fragment key={key(r)}>
                      <tr>
                        <td className="px-3 py-3 font-mono text-xs font-semibold">
                          {onShowDeployment
                            ? <LinkButton className="font-mono text-xs font-semibold" aria-label={`Show the details of the deployment ${d.deployment_id}`} onClick={() => onShowDeployment(d.deployment_id)}>{d.deployment_id}</LinkButton>
                            : d.deployment_id}
                        </td>
                        <td className="px-3 py-3 font-mono text-xs">
                          {onOpenSettings && project
                            ? <LinkButton title={`Show the details of the location ${d.site}`} onClick={() => onOpenSettings('locations', project.acronym, d.site)}>{d.site}</LinkButton>
                            : d.site}
                        </td>
                        <td className="px-3 py-3">
                          {d.start_session && (onShowVisit
                            ? <LinkButton className="block text-xs font-semibold" aria-label={`Show the visit ${d.start_session} to ${d.site}`} onClick={() => onShowVisit({ session: d.start_session!, site: d.site })}>Visit {d.start_session} · {d.site}</LinkButton>
                            : <span className="block text-xs font-semibold">Visit {d.start_session} · {d.site}</span>)}
                          <span className="block font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</span>
                        </td>
                        <td className="px-3 py-3">{destinationLabel(r.upload.destination)}</td>
                        <td className="px-3 py-3">
                          <span title={r.upload.note ?? undefined} className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATE_BADGE[r.upload.state]}`}>{STATE_LABEL[r.upload.state]}</span>
                          {r.upload.state === 'done' && <span className="ml-2 text-xs text-zinc-500 dark:text-zinc-400">{r.upload.uploaded_at ? formatDay(r.upload.uploaded_at, true) : 'synced'}</span>}
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          {/* only what can be done with the row: the options that do not apply to it are not there */}
                          <div className="flex items-center justify-end gap-1.5" role="group" aria-label={`Options of the upload of ${d.deployment_id} to ${destinationLabel(r.upload.destination)}`}>
                            {r.upload.state === 'done' && (
                              <IconButton label={`View the upload of ${d.deployment_id} to ${destinationLabel(r.upload.destination)}`} title="View the upload" expanded={opened === key(r)}
                                          onClick={() => setOpened(opened === key(r) ? null : key(r))} path={ICON_PATHS.view} />
                            )}
                            {r.upload.state !== 'done' && onUpload && project && (
                              <IconButton label={`${r.upload.state === 'failed' ? 'Try again the upload of' : 'Upload'} the deployment ${d.deployment_id}${uploaders.length > 1 ? ` to ${destinationLabel(r.upload.destination)}` : ''}`}
                                          title={d.images_stored ? (r.upload.state === 'failed' ? 'Upload the images again' : 'Upload the images') : 'The deployment is not created yet: its images are not stored'}
                                          disabled={!d.images_stored} onClick={() => onUpload({ researchProjectId: project.acronym, collection: d.collection })} path={ICON_PATHS.upload} />
                            )}
                          </div>
                        </td>
                      </tr>
                      {opened === key(r) && (
                        <tr>
                          <td colSpan={6} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4"><UploadList deployment={d.deployment_id} uploads={(d.uploads ?? []).filter((u) => u.destination === r.upload.destination)} /></td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
                {shown.length === 0 && <tr><td colSpan={6} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{every.length === 0 ? 'There is no upload yet: no deployment is planned, or no uploader is in use.' : 'No upload matches.'}</td></tr>}
              </tbody>
            </table>
          </div>

          {shown.length > 0 && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
              <span role="status" className="text-zinc-500 dark:text-zinc-400">Showing {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, shown.length)} of {shown.length} uploads</span>
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

          <section aria-label="Legend" className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <LegendCard title="Uploads" tone="text-blue-600 dark:text-blue-400"><p>An upload is a deployment going to an uploader. Every deployment that will be made has one for each uploader in use, <em>planned</em> from the start — it waits for the deployment to be created. Then it is <em>done</em> or <em>failed</em>, and a failed one is tried again. A deployment of a stolen camera has none: the card is gone.</p></LegendCard>
            <LegendCard title="Progress" tone="text-violet-600 dark:text-violet-400"><p>The ring counts the uploads done over all there are: the deployments of the revision times the uploaders in use (or the one picked). Pick a card to see only the uploads in that status.</p></LegendCard>
          </section>
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
