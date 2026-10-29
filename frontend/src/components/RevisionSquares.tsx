/** How many of the revisions are shown as squares: the most recent ones; the older are picked from a list on the right. */
export const SHOWN_REVISIONS = 5

export interface RevisionSquare { id: string; label: string; note: string }

/** A square for all the revisions and one for each of the five most recent — `revisions` newest first —, with a list on the right for the older ones.
 * The value is the id of the one picked, '' for all of them. */
export default function RevisionSquares({ all, revisions, value, onPick, label = 'Revision' }: {
  all: Omit<RevisionSquare, 'id'>; revisions: RevisionSquare[]; value: string; onPick: (id: string) => void; label?: string
}) {
  const recent = revisions.slice(0, SHOWN_REVISIONS), older = revisions.slice(SHOWN_REVISIONS)
  const square = 'rounded-xl border px-5 py-3 text-left transition-colors'
  const pressed = 'border-blue-500 bg-blue-50 dark:bg-blue-950/40'
  const idle = 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'
  const picked = older.find((r) => r.id === value)
  return (
    <div className="flex flex-wrap items-stretch gap-3" role="group" aria-label={label}>
      {[{ id: '', ...all }, ...recent].map((r) => (
        <button key={r.id || 'all'} type="button" aria-pressed={value === r.id} onClick={() => onPick(r.id)} className={`${square} ${value === r.id ? pressed : idle}`}>
          <span className="block font-mono text-lg font-semibold">{r.label}</span>
          <span className="block text-sm text-zinc-500 dark:text-zinc-400">{r.note}</span>
        </button>
      ))}
      {older.length > 0 && (
        <div className={`ml-auto flex flex-col justify-center rounded-xl border px-4 py-3 ${picked ? pressed : 'border-zinc-200 dark:border-zinc-700'}`}>
          <label htmlFor="older-revisions" className="text-sm text-zinc-500 dark:text-zinc-400 mb-1">Older revisions</label>
          <select id="older-revisions" value={picked ? picked.id : ''} onChange={(e) => e.target.value && onPick(e.target.value)}
                  className="rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-900 px-3 py-1.5 font-mono text-sm text-zinc-900 dark:text-zinc-100">
            <option value="">Pick one…</option>
            {older.map((r) => <option key={r.id} value={r.id}>{r.label} — {r.note}</option>)}
          </select>
        </div>
      )}
    </div>
  )
}
