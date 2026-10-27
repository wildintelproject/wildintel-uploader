import { useEffect, useState } from 'react'
import { api } from '../api'
import ReportPanel from './ReportPanel'
import type { ReportKind, ReportSummary } from '../types'

const KIND_LABELS: Record<ReportKind, string> = { validation: 'Validation', postvalidation: 'Postvalidation', preprocessing: 'Preprocessing', repair: 'Repair', upload: 'Upload' }
const KIND_TONES: Record<ReportKind, string> = {
  validation: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  postvalidation: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
  preprocessing: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  repair: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  upload: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300',
}
const PAGE = 6

const formatDate = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

const pill = 'px-3 py-1 text-xs rounded-full border transition-colors'
const rowBtn = 'px-3 h-9 inline-flex items-center gap-1 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors no-underline cursor-pointer'

/** The reports the validations, postvalidations, preprocessings and repairs left: to look at again, download or delete. */
export default function ReportsList() {
  const [reports, setReports] = useState<ReportSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [kind, setKind] = useState<ReportKind | 'all'>('all')
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(PAGE)

  useEffect(() => {
    api.listReports().then(setReports).catch((e) => setError(e instanceof Error ? e.message : 'Could not read the reports.'))
  }, [])

  async function handleDelete(id: string) {
    try {
      await api.deleteReport(id)
      setReports((list) => (list ?? []).filter((r) => r.id !== id))
      if (open === id) setOpen(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the report.')
    } finally {
      setConfirming(null)
    }
  }

  const all = reports ?? []
  const needle = query.trim().toLowerCase()
  const matching = all.filter((r) => (kind === 'all' || r.kind === kind)
    && (!needle || [r.title, r.source_dir ?? '', r.deployment_id ?? '', formatDate(r.created_at)].some((t) => t.toLowerCase().includes(needle))))
  const visible = matching.slice(0, shown)
  const count = (k: ReportKind) => all.filter((r) => r.kind === k).length

  return (
    <div className="py-3 space-y-5">
      <p className="text-zinc-500 dark:text-zinc-400 text-sm leading-relaxed max-w-prose">
        Every check, preparation, repair and upload leaves a report of what was checked and done, image by image, or deployment by deployment for an upload.
        Open one again, download it, or delete the ones you no longer need.
      </p>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {reports === null && !error && <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the reports…</p>}
      {reports?.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">There are no reports yet — they are made when you validate or import images.</p>}
      {all.length > 0 && (
        <>
          <div role="group" aria-label="Kind of report" className="flex flex-wrap gap-2">
            {(['all', ...Object.keys(KIND_LABELS)] as (ReportKind | 'all')[]).map((k) => (
              <button key={k} type="button" aria-pressed={kind === k} onClick={() => { setKind(k); setShown(PAGE) }}
                      className={`${pill} ${kind === k ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300' : 'border-zinc-300 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>
                {k === 'all' ? 'All' : KIND_LABELS[k]} <span className="opacity-70">{k === 'all' ? all.length : count(k)}</span>
              </button>
            ))}
          </div>
          <input type="search" aria-label="Search by deployment or date" placeholder="Search by deployment or date" value={query} onChange={(e) => { setQuery(e.target.value); setShown(PAGE) }}
                 className="w-full h-11 px-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 text-sm" />
        </>
      )}
      {all.length > 0 && matching.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No report matches.</p>}
      <ul className="space-y-3">
        {visible.map((r) => (
          <li key={r.id} className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-5 py-4" aria-label={r.title}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  <span className={`mr-2 text-xs font-medium px-1.5 py-0.5 rounded ${KIND_TONES[r.kind]}`}>{KIND_LABELS[r.kind]}</span>{r.title}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                  {formatDate(r.created_at)} · {r.checked} {r.kind === 'upload' ? 'deployment(s)' : 'image(s)'} · {r.totals.failed === 0 ? 'nothing failed' : <span className="text-amber-600 dark:text-amber-400 font-medium">{r.totals.failed} problem(s)</span>}
                </p>
                {r.source_dir && <p className="text-xs text-zinc-400 dark:text-zinc-500 font-mono break-all mt-1">{r.source_dir}</p>}
              </div>
              <div className="flex gap-2 items-center">
                <button type="button" className={rowBtn} aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)}>{open === r.id ? 'Hide' : 'View'}</button>
                <details className="relative">
                  <summary className={`${rowBtn} list-none`}>Download <span aria-hidden="true">▾</span></summary>
                  <div className="absolute right-0 z-10 mt-1 w-28 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-lg p-1 flex flex-col">
                    <a className="px-3 py-1.5 text-sm rounded no-underline text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800" href={api.reportUrl(r.id, 'csv')} download>CSV</a>
                    <a className="px-3 py-1.5 text-sm rounded no-underline text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800" href={api.reportUrl(r.id, 'json')} download>JSON</a>
                  </div>
                </details>
                {confirming === r.id
                  ? <button type="button" className="px-3 h-9 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700" onClick={() => handleDelete(r.id)}>Delete it</button>
                  : (
                    <button type="button" aria-label="Delete" title="Delete the report" className="w-9 h-9 flex items-center justify-center rounded-lg border border-zinc-300 dark:border-zinc-600 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30" onClick={() => setConfirming(r.id)}>
                      <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6M14 11v6" /><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" /></svg>
                    </button>
                  )}
              </div>
            </div>
            {open === r.id && <ReportPanel reportId={r.id} />}
          </li>
        ))}
      </ul>
      {matching.length > visible.length && (
        <div className="flex justify-center">
          <button type="button" className={rowBtn} onClick={() => setShown((n) => n + PAGE)}>Show {matching.length - visible.length} more</button>
        </div>
      )}
    </div>
  )
}
