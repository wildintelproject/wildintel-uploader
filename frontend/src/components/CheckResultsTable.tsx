import { Fragment, useEffect, useMemo, useState } from 'react'
import type { Report, ReportEntry } from '../types'
import { ActiveFilters, ChevronCell, DetailsRow, RowOptions, TABLE, TableCard, TableFooter, TableToolbar } from './DashboardParts'
import { ImageDetails, Thumbnail, formatTaken, pageNumbers } from './CheckFailures'
import IconButton, { ICON_PATHS } from './IconButton'
import { CheckStatusIcon, STRICTNESS_CHOICES, STRICTNESS_SOFT, checkStatus, strictnessOf } from '../pages/ImportDeploymentPage'

export type Group = 'test' | 'image'
export type Show = 'all' | 'issues' | 'passed'
/** What the table shows: by test or by image, and — for each, independently — all of them, only those with issues or only those that passed. The figures above the table press them. */
export interface ResultFilters { group: Group; tests: Show; images: Show }
export const NO_FILTERS: ResultFilters = { group: 'test', tests: 'all', images: 'all' }
const SHOWS: { value: Show; label: string }[] = [{ value: 'all', label: 'All results' }, { value: 'issues', label: 'Only issues / failures' }, { value: 'passed', label: 'Only passed' }]

/** The cards of the images that failed a test are shown eight at a time; the images, ten. */
const CARDS = 8
const PER_PAGE = 10

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

