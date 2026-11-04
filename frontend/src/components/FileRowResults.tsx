import { Fragment, useState } from 'react'
import type { ReactNode } from 'react'
import { plural } from './SessionResults'

export interface FileRow {
  row: number
  site: string
  /** The revision the row says it is of, when it says. */
  session?: string
  result: 'ok' | 'problem' | 'already_kept' | 'new_site' | 'ignored'
  /** The kind of error — what the rows that share it have in common. Empty for a row that is fine. */
  label?: string
  message: string
}

/** What the pill of a row says, and its colours: ready to add, skipped (already kept, or ignored) or an error — the kind of it. */
const badgeOf = (r: FileRow) => (r.result === 'ok' ? 'Add' : r.result === 'already_kept' ? 'Skipped / Existing' : r.result === 'ignored' ? 'Skipped / Ignored' : kindOf(r))
/** One colour for each thing a row can be, the same in the figures, the filters, the pills and the tables: ready is green, skipped (already kept, ignored) is amber and an error is red. */
type Tone = 'ready' | 'skipped' | 'errors'
const toneKey = (r: FileRow): Tone => (r.result === 'ok' ? 'ready' : r.result === 'already_kept' || r.result === 'ignored' ? 'skipped' : 'errors')
const TONES: Record<Tone, { text: string; pill: string; chip: string; row: string }> = {
  ready: { text: 'text-emerald-700 dark:text-emerald-400', pill: 'border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300',
           chip: 'bg-emerald-600 text-white', row: 'bg-emerald-50 dark:bg-emerald-950/30' },
  skipped: { text: 'text-amber-700 dark:text-amber-400', pill: 'border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300',
             chip: 'bg-amber-500 text-white', row: 'bg-amber-50 dark:bg-amber-950/30' },
  errors: { text: 'text-red-700 dark:text-red-400', pill: 'border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300',
            chip: 'bg-red-600 text-white', row: 'bg-red-50 dark:bg-red-950/30' },
}
const toneOf = (r: FileRow) => TONES[toneKey(r)].pill
const kindOf = (r: FileRow) => r.label || 'Problem'

type SortKey = 'row' | 'site' | 'visit' | 'status'
const COLUMNS: { key: SortKey; label: string }[] = [
  { key: 'row', label: 'Row' }, { key: 'site', label: 'Site ID' }, { key: 'visit', label: 'Visit' }, { key: 'status', label: 'Status' },
]

type Filter = 'all' | 'ready' | 'skipped' | 'errors'
/** What a filter keeps: the rows to add (ready), those left out because they are already kept or ignored (skipped), and those with a problem or a site that is not a location (errors). */
const FILTERS: { value: Filter; label: string; tone: Tone | null; keeps: (r: FileRow) => boolean }[] = [
  { value: 'all', label: 'All', tone: null, keeps: () => true },
  { value: 'ready', label: 'Add', tone: 'ready', keeps: (r) => toneKey(r) === 'ready' },
  { value: 'skipped', label: 'Skipped', tone: 'skipped', keeps: (r) => toneKey(r) === 'skipped' },
  { value: 'errors', label: 'Errors', tone: 'errors', keeps: (r) => toneKey(r) === 'errors' },
]

const viewClass = (active: boolean) => `flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium ${active ? 'bg-blue-600 text-white' : 'text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`
const chipClass = (active: boolean, tone: Tone | null) => `rounded-lg px-3 py-1.5 text-sm font-medium ${active ? (tone ? TONES[tone].chip : 'bg-zinc-700 text-white dark:bg-zinc-600') : `bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 ${tone ? TONES[tone].text : 'text-zinc-700 dark:text-zinc-300'}`}`

/** What became of each row of a file that is read, laid out like the results of the checks of the deployments: the figures, and the rows — each with what
 * went wrong in it — or, by error, each kind of error with the rows that have it, to pick one and see them. */
