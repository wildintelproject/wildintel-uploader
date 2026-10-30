import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import { Icon, LegendCard, Ring, StateCard } from '../components/Dashboard'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import RevisionSquares from '../components/RevisionSquares'
import UploadList from '../components/UploadList'
import { MENU_ICONS, PageHeader } from '../components/TaskCard'
import { formatDay } from '../dateFormat'
import type { UploadTarget, UploadedDeployment } from '../types'
import { UPLOAD_DESTINATIONS, destinationLabel } from '../uploadDestinations'
import { btnOutline, inputClass } from './ImportDeploymentPage'
import type { VisitFocus } from './VisitBookPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
  /** Goes to the visit dashboard, on a visit: the one that started a deployment. */
  onShowVisit?: (visit: VisitFocus) => void
  /** Goes to the Deployments dashboard, on a deployment: its details. */
  onShowDeployment?: (deploymentId: string) => void
  /** Goes to upload a deployment: the research project and the revision it is of. */
  onUpload?: (target: UploadTarget) => void
}

/** How many deployments a page has. */
const PER_PAGE = 10


const plural = (n: number) => `${n} ${n === 1 ? 'deployment' : 'deployments'}`

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`

/** The dashboard of the uploads of the default research project: its created deployments, by revision, each with a label for every platform it was uploaded to and the day. */
export default function UploadStatusPage({ onBack, onOpenSettings, settingsOpen, onShowVisit, onShowDeployment, onUpload }: Props) {
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [deployments, setDeployments] = useState<UploadedDeployment[] | null>(null)
  // every revision the deployments have — also the ones with nothing created yet
  const [allRevisions, setAllRevisions] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  // which uploaders are used, as the settings say: one that is not, has no card
  const [used, setUsed] = useState<Record<string, boolean>>({ trapper: true, agouti: false })
  useEffect(() => {
    api.getSettings().then((s) => setUsed({ trapper: s.TRAPPER?.enabled ?? true, agouti: s.AGOUTI?.enabled ?? false })).catch(() => {})
  }, [settingsOpen])
  const [revision, setRevision] = useState('')
  // where they were uploaded: '' for all the uploaders, or the id of one
  const [uploader, setUploader] = useState('')
  // what the table shows: all of them, the ones uploaded, or the ones not
  const [shownFilter, setShownFilter] = useState<'' | 'uploaded' | 'not'>('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  // the deployment whose uploads are open
  const [opened, setOpened] = useState<string | null>(null)
  const error = projectError ?? loadError

  useEffect(() => {
    setDeployments(null); setLoadError(null); setRevision('')
    if (!project) return
    let cancelled = false
    api.uploads(project.acronym)
      .then(({ deployments: found, revisions }) => { if (!cancelled) { setDeployments(found); setAllRevisions(revisions ?? []) } })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the uploads.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  const every = deployments ?? []
  const revisions = [...new Set([...allRevisions, ...every.map((d) => d.collection)])].sort((a, b) => b.localeCompare(a))
  // the cards and the table follow the revision picked
  const own = revision ? every.filter((d) => d.collection === revision) : every
  // a card for each platform there is — also the ones nothing went to — and for any other an upload names
  const destinations = [...UPLOAD_DESTINATIONS.filter((d) => used[d.id]).map((d) => d.id as string), ...new Set(every.flatMap((d) => d.uploads.map((u) => u.destination)).filter((x) => !UPLOAD_DESTINATIONS.some((k) => k.id === x)))]
  const sentTo = (d: UploadedDeployment, to: string) => d.uploads.some((u) => u.destination === to)
  // the uploaders the progress is of: the one picked, or all of them
  const chosen = uploader ? [uploader] : destinations
  const sentToChosen = (d: UploadedDeployment) => chosen.some((c) => sentTo(d, c))
  // the most there can be is one upload of every deployment to every uploader chosen
  const max = own.length * chosen.length
  const done = own.reduce((n, d) => n + chosen.filter((c) => sentTo(d, c)).length, 0)
  const percent = max ? Math.round((done / max) * 100) : 0
  const needle = text.trim().toLowerCase()
  const shown = own
    .filter((d) => !shownFilter || (shownFilter === 'uploaded') === sentToChosen(d))
    .filter((d) => !needle || `${d.deployment_id} ${d.site} ${d.collection} ${d.uploads.map((u) => destinationLabel(u.destination)).join(' ')}`.toLowerCase().includes(needle))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <PageHeader icon={MENU_ICONS.upload} title="Uploads dashboard" description="The deployments that are created and whether they have been uploaded: to which platform, and when."
        parent="Manage uploads" onParent={onBack}
        aside={project !== undefined || defaultAcronym !== null ? <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The dashboard" onOpenSettings={onOpenSettings} /> : undefined} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && deployments === null && <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p>}

      {deployments !== null && (
        <>
          {revisions.length > 0 && (
            <section aria-label="Revision" className="mb-6">
              <h5 className="text-lg font-semibold mb-1">Revision</h5>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">A revision is one visit to every site. Pick one to see its created deployments and whether they were uploaded.</p>
              <RevisionSquares all={{ label: 'All revisions', note: plural(every.length) }} value={revision}
                revisions={revisions.map((r) => ({ id: r, label: r, note: plural(every.filter((d) => d.collection === r).length) }))}
                onPick={(id) => { setRevision(id); setPage(1) }} />
            </section>
          )}

          <section aria-label="Upload progress" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Where were they uploaded? Pick All, or one uploader.</p>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-[1.6fr_repeat(var(--cards),1fr)]" style={{ '--cards': destinations.length + 1 } as React.CSSProperties}>
              <div className="col-span-2 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4 lg:col-span-1">
                <Ring percent={percent} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{revision ? `Uploads of ${revision}` : 'All the uploads'}{uploader ? ` to ${destinationLabel(uploader)}` : ''}</p>
                  <p className="text-2xl font-semibold leading-tight">{done} <span className="text-zinc-400">/ {max}</span></p>
                  <div role="progressbar" aria-label="Uploads done" aria-valuemin={0} aria-valuemax={max} aria-valuenow={done} className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
                    <div className="h-1.5 bg-blue-500" style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{own.length} {own.length === 1 ? 'deployment' : 'deployments'} × {chosen.length} {chosen.length === 1 ? 'uploader' : 'uploaders'}: the most there can be</p>
                </div>
              </div>
              <StateCard label="All" note={`${destinations.length} ${destinations.length === 1 ? 'uploader' : 'uploaders'}`} count={own.reduce((n, d) => n + destinations.filter((c) => sentTo(d, c)).length, 0)}
                         tone="text-zinc-700 dark:text-zinc-200" badge="bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300"
                         icon={<Icon path={<path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5" />} className="h-5 w-5" />}
                         pressed={uploader === ''} onPress={() => { setUploader(''); setPage(1) }} />
              {destinations.map((d) => (
                <StateCard key={d} label={destinationLabel(d)} note={`of ${own.length} uploaded`} count={own.filter((x) => sentTo(x, d)).length} tone="text-blue-600 dark:text-blue-400"
                           badge="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" icon={<Icon path={<><path d="M20 16.2A4.5 4.5 0 0017.5 8h-1.8A7 7 0 104 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} className="h-5 w-5" />}
                           pressed={uploader === d} onPress={() => { setUploader(uploader === d ? '' : d); setPage(1) }} />
              ))}
            </div>
          </section>

          <div role="search" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the deployments" className={`${inputClass} !pl-9`} placeholder="Search by deployment, site, revision, platform…" value={text} onChange={(e) => { setText(e.target.value); setPage(1) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Show
              <select aria-label="Show" className={`${inputClass} !w-auto`} value={shownFilter} onChange={(e) => { setShownFilter(e.target.value as '' | 'uploaded' | 'not'); setPage(1) }}>
                <option value="">All</option>
                <option value="uploaded">Uploaded</option>
                <option value="not">Not uploaded</option>
              </select>
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Deployments">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Where', 'When', 'Uploaded'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}<th scope="col" className="px-3 py-2.5"><span className="sr-only">What to do</span></th></tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((d) => (
                  <Fragment key={d.deployment_id}>
                    <tr>
                      <td className="px-3 py-3 font-mono text-xs font-semibold">
                        {onShowDeployment
                          ? <button type="button" className="font-mono text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline" aria-label={`Show the details of the deployment ${d.deployment_id}`} onClick={() => onShowDeployment(d.deployment_id)}>{d.deployment_id}</button>
                          : d.deployment_id}
                      </td>
                      <td className="px-3 py-3 font-mono text-xs">{d.site}</td>
                      <td className="px-3 py-3">
                        {d.start_session && (onShowVisit
                          ? <button type="button" className="block text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline" aria-label={`Show the visit ${d.start_session} to ${d.site}`} onClick={() => onShowVisit({ session: d.start_session!, site: d.site })}>Visit {d.start_session} · {d.site}</button>
                          : <span className="block text-xs font-semibold">Visit {d.start_session} · {d.site}</span>)}
                        <span className="block font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</span>
                      </td>
                      <td className="px-3 py-3">
                        {(uploader ? d.uploads.filter((u) => u.destination === uploader) : d.uploads).length === 0
                          ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not uploaded</span>
                          : <div className="flex flex-wrap gap-1.5">
                              {(uploader ? d.uploads.filter((u) => u.destination === uploader) : d.uploads).map((u) => (
                                <span key={u.destination} className="rounded-full px-2 py-0.5 text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                                  {destinationLabel(u.destination)} · {u.uploaded_at ? formatDay(u.uploaded_at, true) : 'synced'}
                                </span>
                              ))}
                            </div>}
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <div className="flex flex-col items-stretch gap-1.5">
                        {!sentToChosen(d) && onUpload && project && (
                          <button type="button" className={`${btnOutline} !px-2.5 !py-1 !text-xs`} aria-label={`Upload the deployment ${d.deployment_id}`} onClick={() => onUpload({ researchProjectId: project.acronym, collection: d.collection })}>Upload</button>
                        )}
                        {d.uploads.length > 0 && (
                          <button type="button" className={`${btnOutline} inline-flex items-center justify-center gap-2`} aria-expanded={opened === d.deployment_id} aria-label={`View the uploads of ${d.deployment_id}`} onClick={() => setOpened(opened === d.deployment_id ? null : d.deployment_id)}>
                            <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" className="fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>View
                          </button>
                        )}
                        </div>
                      </td>
                    </tr>
                    {opened === d.deployment_id && (
                      <tr>
                        <td colSpan={5} className="bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4"><UploadList deployment={d.deployment_id} uploads={d.uploads} /></td>
                      </tr>
                    )}
                  </Fragment>
                ))}
                {shown.length === 0 && <tr><td colSpan={5} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{every.length === 0 ? 'No deployment is created yet: there is nothing to upload.' : 'No deployment matches.'}</td></tr>}
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

          <section aria-label="Legend" className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            <LegendCard title="Created deployments" tone="text-blue-600 dark:text-blue-400"><p>The deployments whose images are stored here. Each says whether it was uploaded: a label for every platform it went to, with the day (press View to see where it went, when, and a link to reach it). One that came from the platform says <em>synced</em>: it was not sent from here.</p></LegendCard>
            <LegendCard title="Progress" tone="text-violet-600 dark:text-violet-400"><p>The ring counts the uploads done over the most there can be: the deployments of the revision times the uploaders picked. Trapper is the only uploader for now; a new one will be one more to pick, and is set up in Settings › Uploader.</p></LegendCard>
          </section>
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
