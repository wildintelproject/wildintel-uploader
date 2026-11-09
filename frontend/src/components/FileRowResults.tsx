import { Fragment, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { btnOutline } from '../pages/ImportDeploymentPage'
import { pageNumbers } from './CheckFailures'
import IconButton, { ICON_PATHS } from './IconButton'
import { plural } from './SessionResults'

export interface FileRow {
  row: number
  site: string
  /** The revision the row says it is of, when it says. */
  session?: string
  /** The day and the time (HH:MM) of the visit the row says, when it says and they are valid. */
  date?: string
  time?: string
  /** What the row does, as the dashboard of visits says it (Revision + Installation); as the file wrote it when it is not valid. */
  actions?: string
  result: 'ok' | 'problem' | 'already_kept' | 'new_site' | 'ignored'
  /** The kind of error — what the rows that share it have in common. Empty for a row that is fine. */
  label?: string
  message: string
  /** What is odd in a row that is added — said, not refused: the visit is kept as the file wrote it. */
  warnings?: string[]
  /** What the row says, by the field of a visit each cell is of — with the defaults filled in. */
  data?: Record<string, string>
}

/** What the pill of a row says, and its colours: ready to add, skipped (already kept, or ignored) or an error — which one it is, its errors tell. */
/** A row that is added, with something odd in it to check. */
const warned = (r: FileRow) => r.result === 'ok' && (r.warnings?.length ?? 0) > 0
const badgeOf = (r: FileRow) => (r.result === 'ok' ? (warned(r) ? 'Add · to check' : 'Add') : r.result === 'already_kept' ? 'Skipped / Existing' : r.result === 'ignored' ? 'Skipped / Ignored' : 'Error')
/** One colour for each thing a row can be, the same in the figures, the filters, the pills and the tables: ready is green, skipped (already kept, ignored) is amber and an error is red. */
type Tone = 'ready' | 'skipped' | 'errors'
const toneKey = (r: FileRow): Tone => (r.result === 'ok' ? 'ready' : r.result === 'already_kept' || r.result === 'ignored' ? 'skipped' : 'errors')
const TONES: Record<Tone, { text: string; pill: string; row: string }> = {
  ready: { text: 'text-emerald-700 dark:text-emerald-400', pill: 'border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300', row: 'bg-emerald-50 dark:bg-emerald-950/30' },
  skipped: { text: 'text-amber-700 dark:text-amber-400', pill: 'border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300', row: 'bg-amber-50 dark:bg-amber-950/30' },
  errors: { text: 'text-red-700 dark:text-red-400', pill: 'border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300', row: 'bg-red-50 dark:bg-red-950/30' },
}
/** The colour a row is told in: what it is, but amber for a row that is added with something to check. */
const shownTone = (r: FileRow): Tone => (warned(r) ? 'skipped' : toneKey(r))
const toneOf = (r: FileRow) => TONES[shownTone(r)].pill
const kindOf = (r: FileRow) => (warned(r) ? 'To check' : r.label || 'Problem')
/** What is wrong with a row, as it is said of it: its message, or what is odd in it. */
const saidOf = (r: FileRow) => (warned(r) ? r.warnings!.join(' ') : r.message)

/** How many rows a page of the table has. */
const PER_PAGE = 10

type SortKey = 'row' | 'site' | 'visit' | 'actions' | 'date' | 'status'
const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'row', label: 'Row' }, { key: 'visit', label: 'Visit' }, { key: 'site', label: 'Site ID' }, { key: 'actions', label: 'Actions' }, { key: 'date', label: 'When' }, { key: 'status', label: 'Status' },
]

type Filter = 'all' | 'ready' | 'skipped' | 'errors'
/** What a filter keeps — the figures at the top apply them: the rows to add (ready), those left out because they are already kept or ignored (skipped), and those with a problem or a site that is not a location (errors). */
const FILTERS: { value: Filter; keeps: (r: FileRow) => boolean }[] = [
  { value: 'all', keeps: () => true },
  { value: 'ready', keeps: (r) => toneKey(r) === 'ready' },
  { value: 'skipped', keeps: (r) => toneKey(r) === 'skipped' },
  { value: 'errors', keeps: (r) => toneKey(r) === 'errors' },
]

/** The icon of the button that shows what is wrong with a row. */
const ALERT_PATH = <><circle cx="12" cy="12" r="9" /><path d="M12 7.500v5M12 16h.01" /></>