export default function FileRowResults({ rows }: { rows: FileRow[] }) {
  const [view, setView] = useState<'row' | 'error'>('row')
  const [filter, setFilter] = useState<Filter>('all')
  const flagged = rows.filter((r) => r.result !== 'ok')
  const [opened, setOpened] = useState<number | null>(flagged[0]?.row ?? null)
  const [picked, setPicked] = useState<string | null>(null)
  const [sort, setSort] = useState<{ key: SortKey; descending: boolean }>({ key: 'row', descending: false })

  const keeps = FILTERS.find((f) => f.value === filter)!.keeps
  const shown = rows.filter(keeps)
  const sortValue = (r: FileRow, key: SortKey) => (key === 'row' ? r.row : key === 'site' ? r.site.toLowerCase() : key === 'visit' ? r.session ?? '' : badgeOf(r))
  const sorted = [...shown].sort((a, b) => {
    const x = sortValue(a, sort.key), y = sortValue(b, sort.key)
    const order = typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))
    return (sort.descending ? -order : order) || a.row - b.row
  })
  const shownFlagged = shown.filter((r) => r.result !== 'ok')
  const kinds = [...new Set(shownFlagged.map(kindOf))].map((kind) => { const of = shownFlagged.filter((r) => kindOf(r) === kind); return { kind, rows: of, tone: toneKey(of[0]) } })

  const count = (tone: Tone) => rows.filter((r) => toneKey(r) === tone).length
  // The figures of the top: what was read, and what became of it — the colours of the filters and the pills.
  const cards: { title: string; value: number; note: string; text: string; icon: ReactNode }[] = [
    { title: 'Rows read', value: rows.length, note: '100%', text: 'text-zinc-700 dark:text-zinc-300', icon: <><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v12c0 1.7 3.1 3 7 3s7-1.300 7-3V6M5 12c0 1.700 3.100 3 7 3s7-1.300 7-3" /></> },
    { title: 'Ready', value: count('ready'), note: 'new visits', text: TONES.ready.text, icon: <><circle cx="12" cy="12" r="9" /><path d="M8 12.500l2.800 2.800L16 9.500" /></> },
    { title: 'Skipped / Existing', value: count('skipped'), note: 'unchanged', text: TONES.skipped.text, icon: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></> },
    { title: 'With problems', value: count('errors'), note: 'needs attention', text: TONES.errors.text, icon: <><circle cx="12" cy="12" r="9" /><path d="M12 7.500v5M12 16h.01" /></> },
  ]

  return (
    <div className="mt-4 mb-5">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5" aria-label="Summary of the rows">
        {cards.map((c) => (
          <div key={c.title} role="group" aria-label={c.title} className="flex flex-col justify-between gap-3 rounded-2xl border border-zinc-200 dark:border-zinc-700 px-5 py-4">
            <p className={`flex items-center gap-2 text-sm font-semibold ${c.text}`}>
              <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{c.icon}</svg>{c.title}
            </p>
            <div className="flex items-end justify-between gap-3">
              <p className={`text-4xl font-bold leading-none ${c.value === 0 ? 'text-zinc-400 dark:text-zinc-500' : 'text-zinc-900 dark:text-zinc-100'}`}>{c.value.toLocaleString('en-US')}</p>
              <p className="text-sm text-zinc-500 dark:text-zinc-400">{c.note}</p>
            </div>
          </div>
        ))}
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
        <div className="flex items-center gap-2 flex-wrap" role="group" aria-label="Filter the rows">
          <span className="flex items-center gap-1.5 text-sm text-zinc-500 dark:text-zinc-400">
            <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 5h18l-7 8v6l-4-2v-4z" /></svg>Filter:
          </span>
          {FILTERS.map((f) => (
            <button key={f.value} type="button" aria-pressed={filter === f.value} className={chipClass(filter === f.value, f.tone)} onClick={() => setFilter(f.value)}>
              {f.label} ({rows.filter(f.keeps).length})
            </button>
          ))}
        </div>
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
                        <button type="button" aria-pressed={picked === kind} aria-label={`${picked === kind ? 'Hide' : 'View'} the rows with ${kind}`}
                                className="text-blue-600 dark:text-blue-400 hover:underline" onClick={() => setPicked(picked === kind ? null : kind)}>
                          {picked === kind ? 'Hide the rows' : 'View the rows'}
                        </button>
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
                      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{r.message}</td>
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
                  <th key={c.key} scope="col" aria-sort={sort.key === c.key ? (sort.descending ? 'descending' : 'ascending') : 'none'} className="px-4 py-3 text-left font-semibold">
                    <button type="button" aria-label={`Sort by ${c.label}`} className="flex items-center gap-1.5 font-semibold" onClick={() => setSort((now) => ({ key: c.key, descending: now.key === c.key && !now.descending }))}>
                      {c.label}
                      <svg aria-hidden="true" viewBox="0 0 24 24" className={`h-3.5 w-3.5 fill-none stroke-current ${sort.key === c.key ? 'text-blue-500' : 'text-zinc-400 dark:text-zinc-600'}`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        {sort.key === c.key ? (sort.descending ? <path d="M12 5v14M6 13l6 6 6-6" /> : <path d="M12 19V5M6 11l6-6 6 6" />) : <path d="M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4" />}
                      </svg>
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
              {sorted.map((r) => {
                const open = opened === r.row
                const name = `Row ${r.row}`
                return (
                  <Fragment key={r.row}>
                    <tr className="align-middle">
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2">
                          <button type="button" aria-expanded={open} aria-label={`${open ? 'Close' : 'Open'} ${name}`} onClick={() => setOpened(open ? null : r.row)} className="inline-flex rounded p-1 text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100">
                            <svg aria-hidden="true" viewBox="0 0 24 24" className={`h-4 w-4 fill-none stroke-current transition-transform ${open ? 'rotate-90' : ''}`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6" /></svg>
                          </button>
                          <span className="font-semibold text-zinc-900 dark:text-zinc-100">{r.row}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">{r.site ? <span className="rounded-md border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900 px-2.5 py-1 font-mono text-xs text-zinc-700 dark:text-zinc-300">{r.site}</span> : '—'}</td>
                      <td className="px-4 py-3 font-semibold text-zinc-900 dark:text-zinc-100">{r.session || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${toneOf(r)}`}>
                          <svg aria-hidden="true" viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></svg>
                          {badgeOf(r)}
                        </span>
                      </td>
                    </tr>
                    {open && (
                      <tr>
                        <td colSpan={COLUMNS.length} className="px-4 pb-4 pt-0">
                          {r.result !== 'ok' ? (
                            <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
                              <table className="w-full text-sm" aria-label={`Problems of ${name}`}>
                                <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                                  <tr>{['Error', 'What went wrong'].map((h) => <th key={h} scope="col" className="px-3 py-2 text-left font-medium">{h}</th>)}</tr>
                                </thead>
                                <tbody>
                                  <tr className="align-top">
                                    <td className={`px-3 py-2 font-medium ${TONES[toneKey(r)].text}`}>{kindOf(r)}</td>
                                    <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{r.message}</td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          ) : <p className="text-sm text-zinc-600 dark:text-zinc-400">{r.message || 'The visit of this row will be added.'}</p>}
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
              {sorted.length === 0 && <tr><td colSpan={COLUMNS.length} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">No row matches.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
