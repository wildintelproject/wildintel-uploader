import type { ReactNode } from 'react'

/** The colour of a fix, and of the chip that names what it is about. */
export type FixTone = 'blue' | 'amber'

/** One repair offered beside the checks: what it is about, what it would change, and the button that does it. */
export interface Fix {
  key: string
  tone: FixTone
  /** What it is about — "Camera 43 · Metadata" —, then how it is done — "1-click fix", "Needs review". */
  subject: string
  kind: string
  title: string
  description: ReactNode
  /** What is and what would be: "Make: empty → RECONYX"; with no `before`, only what is. */
  changes: { label: string; before?: string | null; after: string }[]
  action: ReactNode
  /** Said under it once it was done, or why it could not be. */
  outcome?: ReactNode
}

const BORDER: Record<FixTone, string> = {
  blue: 'border-blue-300 dark:border-blue-900 before:bg-blue-500',
  amber: 'border-amber-300 dark:border-amber-900 before:bg-amber-500',
}
const SUBJECT: Record<FixTone, string> = {
  blue: 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-300',
  amber: 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300',
}
const AFTER: Record<FixTone, string> = { blue: 'text-blue-700 dark:text-blue-300', amber: 'text-amber-700 dark:text-amber-300' }
const chip = 'inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide'

/** The button that opens the fixes: how many there are, pressed while they are shown. */
export function FixesBadge({ count, open, onToggle }: { count: number; open: boolean; onToggle: () => void }) {
  return (
    <button type="button" aria-expanded={open} aria-controls="available-fixes" onClick={onToggle}
            className={`${chip} shrink-0 cursor-pointer border-amber-400 bg-amber-100 text-amber-800 hover:bg-amber-200 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-300 dark:hover:bg-amber-900/70`}>
      {count} {count === 1 ? 'fix' : 'fixes'} available
    </button>
  )
}

function FixCard({ fix }: { fix: Fix }) {
  return (
    <article aria-label={fix.title}
             className={`relative overflow-hidden rounded-xl border bg-white p-4 pl-5 dark:bg-zinc-900 before:absolute before:inset-y-0 before:left-0 before:w-1 ${BORDER[fix.tone]}`}>
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap gap-2">
            <span className={`${chip} ${SUBJECT[fix.tone]}`}>{fix.subject}</span>
            <span className={`${chip} border-zinc-300 bg-zinc-100 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400`}>{fix.kind}</span>
          </div>
          <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{fix.title}</h5>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{fix.description}</p>
          {fix.changes.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {fix.changes.map((c) => (
                <li key={c.label} className="rounded-md border border-zinc-200 bg-zinc-50 px-2.5 py-1.5 font-mono text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400">
                  {c.label}:{' '}
                  {c.before !== undefined && <><span className={c.before ? '' : 'line-through'}>{c.before || 'empty'}</span> → </>}
                  <span className={`font-semibold ${c.before !== undefined ? AFTER[fix.tone] : 'text-zinc-900 dark:text-zinc-100'}`}>{c.after}</span>
                </li>
              ))}
            </ul>
          )}
          {fix.outcome}
        </div>
        <div className="shrink-0">{fix.action}</div>
      </div>
    </article>
  )
}

/** The repairs offered beside the checks, apart from them: each one a card with what it would change and its button. */
export default function AvailableFixes({ fixes, open }: { fixes: Fix[]; open: boolean }) {
  if (fixes.length === 0 || !open) return null
  return (
    <section id="available-fixes" aria-label="Available fixes" className="mb-4 space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Available fixes ({fixes.length})</h4>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">Repairs, apart from the checks · run the checks again after one</p>
      </div>
      {fixes.map((f) => <FixCard key={f.key} fix={f} />)}
    </section>
  )
}