const viewClass = (active: boolean) => `flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${active ? 'bg-blue-600 text-white' : 'text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`

/** What became of each row of a file that is read, laid out like the results of the checks of the deployments: the figures, and the rows — each with what
 * went wrong in it — or, by error, each kind of error with the rows that have it, to pick one and see them. */
export default function FileRowResults({ rows, labels = {} }: {
  rows: FileRow[]
  /** The name of each field of a visit, as it is shown beside what the row says of it. */
  labels?: Record<string, string>
}) {
  const [view, setView] = useState<'row' | 'error'>('row')
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const isFlagged = (r: FileRow) => r.result !== 'ok' || warned(r)
  const flagged = rows.filter(isFlagged)
  // The row that is open, and what is shown of it: what it says (its contents) or what is wrong with it (its errors). The first row with errors starts open.
  const [opened, setOpened] = useState<{ row: number; panel: 'contents' | 'errors' } | null>(flagged[0] ? { row: flagged[0].row, panel: 'errors' } : null)
  const [picked, setPicked] = useState<string | null>(null)
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({ key: 'row', descending: false })

  const keeps = FILTERS.find((f) => f.value === filter)!.keeps
  // The search: every word typed is somewhere in the row — its number, site, visit, actions, when, what became of it, or what is wrong with it.
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const matches = (r: FileRow) => {
    const text = [r.row, r.site, r.session, r.actions, r.date, r.time, badgeOf(r), isFlagged(r) ? kindOf(r) : '', r.message, ...(r.warnings ?? [])].join(' ').toLowerCase()
    return words.every((w) => text.includes(w))
  }
  const shown = rows.filter(keeps).filter(matches)
  const sortValue = (r: FileRow, key: SortKey) => (key === 'row' ? r.row : key === 'site' ? r.site.toLowerCase() : key === 'visit' ? r.session ?? '' : key === 'actions' ? r.actions ?? '' : key === 'date' ? `${r.date ?? ''} ${r.time ?? ''}`.trim() : badgeOf(r))
  const sorted = [...shown].sort((a, b) => {
    const x = sortValue(a, sort.key), y = sortValue(b, sort.key)
    const order = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
    return (sort.descending ? -order : order) || a.row - b.row
  })
  // The table goes ten rows at a time; it starts again from the first page when what it shows changes.
  useEffect(() => setPage(1), [filter, query, sort.key, sort.descending])
  const pages = Math.max(1, Math.ceil(sorted.length / PER_PAGE))
  const current = Math.min(page, pages)
  const onPage = sorted.slice((current - 1) * PER_PAGE, current * PER_PAGE)
  const goTo = (n: number) => { setPage(n); setOpened(null) }
  const shownFlagged = shown.filter(isFlagged)
  const kinds = [...new Set(shownFlagged.map(kindOf))].map((kind) => { const of = shownFlagged.filter((r) => kindOf(r) === kind); return { kind, rows: of, tone: shownTone(of[0]) } })

  const count = (tone: Tone) => rows.filter((r) => toneKey(r) === tone).length
  // The figures of the top: what was read, and what became of it — the colours of the filters and the pills.
  const cards: { filter: Filter; title: string; value: number; note: string; text: string; border: string; icon: ReactNode }[] = [
    { filter: 'all', title: 'Rows read', value: rows.length, note: '100%', text: 'text-zinc-700 dark:text-zinc-300', border: 'border-blue-500', icon: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.300 7-3V6M5 12c0 1.700 3.100 3 7 3s7-1.300 7-3" /></> },
    { filter: 'ready', title: 'Ready', value: count('ready'), note: 'new visits', text: TONES.ready.text, border: 'border-emerald-500', icon: <><circle cx="12" cy="12" r="9" /><path d="M8 12.500l2.800 2.800L16 9.500" /></> },
    { filter: 'skipped', title: 'Skipped / Existing', value: count('skipped'), note: 'unchanged', text: TONES.skipped.text, border: 'border-amber-500', icon: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></> },
    { filter: 'errors', title: 'With problems', value: count('errors'), note: 'needs attention', text: TONES.errors.text, border: 'border-red-500', icon: <><circle cx="12" cy="12" r="9" /><path d="M12 7.500v5M12 16h.01" /></> },
  ]

  return (
    <div className="mt-4 mb-5">
      {/* the figures are the filters: the one pressed keeps those rows — pressed again, all of them */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5" role="group" aria-label="Filter the rows">
        {cards.map((c) => {
          const on = filter === c.filter
          return (
            <button key={c.title} type="button" aria-pressed={on} aria-label={c.title} onClick={() => setFilter(on ? 'all' : c.filter)}
                    className={`flex flex-col justify-between gap-3 rounded-2xl border px-5 py-4 text-left transition-colors ${on ? `${c.border} bg-zinc-50 dark:bg-zinc-900/60` : 'border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-500'}`}>
              <span className={`flex items-center gap-2 text-sm font-semibold ${c.text}`}>
                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{c.icon}</svg>{c.title}
              </span>
              <span className="flex items-end justify-between gap-3">
                <span className={`text-4xl font-bold leading-none ${c.value === 0 ? 'text-zinc-400 dark:text-zinc-500' : 'text-zinc-900 dark:text-zinc-100'}`}>{c.value.toLocaleString('en-US')}</span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">{c.note}</span>
              </span>
            </button>
          )
        })}
      </div>

      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex gap-1 rounded-xl border border-zinc-200 dark:border-zinc-700 p-1" role="tablist" aria-label="Rows by">
          <button type="button" role="tab" aria-selected={view === 'row'} className={viewClass(view === 'row')} onClick={() => setView('row')}>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h16M7 12h10M10 18h4" /></svg>By row
          </button>
          <button type="button" role="tab" aria-selected={view === 'error'} className={viewClass(view === 'error')} onClick={() => setView('error')}>
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l9 5-9 5-9-5 9-5z" /><path d="M3 13l9 5 9-5" /></svg>By reason / error
          </button>
        </div>
        <label className="relative block w-full sm:w-80">
          <span className="sr-only">Search the rows</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 fill-none stroke-current text-zinc-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.500-3.500" /></svg>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by row, site, visit, action…"
                 className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 py-2 pl-9 pr-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-blue-500" />
        </label>
      </div>

      {view === 'error' ? (
        <>
          {kinds.length === 0 ? <p className="text-sm text-zinc-600 dark:text-zinc-400">No row has errors.</p> : (
            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
              <table className="w-full text-sm" aria-label="Errors of the file">
                <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                  <tr>{['Error', 'Rows', ''].map((h, i) => <th key={i} scope="col" className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                  {kinds.map(({ kind, rows: of, tone }) => (
                    <tr key={kind} className={`align-top ${picked === kind ? TONES[tone].row : ''}`}>
                      <td className={`px-3 py-2 font-medium ${TONES[tone].text}`}>{kind}</td>
                      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{plural(of.length, 'row', 'rows')}</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">
                        <div className="flex justify-end">
                          <IconButton label={`${picked === kind ? 'Hide' : 'View'} the rows with ${kind}`} title={picked === kind ? 'Hide the rows with this error' : 'View the rows with this error'}
                                      expanded={picked === kind} onClick={() => setPicked(picked === kind ? null : kind)} path={ALERT_PATH} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {picked && (
            <div className="mt-3 overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
              <table className="w-full text-sm" aria-label={`Rows with ${picked}`}>
                <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                  <tr>{['Row', 'Revision', 'Site', 'What went wrong'].map((h) => <th key={h} scope="col" className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                  {shownFlagged.filter((r) => kindOf(r) === picked).map((r) => (
                    <tr key={r.row} className="align-top">
                      <td className="px-3 py-2 font-mono">{r.row}</td>
                      <td className="px-3 py-2 font-mono">{r.session || '—'}</td>
                      <td className="px-3 py-2 font-mono">{r.site || '—'}</td>
                      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{saidOf(r)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
          <table className="w-full text-sm" aria-label="Rows of the file">
            <thead className="bg-zinc-50 dark:bg-zinc-800/70 text-zinc-800 dark:text-zinc-200">
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.descending ? 'descending' : 'ascending') : 'none'} className={`px-4 py-3 text-left font-semibold ${c.key === 'actions' ? '' : 'w-px whitespace-nowrap'}`}>
                    <button type="button" aria-label={`Sort by ${c.label}`} className="flex items-center gap-1.5 font-semibold" onClick={() => setSort((now) => ({ key: c.key, descending: now.key === c.key && !now.descending }))}>
                      {c.label}
                      <svg aria-hidden="true" viewBox="0 0 24 24" className={`h-3.5 w-3.5 fill-none stroke-current ${sort.key === c.key ? 'text-blue-500' : 'text-zinc-400 dark:text-zinc-600'}`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        {sort.key === c.key ? (sort.descending ? <path d="M12 5v14M6 13l6 6 6-6" /> : <path d="M12 19V5M6 11l6-6 6 6" />) : <path d="M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4" />}
                      </svg>
                    </button>
                  </th>
                ))}
                <th scope="col" className="w-px px-4 py-3"><span className="sr-only">Options</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
              {onPage.map((r) => {
                const panel = opened?.row === r.row ? opened.panel : null
                const toggle = (which: 'contents' | 'errors') => setOpened(panel === which ? null : { row: r.row, panel: which })
                const name = `Row ${r.row}`
                return (
                  <Fragment key={r.row}>
                    <tr className="align-middle">
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">{r.row}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">{r.session || '—'}</td>
                      <td className="whitespace-nowrap px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">{r.site || '—'}</td>
                      <td className="px-4 py-3 text-zinc-700 dark:text-zinc-300">{r.actions || '—'}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-zinc-700 dark:text-zinc-300">{r.date ? <>{r.date}{r.time && <span className="text-zinc-500 dark:text-zinc-400"> {r.time}</span>}</> : '—'}</td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${toneOf(r)}`}>
                          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
                          {badgeOf(r)}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5" role="group" aria-label={`Options of ${name}`}>
                          <IconButton label={`View the contents of ${name}`} title="View what the row says" expanded={panel === 'contents'} onClick={() => toggle('contents')} path={ICON_PATHS.view} />
                          {isFlagged(r) && <IconButton label={`View the errors of ${name}`} title="View what is wrong with the row" expanded={panel === 'errors'} onClick={() => toggle('errors')} path={ALERT_PATH} />}
                        </div>
                      </td>
                    </tr>
                    {panel && (
                      <tr>
                        <td colSpan={COLUMNS.length + 1} className={panel === 'contents' ? 'bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4' : 'px-4 pb-4 pt-3'}>
                          {panel === 'errors' ? (
                            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
                              <table className="w-full text-sm" aria-label={`Problems of ${name}`}>
                                <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                                  <tr>{['Error', 'What went wrong'].map((h) => <th key={h} scope="col" className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                                  {/* a row that is not added says what is wrong; one that is, each thing to check in it */}
                                  {(warned(r) ? r.warnings! : [r.message]).map((message, i) => (
                                    <tr key={i} className="align-top">
                                      <td className={`px-3 py-2 font-medium ${TONES[shownTone(r)].text}`}>{kindOf(r)}</td>
                                      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{message}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <>
                              {r.result === 'ok' && r.message && <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">{r.message}</p>}
                              {Object.keys(r.data ?? {}).length > 0 ? (
                                <dl aria-label={`Contents of ${name}`} className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
                                  {Object.entries(r.data!).map(([field, value]) => (
                                    <div key={field} className="flex gap-2">
                                      <dt className="text-zinc-500 dark:text-zinc-400">{labels[field] ?? field}</dt>
                                      <dd className="font-mono text-xs break-all self-center">{value}</dd>
                                    </div>
                                  ))}
                                </dl>
                              ) : <p className="text-sm text-zinc-600 dark:text-zinc-400">The row has no contents.</p>}
                            </>
                          )}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
              {sorted.length === 0 && <tr><td colSpan={COLUMNS.length + 1} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No row matches.</td></tr>}
            </tbody>
          </table>
          {sorted.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 dark:border-zinc-700 px-4 py-3 text-sm">
              <span role="status" className="text-zinc-500 dark:text-zinc-400">Showing {(current - 1) * PER_PAGE + 1}–{Math.min(current * PER_PAGE, sorted.length)} of {sorted.length} rows</span>
              {pages > 1 && (
                <nav className="flex items-center gap-1" aria-label="Pages">
                  <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Previous page" disabled={current === 1} onClick={() => goTo(current - 1)}>‹</button>
                  {pageNumbers(current, pages).map((n, i) => n === null
                    ? <span key={`gap${i}`} className="px-1 text-zinc-400">…</span>
                    : <button key={n} type="button" aria-label={`Page ${n}`} aria-current={n === current ? 'page' : undefined} onClick={() => goTo(n)}
                              className={`px-2.5 py-1 rounded ${n === current ? 'bg-blue-600 text-white' : 'border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300'}`}>{n}</button>)}
                  <button type="button" className={`${btnOutline} !px-2.5 !py-1`} aria-label="Next page" disabled={current === pages} onClick={() => goTo(current + 1)}>›</button>
                </nav>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
