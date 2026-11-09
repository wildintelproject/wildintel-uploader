import type { ReactNode } from 'react'

/** How many of the revisions are shown as squares: the most recent ones; the older are picked from a list on the right. */
export const SHOWN_REVISIONS = 5

export interface RevisionSquare { id: string; label: string; note: string; /** Optional: the days the revision went from and to, a line below the note. */ dates?: string }

/** A square for all the revisions and one for each of the five most recent — `revisions` newest first —, with a list on the right for the older ones.
 * The value is the id of the one picked, '' for all of them. */
export default function RevisionSquares({ all, revisions, value, onPick, label = 'Revision', description }: {
  all: Omit<RevisionSquare, 'id'>; revisions: RevisionSquare[]; value: string; onPick: (id: string) => void; label?: string
  /** What a revision is, above the squares: given, the list of the older ones goes at its height, at the right, not beside the squares. */
  description?: ReactNode
}) {
  const recent = revisions.slice(0, SHOWN_REVISIONS), older = revisions.slice(SHOWN_REVISIONS)
  const square = 'rounded-xl border px-5 py-3 text-left transition-colors'
  const pressed = 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
  const idle = 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'
  const picked = older.find((r) => r.id === value)
  const select = (
    <select id="older-revisions" value={picked ? picked.id : ''} onChange={(e) => e.target.value && onPick(e.target.value)}
            className="rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-1.5 font-mono text-sm text-zinc-900 dark:text-zinc-100">
      <option value="">Pick one…</option>
      {older.map((r) => <option key={r.id} value={r.id}>{r.label} — {r.note}{r.dates ? ` (${r.dates})` : ''}</option>)}
    </select>
  )
  const body = (
    <div className="flex flex-wrap items-stretch gap-3" role="group" aria-label={label}>
      {[{ id: '', ...all }, ...recent].map((r) => (
        <button key={r.id || 'all'} type="button" aria-pressed={value === r.id} onClick={() => onPick(r.id)} className={`${square} ${value === r.id ? pressed : idle}`}>
          <span className="block font-mono text-lg font-semibold">{r.label}</span>
          <span className="block text-sm text-zinc-500 dark:text-zinc-400">{r.note}</span>
          {'dates' in r && r.dates && <span className="block font-mono text-xs text-zinc-500 dark:text-zinc-400">{r.dates}</span>}
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
