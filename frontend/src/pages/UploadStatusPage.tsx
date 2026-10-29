import { Fragment, useEffect, useState } from 'react'
import { api } from '../api'
import { pageNumbers } from '../components/CheckFailures'
import { Icon, LegendCard, StateCard } from '../components/Dashboard'
import RevisionSquares from '../components/RevisionSquares'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import { MENU_ICONS, PageHeader } from '../components/TaskCard'
import { formatDay } from '../dateFormat'
import type { UploadRecord } from '../types'
import { UPLOAD_DESTINATIONS, destinationLabel } from '../uploadDestinations'
import { btnOutline, inputClass } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
}

/** How many uploads a page has. */
const PER_PAGE = 10

const plural = (n: number) => `${n} ${n === 1 ? 'upload' : 'uploads'}`
const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`

/** What an upload did, in a few words. */
function whatItDid(u: UploadRecord): string {
  if (u.kind === 'synced') return `Synced from ${destinationLabel(u.destination)}: it was not sent from here`
  const parts = u.parts != null ? `${u.parts} ${u.parts === 1 ? 'package' : 'packages'}` : ''
  const made = [u.location_created && 'location', u.deployment_created && 'deployment'].filter(Boolean).join(' and ')
  return [parts, made && `${made} created there`].filter(Boolean).join(' · ')
}

/** The dashboard of the uploads of the default research project: the deployments that went to a platform — which one, when and how — and a card for each platform. */
export default function UploadStatusPage({ onBack, onOpenSettings, settingsOpen }: Props) {
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [uploads, setUploads] = useState<UploadRecord[] | null>(null)
  // every revision the deployments have — also the ones with no upload yet
  const [allRevisions, setAllRevisions] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [revision, setRevision] = useState('')
  const [destination, setDestination] = useState('')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const error = projectError ?? loadError

  useEffect(() => {
    setUploads(null); setLoadError(null); setRevision('')
    if (!project) return
    let cancelled = false
    api.uploads(project.acronym)
      .then(({ results, revisions }) => { if (!cancelled) { setUploads(results); setAllRevisions(revisions ?? []) } })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the uploads.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  const everyUpload = uploads ?? []
  // the revisions the project has, the newest first; the cards, the table and the last upload follow the one picked
  const revisions = [...new Set([...allRevisions, ...everyUpload.map((u) => u.collection)])].sort((a, b) => b.localeCompare(a))
  const all = revision ? everyUpload.filter((u) => u.collection === revision) : everyUpload
  // a card for each platform there is — also the ones with no upload yet — and for any other an upload names
  const destinations = [...UPLOAD_DESTINATIONS.map((d) => d.id as string), ...new Set(all.map((u) => u.destination).filter((d) => !UPLOAD_DESTINATIONS.some((k) => k.id === d)))]
  const needle = text.trim().toLowerCase()
  const shown = all
    .filter((u) => !destination || u.destination === destination)
    .filter((u) => !needle || `${u.deployment_id} ${u.site} ${u.collection} ${destinationLabel(u.destination)}`.toLowerCase().includes(needle))
  const pages = Math.max(1, Math.ceil(shown.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const last = all.find((u) => u.uploaded_at)

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <PageHeader icon={MENU_ICONS.upload} title="Uploads dashboard" description="The deployments that have been uploaded: where they went, when, and what the upload did."
        parent="Manage uploads" onParent={onBack}
        aside={project !== undefined || defaultAcronym !== null ? <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The dashboard" onOpenSettings={onOpenSettings} /> : undefined} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && uploads === null && <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the uploads…</p>}

      {uploads !== null && (
        <>
          {revisions.length > 0 && (
            <section aria-label="Revision" className="mb-6">
              <h5 className="text-lg font-semibold mb-1">Revision</h5>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-3">A revision is one visit to every site. Pick one to see its uploads.</p>
              <RevisionSquares all={{ label: 'All revisions', note: plural(everyUpload.length) }} value={revision}
                revisions={revisions.map((r) => ({ id: r, label: r, note: plural(everyUpload.filter((u) => u.collection === r).length) }))}
                onPick={(id) => { setRevision(id); setPage(1) }} />
            </section>
          )}

          <section aria-label="Uploads by platform" className="mb-5">
            <p className="mb-2 text-right text-xs text-zinc-500 dark:text-zinc-400">Pick a platform to show only its uploads.</p>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="col-span-2 flex items-center gap-4 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4">
                <span aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400">
                  <Icon path={<><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} className="h-6 w-6" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">Uploaded deployments</p>
                  <p className="text-3xl font-semibold leading-tight">{all.length}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">{last?.uploaded_at ? `The last, ${last.deployment_id}, on ${when(last.uploaded_at)}` : 'None uploaded from here yet'}</p>
                </div>
              </div>
              {destinations.map((d) => (
                <StateCard key={d} label={destinationLabel(d)} note="Uploads to it" count={all.filter((u) => u.destination === d).length} tone="text-blue-600 dark:text-blue-400"
                           badge="bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" icon={<Icon path={<><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>} className="h-5 w-5" />}
                           pressed={destination === d} onPress={() => { setDestination(destination === d ? '' : d); setPage(1) }} />
              ))}
            </div>
          </section>

          <div role="search" className="mb-3 flex flex-wrap items-center gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-3 py-2.5">
            <div className="relative min-w-[14rem] flex-1">
              <span aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"><Icon path={<><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>} className="h-4 w-4" /></span>
              <input aria-label="Filter the uploads" className={`${inputClass} !pl-9`} placeholder="Search by deployment, site, revision, platform…" value={text} onChange={(e) => { setText(e.target.value); setPage(1) }} />
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-300">Platform
              <select aria-label="Platform" className={`${inputClass} !w-auto`} value={destination} onChange={(e) => { setDestination(e.target.value); setPage(1) }}>
                <option value="">All</option>
                {destinations.map((d) => <option key={d} value={d}>{destinationLabel(d)}</option>)}
              </select>
            </label>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Uploads">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Revision', 'Platform', 'Uploaded', 'What it did'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((u) => (
                  <Fragment key={`${u.destination}|${u.deployment_id}`}>
                    <tr>
                      <td className="px-3 py-3 font-mono text-xs font-semibold">{u.deployment_id}</td>
                      <td className="px-3 py-3 font-mono text-xs">{u.collection}</td>
                      <td className="px-3 py-3"><span className="rounded-full px-2 py-0.5 text-xs font-semibold bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300">{destinationLabel(u.destination)}</span></td>
                      <td className="px-3 py-3 font-mono text-xs">{u.uploaded_at ? when(u.uploaded_at) : <span className="font-sans text-zinc-400">—</span>}</td>
                      <td className="px-3 py-3 text-xs text-zinc-600 dark:text-zinc-400">{whatItDid(u)}</td>
                    </tr>
                  </Fragment>
                ))}
                {shown.length === 0 && <tr><td colSpan={5} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{everyUpload.length === 0 ? 'No deployment has been uploaded yet.' : 'No upload matches.'}</td></tr>}
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
            <LegendCard title="Uploads" tone="text-blue-600 dark:text-blue-400"><p>An upload is a deployment sent to a platform: which one, when, and what it did there (how many packages, and whether its location and its deployment were created). One that came from the platform is shown with no day: it was not sent from here.</p></LegendCard>
            <LegendCard title="Platforms" tone="text-violet-600 dark:text-violet-400"><p>Each platform has its card, which filters the table. Trapper is the only one for now; a new one will have its own card here, and is set up in Settings › Uploader.</p></LegendCard>
          </section>
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
