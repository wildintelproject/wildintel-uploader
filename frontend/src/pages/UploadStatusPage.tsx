import { useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import { Icon, LegendCard, StateCard } from '../components/Dashboard'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import RevisionSquares from '../components/RevisionSquares'
import { MENU_ICONS, PageHeader } from '../components/TaskCard'
import { formatDay } from '../dateFormat'
import type { UploadEntry, UploadedDeployment } from '../types'
import { UPLOAD_DESTINATIONS, destinationLabel } from '../uploadDestinations'
import { btnOutline, inputClass } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
}

/** How many deployments a page has. */
const PER_PAGE = 10

/** What the table shows: all the created deployments, the ones not uploaded anywhere, or the ones uploaded to a platform (its id). */
const NOT_UPLOADED = 'none'

const plural = (n: number) => `${n} ${n === 1 ? 'deployment' : 'deployments'}`

/** What an upload did, in a few words — for the tooltip of its label. */
function whatItDid(u: UploadEntry): string {
  if (u.kind === 'synced') return `It came from ${destinationLabel(u.destination)}: it was not sent from here`
  const parts = u.parts != null ? `${u.parts} ${u.parts === 1 ? 'package' : 'packages'}` : ''
  const made = [u.location_created && 'location', u.deployment_created && 'deployment'].filter(Boolean).join(' and ')
  return [parts, made && `${made} created there`].filter(Boolean).join(' · ')
}

/** The dashboard of the uploads of the default research project: its created deployments, by revision, each with a label for every platform it was uploaded to and the day. */
export default function UploadStatusPage({ onBack, onOpenSettings, settingsOpen }: Props) {
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [deployments, setDeployments] = useState<UploadedDeployment[] | null>(null)
  // every revision the deployments have — also the ones with nothing created yet
  const [allRevisions, setAllRevisions] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState('')
  const [shownFilter, setShownFilter] = useState('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
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
  const destinations = [...UPLOAD_DESTINATIONS.map((d) => d.id as string), ...new Set(every.flatMap((d) => d.uploads.map((u) => u.destination)).filter((x) => !UPLOAD_DESTINATIONS.some((k) => k.id === x)))]
  const sentTo = (d: UploadedDeployment, to: string) => d.uploads.some((u) => u.destination === to)
  const notUploaded = own.filter((d) => d.uploads.length === 0)
  const needle = text.trim().toLowerCase()
  const shown = own
    .filter((d) => !shownFilter || (shownFilter === NOT_UPLOADED ? d.uploads.length === 0 : sentTo(d, shownFilter)))
    .filter((d) => !needle || `${d.deployment_id} ${d.site} ${d.collection} ${d.uploads.map((u) => destinationLabel(u.destination)).join(' ')}`.toLowerCase().includes(needle))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const pick = (value: string) => { setShownFilter(shownFilter === value ? '' : value); setPage(1) }

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

          <section aria-label="Uploads by platform" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a card to show only those deployments.</p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="col-span-2 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4 lg:col-span-1">
                <span aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
                  <Icon path={<path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />} className="h-6 w-6" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{revision ? `Created in ${revision}` : 'Created deployments'}</p>
                  <p className="text-3xl font-semibold leading-tight">{own.length}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{own.length - notUploaded.length} uploaded · {notUploaded.length} not yet</p>
                </div>
              </div>
              <StateCard label="Not uploaded" note="Created, sent nowhere yet" count={notUploaded.length} tone="text-zinc-600 dark:text-zinc-300"
                         badge="bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300" icon={<Icon path={<><circle cx="12" cy="12" r="9" /><path d="M8 12h8" /></>} className="h-5 w-5" />}
                         pressed={shownFilter === NOT_UPLOADED} onPress={() => pick(NOT_UPLOADED)} />
              {destinations.map((d) => (
                <StateCard key={d} label={destinationLabel(d)} note="Uploaded to it" count={own.filter((x) => sentTo(x, d)).length} tone="text-blue-600 dark:text-blue-400"
                           badge="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" icon={<Icon path={<><path d="M20 16.2A4.5 4.5 0 0017.5 8h-1.8A7 7 0 104 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} className="h-5 w-5" />}
                           pressed={shownFilter === d} onPress={() => pick(d)} />
              ))}
            </div>
          </section>

          <div role="search" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the deployments" className={`${inputClass} !pl-9`} placeholder="Search by deployment, site, revision, platform…" value={text} onChange={(e) => { setText(e.target.value); setPage(1) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Show
              <select aria-label="Show" className={`${inputClass} !w-auto`} value={shownFilter} onChange={(e) => { setShownFilter(e.target.value); setPage(1) }}>
                <option value="">All</option>
                <option value={NOT_UPLOADED}>Not uploaded</option>
                {destinations.map((d) => <option key={d} value={d}>Uploaded to {destinationLabel(d)}</option>)}
              </select>
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Deployments">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Revision', 'Where', 'Uploaded'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((d) => (
                  <tr key={d.deployment_id}>
                    <td className="px-3 py-3 font-mono text-xs font-semibold">{d.deployment_id}</td>
                    <td className="px-3 py-3 font-mono text-xs">{d.collection}</td>
                    <td className="px-3 py-3 font-mono text-xs">{d.site}</td>
                    <td className="px-3 py-3">
                      {d.uploads.length === 0
                        ? <span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Not uploaded</span>
                        : <div className="flex flex-wrap gap-1.5">
                            {d.uploads.map((u) => (
                              <span key={u.destination} title={whatItDid(u)} className="rounded-full px-2 py-0.5 text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">
                                {destinationLabel(u.destination)} · {u.uploaded_at ? formatDay(u.uploaded_at, true) : 'synced'}
                              </span>
                            ))}
                          </div>}
                    </td>
                  </tr>
                ))}
                {shown.length === 0 && <tr><td colSpan={4} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{every.length === 0 ? 'No deployment is created yet: there is nothing to upload.' : 'No deployment matches.'}</td></tr>}
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
            <LegendCard title="Created deployments" tone="text-blue-600 dark:text-blue-400"><p>The deployments whose images are stored here. Each says whether it was uploaded: a label for every platform it went to, with the day (hover it to see what the upload did). One that came from the platform says <em>synced</em>: it was not sent from here.</p></LegendCard>
            <LegendCard title="Platforms" tone="text-violet-600 dark:text-violet-400"><p>Each platform has its card, which shows only what went to it. Trapper is the only one for now; a new one will have its own card and its own labels, and is set up in Settings › Uploader.</p></LegendCard>
          </section>
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
