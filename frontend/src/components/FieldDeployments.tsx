import { useEffect, useRef, useState, type ReactNode } from 'react'
import { formatDay } from '../dateFormat'
import { btnOutline } from '../pages/ImportDeploymentPage'
import type { FieldDeployment } from '../types'
import { pageNumbers } from './CheckFailures'
import RevisionSquares from './RevisionSquares'

/** How many deployments a page has. */
const PER_PAGE = 10

/** The rows the status squares show: all of them, the closed ones with their images stored, the ones whose camera is still out, and the closed ones with images stored that are not on Trapper. */
export type Filter = '' | 'closed' | 'open' | 'to_upload'
const matches = (d: FieldDeployment, f: Filter) =>
  !f || (f === 'open' ? d.status === 'open' : f === 'closed' ? d.status === 'closed' && Boolean(d.images_stored) : d.status === 'closed' && Boolean(d.images_stored) && !d.on_trapper)

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

/** The deployments the visits of a research project say, as a book: a square for each revision (collection), the status squares of the one picked, and a table — the one a link of the visit book goes to is highlighted. */
export default function FieldDeployments({ deployments, highlight, initialFilter = '', belowSummary }: { deployments: FieldDeployment[]; highlight?: string; initialFilter?: Filter; belowSummary?: ReactNode }) {
  const [revision, setRevision] = useState('')
  const [filter, setFilter] = useState<Filter>(initialFilter)
  const [page, setPage] = useState(1)
  const revisions = [...new Set(deployments.map((d) => d.collection))].sort((a, b) => b.localeCompare(a))
  const inRevision = revision ? deployments.filter((d) => d.collection === revision) : deployments
  const shown = inRevision.filter((d) => matches(d, filter))
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

  const SQUARES: { filter: Filter; label: string; note: string; tone: string }[] = [
    { filter: '', label: revision ? `Deployments of ${revision}` : 'All the deployments', note: 'one per camera and site', tone: 'text-zinc-900 dark:text-zinc-100' },
    { filter: 'closed', label: 'Closed', note: 'camera collected, images stored', tone: 'text-emerald-600 dark:text-emerald-400' },
    { filter: 'open', label: 'Camera still out', note: 'waiting for the next visit', tone: 'text-amber-600 dark:text-amber-400' },
    { filter: 'to_upload', label: 'Not on Trapper yet', note: 'closed, ready to upload', tone: 'text-blue-600 dark:text-blue-400' },
  ]
  const square = 'rounded-xl border px-4 py-3 text-left transition-colors'
  const pressed = 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
  const idle = 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'

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
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <h5 className="text-lg font-semibold">{revision ? `Revision ${revision}: deployments by status` : 'Deployments by status'}</h5>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Pick a square to show only those deployments.</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {SQUARES.map((s) => (
                <button key={s.label} type="button" aria-pressed={filter === s.filter} onClick={() => { setFilter(filter === s.filter ? '' : s.filter); setPage(1) }} className={`${square} ${filter === s.filter ? pressed : idle}`}>
                  <span className="block text-xs font-semibold text-zinc-600 dark:text-zinc-300">{s.label}</span>
                  <span className={`block text-3xl font-semibold leading-tight ${s.tone}`}>{count(s.filter)}</span>
                  <span className="block text-xs text-zinc-500 dark:text-zinc-400">{s.note}</span>
                </button>
              ))}
            </div>
          </section>

          {belowSummary}

          <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-sm" aria-label="Deployments">
              <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                <tr>{['Deployment', 'Where', 'Status', 'Period', 'Card and photos', 'On Trapper'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {onPage.map((d) => (
                  <tr key={d.deployment_id} ref={d.deployment_id === highlight ? marked : undefined} aria-current={d.deployment_id === highlight ? 'true' : undefined} className={d.deployment_id === highlight ? 'bg-blue-50 dark:bg-blue-950/40' : ''}>
                    <td className="px-3 py-3 font-mono text-xs font-semibold">{d.deployment_id}</td>
                    <td className="px-3 py-3 font-mono text-xs">{d.site}</td>
                    <td className="px-3 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${d.status === 'closed' ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'}`}>{d.status === 'closed' ? 'Closed' : 'Camera still out'}</span>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs">{when(d.start)} → {d.end ? when(d.end) : '…'}</td>
                    <td className="px-3 py-3 text-xs text-zinc-600 dark:text-zinc-400">{[d.card && `Card ${d.card}`, d.photos_counted != null && `${d.photos_counted} photos`].filter(Boolean).join(' · ')}</td>
                    <td className="px-3 py-3">
                      {d.on_trapper
                        ? <span role="img" aria-label="On Trapper" title={d.uploaded_at ? `Uploaded to Trapper on ${d.uploaded_at.slice(0, 10)}` : 'On Trapper: synced from there'} className="inline-flex text-emerald-600 dark:text-emerald-400">
                            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
                          </span>
                        : <span role="img" aria-label="Not on Trapper" title="Not uploaded to Trapper" className="inline-flex text-zinc-400 dark:text-zinc-500">
                            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M9 9l6 6M15 9l-6 6" /></svg>
                          </span>}
                    </td>
                  </tr>
                ))}
                {shown.length === 0 && <tr><td colSpan={6} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No deployment matches.</td></tr>}
              </tbody>
            </table>
          </div>

          {shown.length > PER_PAGE && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
              <span role="status" className="text-zinc-500 dark:text-zinc-400">Deployments {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, shown.length)} of {shown.length}</span>
              <nav className="flex items-center gap-1" aria-label="Pages">
                <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Previous page" disabled={current === 1} onClick={() => setPage(current - 1)}>‹</button>
                {pageNumbers(current, pages).map((n, i) => n === null
                  ? <span key={`gap${i}`} className="px-1 text-zinc-400">…</span>
                  : <button key={n} type="button" aria-label={`Page ${n}`} aria-current={n === current ? 'page' : undefined} onClick={() => setPage(n)}
                            className={`px-2.5 py-1 rounded ${n === current ? 'bg-blue-600 text-white' : 'border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300'}`}>{n}</button>)}
                <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Next page" disabled={current === pages} onClick={() => setPage(current + 1)}>›</button>
              </nav>
            </div>
          )}
        </>
      )}
    </div>
  )
}