/** The buttons to see the images as pictures or as a list: two icons in a box, the one in use filled. */
export function LayoutToggle({ value, onChange }: { value: 'grid' | 'list'; onChange: (value: 'grid' | 'list') => void }) {
  const icon = { grid: <><rect x="4" y="4" width="6.5" height="6.5" rx="1" /><rect x="13.5" y="4" width="6.5" height="6.5" rx="1" /><rect x="4" y="13.5" width="6.5" height="6.5" rx="1" /><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1" /></>, list: <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" /> }
  return (
    <div className="inline-flex gap-1 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 p-1" role="group" aria-label="View">
      {(['grid', 'list'] as const).map((v) => (
        <button key={v} type="button" aria-pressed={value === v} aria-label={v === 'grid' ? 'Grid view' : 'List view'} title={v === 'grid' ? 'See the images as pictures' : 'See the images as a list'} onClick={() => onChange(v)}
                className={`rounded-lg p-1.5 transition-colors ${value === v ? 'bg-blue-600 text-white' : 'text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>
          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{icon[v]}</svg>
        </button>
      ))}
    </div>
  )
}

/** The images that failed a test, inside its row: to search, to see as cards or as a list, and to page through. */
function FailedImages({ report, label, failures, unit, onDetails }: { report: Report; label: string; failures: ReportEntry[]; unit: { one: string; many: string }; onDetails: (path: string) => void }) {
  const [search, setSearch] = useState('')
  const [tag, setTag] = useState('')
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [page, setPage] = useState(1)
  const tags = useMemo(() => [...new Set(failures.map((e) => e.tag).filter((t): t is string => Boolean(t)))].sort(), [failures])
  const shown = failures.filter((e) => (!tag || e.tag === tag) && e.identifier.toLowerCase().includes(search.trim().toLowerCase()))
  const perPage = view === 'grid' ? CARDS : 20
  const pages = Math.max(1, Math.ceil(shown.length / perPage))
  const current = Math.min(page, pages)
  const visible = shown.slice((current - 1) * perPage, current * perPage)
  const select = 'rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 px-3 py-1.5 text-xs text-zinc-900 dark:text-zinc-200'
  return (
    <section aria-label={`Failures of ${label}`}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
        <h6 className="font-semibold text-amber-700 dark:text-amber-400">{unit.many[0].toUpperCase() + unit.many.slice(1)} failing &lsquo;{label}&rsquo; ({plural(failures.length, 'file', 'files')})</h6>
        <span className="text-xs text-zinc-500 dark:text-zinc-400">Click any {unit.one} to inspect its details</span>
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <input type="search" aria-label="Search by filename" placeholder="Search by filename…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} className={`${select} min-w-[12rem] flex-1`} />
        {tags.length > 1 && (
          <select aria-label="Filter by error" className={select} value={tag} onChange={(e) => { setTag(e.target.value); setPage(1) }}>
            <option value="">All errors</option>
            {tags.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        )}
        <LayoutToggle value={view} onChange={(v) => { setView(v); setPage(1) }} />
      </div>
      {shown.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No {unit.one} matches.</p>}
      {view === 'grid' ? (
        <ul className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(11rem, 1fr))' }}>
          {visible.map((e) => (
            <li key={e.identifier} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 p-2 text-xs">
              <Thumbnail reportId={report.id} path={e.identifier} className="h-28 w-full rounded-lg" />
              <p className="mt-2 font-mono text-sm font-semibold break-all text-zinc-900 dark:text-zinc-100">{e.identifier}</p>
              {e.tag && <p className="mt-0.5 text-amber-700 dark:text-amber-400">{e.tag}</p>}
              <p className="text-zinc-500 dark:text-zinc-400">{formatTaken(e.taken)}</p>
              <button type="button" className="mt-2 w-full rounded-lg border border-blue-500 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30" aria-label={`View details of ${e.identifier}`} onClick={() => onDetails(e.identifier)}>View details</button>
            </li>
          ))}
        </ul>
      ) : shown.length > 0 && (
        <table className="w-full text-sm" aria-label={`Failures of ${label}, as a list`}>
          <thead><tr className="text-left text-xs text-zinc-500 dark:text-zinc-400"><th className="py-1 font-medium">{unit.one[0].toUpperCase() + unit.one.slice(1)}</th><th className="py-1 font-medium">What failed</th><th className="py-1 font-medium">Taken</th><th /></tr></thead>
          <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {visible.map((e) => (
              <tr key={e.identifier} className="align-top">
                <td className="py-1.5 font-mono break-all">{e.identifier}</td>
                <td className="py-1.5 text-amber-700 dark:text-amber-400">{e.message}</td>
                <td className="whitespace-nowrap py-1.5 font-normal text-zinc-500 dark:text-zinc-400">{formatTaken(e.taken)}</td>
                <td className="py-1.5 text-right"><button type="button" className="text-blue-600 dark:text-blue-400 hover:underline" aria-label={`View details of ${e.identifier}`} onClick={() => onDetails(e.identifier)}>View details</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {shown.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500 dark:text-zinc-400">
          <span role="status">Showing {(current - 1) * perPage + 1}–{Math.min(current * perPage, shown.length)} of {shown.length} {unit.many}</span>
          {pages > 1 && (
            <nav className="flex items-center gap-1" aria-label="Pages of the failures">
              <button type="button" className="rounded bg-zinc-200 dark:bg-zinc-800 px-2.5 py-1 disabled:opacity-40" aria-label="Previous page of the failures" disabled={current === 1} onClick={() => setPage(current - 1)}>‹</button>
              {pageNumbers(current, pages).map((n, i) => n === null
                ? <span key={`gap${i}`} className="px-1">…</span>
                : <button key={n} type="button" aria-label={`Page ${n} of the failures`} aria-current={n === current ? 'page' : undefined} onClick={() => setPage(n)}
                          className={`rounded px-2.5 py-0.5 ${n === current ? 'border border-blue-500/30 bg-blue-600/20 text-blue-700 dark:text-blue-300' : 'border border-zinc-300 dark:border-zinc-700'}`}>{n}</button>)}
              <button type="button" className="rounded bg-zinc-200 dark:bg-zinc-800 px-2.5 py-1 disabled:opacity-40" aria-label="Next page of the failures" disabled={current === pages} onClick={() => setPage(current + 1)}>›</button>
            </nav>
          )}
        </div>
      )}
    </section>
  )
}

/** The results of the tests of a report as a table like the ones of the dashboards: by test — each with its strictness and how it ended; the chevron of one that failed opens the
 * images it found, as cards — or by image — each with what the tests found in it; the chevron opens every test, passed or not. "View details" of an image opens its panel. */
export default function CheckResultsTable<T extends string>({ report, options, enabled, required, describe, unit = { one: 'image', many: 'images' }, filters: given, onFilters }: {
  report: Report
  options: { value: T; label: string }[]
  enabled: Set<T>
  required: Set<T>
  describe?: (value: T) => string | undefined
  /** What the things that fail a test are (images). */
  unit?: { one: string; many: string }
  /** The filters, when the page keeps them (its figures press them); the table keeps its own otherwise. */
  filters?: ResultFilters
  onFilters?: (filters: ResultFilters) => void
}) {
  const [own, setOwn] = useState<ResultFilters>(NO_FILTERS)
  const filters = given ?? own
  const setFilters = onFilters ?? setOwn
  const { group } = filters
  const show = group === 'test' ? filters.tests : filters.images
  const setGroup = (g: Group) => setFilters({ ...filters, group: g })
  const setShow = (v: Show) => setFilters(group === 'test' ? { ...filters, tests: v } : { ...filters, images: v })
  const [query, setQuery] = useState('')
  const [openTest, setOpenTest] = useState<T | null>(null)
  const [openImage, setOpenImage] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [details, setDetails] = useState<string | null>(null)
  // By image, the images are seen as a list or as pictures.
  const [layout, setLayout] = useState<'grid' | 'list'>('list')
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const all = (text: string) => words.every((w) => text.toLowerCase().includes(w))

  // by test
  const tests = options.map((opt) => {
    const info = report.checks[opt.value]
    const runs = enabled.has(opt.value)
    const failed = runs && info ? info.failed : 0
    return { ...opt, runs, info, failed, passed: runs && Boolean(info) && failed === 0, strictness: strictnessOf(runs, required.has(opt.value)) }
  }).filter((t) => (show === 'all' || (show === 'issues' ? t.failed > 0 : t.passed)) && all(`${t.label} ${describe?.(t.value) ?? ''}`))

  // by image: every image the report speaks of, with what each test found in it
  const images = useMemo(() => {
    const by = new Map<string, ReportEntry[]>()
    for (const e of report.entries) {
      if (report.checks[e.check]?.scope !== 'images') continue
      by.set(e.identifier, [...(by.get(e.identifier) ?? []), e])
    }
    return [...by.entries()].map(([path, entries]) => ({ path, entries, failed: entries.filter((e) => e.status !== 'ok').length, taken: entries.find((e) => e.taken)?.taken }))
      .sort((a, b) => a.path.localeCompare(b.path, undefined, { numeric: true }))
  }, [report])
  const shownImages = images.filter((i) => (show === 'all' || (show === 'issues' ? i.failed > 0 : i.failed === 0)) && all(`${i.path} ${i.entries.filter((e) => e.status !== 'ok').map((e) => `${report.checks[e.check]?.label ?? e.check} ${e.message}`).join(' ')}`))
  const perPage = layout === 'grid' ? 12 : PER_PAGE
  const pages = Math.max(1, Math.ceil(shownImages.length / perPage))
  const current = Math.min(page, pages)
  const onPage = shownImages.slice((current - 1) * perPage, current * perPage)
  useEffect(() => setPage(1), [show, query, group, layout])

  const th = `${TABLE.th} sticky top-0 bg-zinc-100 dark:bg-zinc-900`
  const reset = () => { setFilters(NO_FILTERS); setQuery(''); setOpenTest(null); setOpenImage(null) }

  return (
    <div className="mb-3">
      <TableCard label="Results of the tests">
        <TableToolbar searchLabel="Search the results" placeholder={group === 'test' ? 'Search by test…' : `Search by ${unit.one} name or by what was found…`} text={query} onText={setQuery} onReset={reset} extra={group === 'image' ? <LayoutToggle value={layout} onChange={setLayout} /> : undefined}
          choice={[
            { label: 'Group by', value: group, onChange: (v) => { setGroup(v as Group); setOpenTest(null); setOpenImage(null) }, options: [{ value: 'test', label: 'Test' }, { value: 'image', label: unit.one === 'image' ? 'Image' : unit.one[0].toUpperCase() + unit.one.slice(1) }], all: null },
            { label: 'Results', value: show, onChange: (v) => setShow(v as Show), options: SHOWS, all: null },
          ]} />
        <ActiveFilters
          filters={[{ label: `Group by: ${group === 'test' ? 'Test' : unit.one[0].toUpperCase() + unit.one.slice(1)}`, tone: 'blue' }, { label: `Results: ${SHOWS.find((s) => s.value === show)!.label}`, tone: 'green' }, ...(query.trim() ? [{ label: `Search: ${query.trim()}`, tone: 'blue' as const }] : [])]}
          summary={group === 'test' ? `${tests.length} of ${options.length} tests match` : `${shownImages.length} of ${images.length} ${images.length === 1 ? unit.one : unit.many} match`} />

        {group === 'test' ? (
          <div className="max-h-[32rem] overflow-y-auto">
            <table className={TABLE.table} aria-label="Tests">
              <thead className={TABLE.head}>
                <tr>
                  <th scope="col" className={`${th} w-10 !px-2`}><span className="sr-only">Details</span></th>
                  <th scope="col" className={`${th} w-12`}><span className="sr-only">Status</span></th>
                  <th scope="col" className={`${th} text-left`}>Check</th>
                  <th scope="col" className={`${th} text-center`}>How strict</th>
                  <th scope="col" className={`${th} text-right`}>Result</th>
                </tr>
              </thead>
              <tbody className={TABLE.body}>
                {tests.map((t) => {
                  const failures = report.entries.filter((e) => e.check === t.value && e.status === 'failed')
                  const open = openTest === t.value
                  const status = checkStatus(t.runs, false, t.info ? t.failed === 0 : null)
                  return (
                    <Fragment key={t.value}>
                      <tr className={TABLE.row(open)}>
                        <ChevronCell open={open} available={t.failed > 0} label={`the failures of ${t.label}`} onToggle={() => setOpenTest(open ? null : t.value)} />
                        <td className="py-3 text-center align-middle"><CheckStatusIcon status={status} required={t.strictness === 'must'} label={t.label} /></td>
                        <td className="px-4 py-3 text-zinc-800 dark:text-zinc-200">
                          <span className="font-semibold">{t.label}</span>
                          {describe?.(t.value) && <span className="block text-xs font-normal text-zinc-500 dark:text-zinc-400">{describe(t.value)}.</span>}
                        </td>
                        <td className="px-4 py-3 text-center"><span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STRICTNESS_SOFT[t.strictness]}`}>{STRICTNESS_CHOICES.find((c) => c.value === t.strictness)!.label}</span></td>
                        <td className="px-4 py-3 text-right">
                          {!t.runs ? <span className="text-xs text-zinc-400 dark:text-zinc-500">Skipped</span> : t.info && (
                            <span className="inline-flex flex-col items-end gap-0.5">
                              <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${t.failed > 0 ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300' : 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'}`}>{t.failed > 0 ? 'Failed' : 'Passed'}</span>
                              <span className="text-xs font-normal text-zinc-500 dark:text-zinc-400">{t.failed === 0 ? '0' : t.info.scope === 'images' ? plural(t.failed, unit.one, unit.many) : 'Whole folder'}</span>
                            </span>
                          )}
                        </td>
                      </tr>
                      {open && (
                        <DetailsRow colSpan={5}>
                          {t.info?.scope === 'images' ? (
                            <>
                              <FailedImages report={report} label={t.label} failures={failures} unit={unit} onDetails={setDetails} />
                            </>
                          ) : (
                            <ul className="space-y-1 text-sm">{failures.map((e, i) => <li key={i} className="text-amber-700 dark:text-amber-400">{e.message}</li>)}</ul>
                          )}
                        </DetailsRow>
                      )}
                    </Fragment>
                  )
                })}
                {tests.length === 0 && <tr><td colSpan={5} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No test matches.</td></tr>}
              </tbody>
            </table>
          </div>
        ) : (
          <>
            {layout === 'grid' ? (
              <div className="p-4">
                {shownImages.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No {unit.one} matches.</p>}
                <ul className="grid gap-3" aria-label={`The ${unit.many}, as pictures`} style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(11rem, 1fr))' }}>
                  {onPage.map((i) => (
                    <li key={i.path} className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950/40 p-2 text-xs">
                      <Thumbnail reportId={report.id} path={i.path} className="h-28 w-full rounded-lg" />
                      <p className="mt-2 font-mono text-sm font-semibold break-all text-zinc-900 dark:text-zinc-100">{i.path}</p>
                      <p className="text-zinc-500 dark:text-zinc-400">{formatTaken(i.taken)}</p>
                      <span className={`mt-1 inline-block rounded-full px-2 py-0.5 font-semibold ${i.failed > 0 ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300' : 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'}`}>
                        {i.failed > 0 ? `${plural(i.failed, 'failure', 'failures')} of ${i.entries.length}` : `${i.entries.length} passed`}
                      </span>
                      <button type="button" className="mt-2 w-full rounded-lg border border-blue-500 py-1 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/30" aria-label={`View details of ${i.path}`} onClick={() => setDetails(i.path)}>View details</button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
            <div className="overflow-x-auto">
              <table className={TABLE.table} aria-label={`By ${unit.one}`}>
                <thead className={TABLE.head}>
                  <tr>
                    <th scope="col" className={`${TABLE.th} w-10 !px-2`}><span className="sr-only">Details</span></th>
                    <th scope="col" className={TABLE.th}>{unit.one[0].toUpperCase() + unit.one.slice(1)}</th>
                    <th scope="col" className={TABLE.th}>Taken</th>
                    <th scope="col" className={TABLE.th}>Tests</th>
                    <th scope="col" className={TABLE.th}><span className="sr-only">Options</span></th>
                  </tr>
                </thead>
                <tbody className={TABLE.body}>
                  {onPage.map((i) => {
                    const open = openImage === i.path
                    return (
                      <Fragment key={i.path}>
                        <tr className={TABLE.row(open)}>
                          <ChevronCell open={open} label={`the tests of ${i.path}`} onToggle={() => setOpenImage(open ? null : i.path)} />
                          <td className="px-4 py-3 font-mono font-semibold text-zinc-900 dark:text-zinc-200">{i.path}</td>
                          <td className="whitespace-nowrap px-4 py-3 font-normal text-zinc-700 dark:text-zinc-300">{formatTaken(i.taken)}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${i.failed > 0 ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300' : 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'}`}>
                              {i.failed > 0 ? `${plural(i.failed, 'failure', 'failures')} of ${i.entries.length}` : `${i.entries.length} passed`}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-4 py-3">
                            <RowOptions label={`Options of ${i.path}`}>
                              <IconButton compact label={`View details of ${i.path}`} title={`View the details of the ${unit.one}`} onClick={() => setDetails(i.path)} path={ICON_PATHS.view} />
                            </RowOptions>
                          </td>
                        </tr>
                        {open && (
                          <DetailsRow colSpan={5}>
                            <ul className="space-y-2 text-sm" aria-label={`Tests of ${i.path}`}>
                              {i.entries.map((e, n) => {
                                const failed = e.status !== 'ok'
                                return (
                                  <li key={`${e.check}|${n}`} className="flex items-center gap-3 rounded-xl border border-zinc-200 dark:border-zinc-800 px-4 py-2.5">
                                    <CheckStatusIcon status={failed ? 'failed' : 'passed'} required={false} label={report.checks[e.check]?.label ?? e.check} />
                                    <span className="flex-1 font-medium text-zinc-800 dark:text-zinc-200">{report.checks[e.check]?.label ?? e.check}</span>
                                    <span className={`text-xs ${failed ? 'text-amber-700 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>{failed ? e.message : 'Passed'}</span>
                                  </li>
                                )
                              })}
                            </ul>
                          </DetailsRow>
                        )}
                      </Fragment>
                    )
                  })}
                  {shownImages.length === 0 && <tr><td colSpan={5} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No {unit.one} matches.</td></tr>}
                </tbody>
              </table>
            </div>
            )}
            {shownImages.length > 0 && <TableFooter from={(current - 1) * perPage + 1} to={Math.min(current * perPage, shownImages.length)} total={shownImages.length} noun={unit.many} page={current} pages={pages} onPage={(n) => { setPage(n); setOpenImage(null) }} />}
          </>
        )}
      </TableCard>
      {details && <ImageDetails report={report} path={details} onClose={() => setDetails(null)} />}
    </div>
  )
}
