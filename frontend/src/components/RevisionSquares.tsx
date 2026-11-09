import type { ReactNode } from 'react'

/** How many of the revisions are shown as squares: the most recent ones; the older are picked from a list on the right. */
export const SHOWN_REVISIONS = 5

export interface RevisionSquare {
  id: string; label: string; note: string
  /** Optional: the days the revision went from and to, at the right of its name. */
  dates?: string
  /** Optional: every visit of the revision is done — a tick beside its note. */
  complete?: boolean
  /** Optional, of the square for all the revisions: how much of them is done, in a badge beside its note. */
  percent?: number
}

/** A square for all the revisions and one for each of the five most recent — `revisions` newest first —, with a list on the right for the older ones.
 * The value is the id of the one picked, '' for all of them. */
export default function RevisionSquares({ all, revisions, value, onPick, label = 'Revision', description }: {
  all: Omit<RevisionSquare, 'id'>; revisions: RevisionSquare[]; value: string; onPick: (id: string) => void; label?: string
  /** What a revision is, above the squares: given, the list of the older ones goes at its height, at the right, not beside the squares. */
  description?: ReactNode
}) {
  const recent = revisions.slice(0, SHOWN_REVISIONS), older = revisions.slice(SHOWN_REVISIONS)
  const square = 'group rounded-xl border p-3.5 text-left transition-all duration-200'
  const pressed = 'border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-md shadow-blue-500/10 ring-1 ring-blue-500/50'
  const idle = 'border-zinc-200 dark:border-zinc-700 bg-zinc-50/60 dark:bg-zinc-800/40 hover:bg-zinc-100 dark:hover:bg-zinc-800/80 hover:border-zinc-300 dark:hover:border-zinc-600'
  const picked = older.find((r) => r.id === value)
  const select = (
    <select id="older-revisions" value={picked ? picked.id : ''} onChange={(e) => e.target.value && onPick(e.target.value)}
            className="rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-1.5 font-mono text-sm text-zinc-900 dark:text-zinc-100">
      <option value="">Pick one…</option>
      {older.map((r) => <option key={r.id} value={r.id}>{r.label} — {r.note}{r.dates ? ` (${r.dates})` : ''}</option>)}
    </select>
  )
  const body = (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6" role="group" aria-label={label}>
      {[{ id: '', ...all }, ...recent].map((r) => (
        <button key={r.id || 'all'} type="button" aria-pressed={value === r.id} onClick={() => onPick(r.id)} className={`${square} ${value === r.id ? pressed : idle}`}>
          {r.id === '' ? (
            <>
              <span className="flex items-center justify-between">
                <span className={`text-xs font-semibold uppercase tracking-wider ${value === r.id ? 'text-blue-700 dark:text-blue-300' : 'text-zinc-700 dark:text-zinc-300'}`}>{r.label}</span>
                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current text-blue-600 dark:text-blue-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2l10 5-10 5L2 7z" /><path d="M2 12l10 5 10-5" /><path d="M2 17l10 5 10-5" /></svg>
              </span>
              <span className="mt-2 flex items-baseline justify-between gap-2">
                <span className="text-sm font-bold tracking-tight text-zinc-900 dark:text-white">{r.note}</span>
                {r.percent !== undefined && <span className="rounded border border-emerald-500/20 bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">{r.percent}%</span>}
              </span>
            </>
          ) : (
            <>
              <span className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 group-hover:text-zinc-900 dark:group-hover:text-white">{r.label}</span>
                {'dates' in r && r.dates && <span className="font-mono text-[10px] text-zinc-500 dark:text-zinc-400">{r.dates}</span>}
              </span>
              <span className="mt-2 flex items-baseline justify-between gap-2">
                <span className="text-sm font-bold text-zinc-800 dark:text-zinc-200">{r.note}</span>
                {r.complete && <svg role="img" aria-label="Complete" viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0 fill-none stroke-current text-emerald-600 dark:text-emerald-400" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><path d="M8 12l3 3 5-6" /></svg>}
              </span>
            </>
          )}
        </button>
      ))}
      {description === undefined && older.length > 0 && (
        <div className={`ml-auto flex flex-col justify-center rounded-xl border px-4 py-3 ${picked ? pressed : 'border-zinc-200 dark:border-zinc-700'}`}>
          <label htmlFor="older-revisions" className="text-sm text-zinc-500 dark:text-zinc-400 mb-1">Older revisions</label>
          {select}
        </div>
      )}
    </div>
  )
  if (description === undefined) return body
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">{description}</p>
        {older.length > 0 && (
          <div className={`flex items-center gap-2 rounded-xl border px-3 py-1.5 ${picked ? pressed : 'border-zinc-200 dark:border-zinc-700'}`}>
            <label htmlFor="older-revisions" className="text-sm text-zinc-500 dark:text-zinc-400">Older revisions</label>
            {select}
          </div>
        )}
      </div>
      {body}
    </div>
  )
}
