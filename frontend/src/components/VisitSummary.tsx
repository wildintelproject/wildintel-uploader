import { useState } from 'react'
import type { ReactNode } from 'react'
import { Icon } from './Dashboard'

/** How a value is shown: plain, as code, or as a pill that is good (green), bad (red) or neutral. */
export type SummaryTone = 'plain' | 'code' | 'good' | 'bad' | 'neutral'
export interface SummaryRow { label: string; value: string; tone?: SummaryTone }
export interface SummarySection { key: string; title: string; icon: ReactNode; optional?: boolean; rows: SummaryRow[] }
export interface VisitSummaryData {
  /** What the visit is, that the sections do not say: where, which revision, when, who and what was done. */
  overview: SummaryRow[]
  /** The GPS of the note, with a button to copy it. */
  gps: string
  /** The sections of the form, as they are kept in it. */
  sections: SummarySection[]
}

const CARD = 'rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60'
const PILL = 'inline-flex items-center rounded-md border px-2 py-0.5 text-sm font-medium'
const TONE: Record<SummaryTone, string> = {
  plain: 'font-semibold text-zinc-900 dark:text-zinc-100',
  code: `${PILL} font-mono border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200`,
  good: `${PILL} border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300`,
  bad: `${PILL} border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300`,
  neutral: `${PILL} border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200`,
}
const OVERVIEW_ICON = <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4h6v2H9z" /><path d="M9 13l2 2 4-4" /></>

function Values({ rows }: { rows: SummaryRow[] }) {
  return (
    <>
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline justify-between gap-4 text-sm">
          <span className="text-zinc-500 dark:text-zinc-400">{r.label}</span>
          <span className={`text-right break-words min-w-0 ${TONE[r.tone ?? 'plain']}`}>{r.value}</span>
        </div>
      ))}
    </>
  )
}

/** What a visit says before it is kept, as cards: the overview across the page and the sections of the form below it. */
export default function VisitSummary({ data }: { data: VisitSummaryData }) {
  const [copied, setCopied] = useState(false)
  const copyGps = async () => {
    try {
      await navigator.clipboard.writeText(data.gps)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* the browser did not allow it: nothing is copied */ }
  }
  return (
    <div className="mb-4 space-y-3" role="group" aria-label="The visit">
      <section className={`${CARD} px-6 py-5`} aria-label="Visit overview">
        <div className="flex items-center gap-3 border-b border-zinc-200 dark:border-zinc-800 pb-4">
          <span className="text-blue-600 dark:text-blue-400"><Icon path={OVERVIEW_ICON} className="h-6 w-6" /></span>
          <h5 className="flex-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">Visit overview</h5>
          {data.gps && (
            <button type="button" className="px-3 py-1.5 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => void copyGps()}>
              {copied ? 'Copied' : 'Copy GPS'}
            </button>
          )}
        </div>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-3">
          <Values rows={[...data.overview, ...(data.gps ? [{ label: 'GPS of the note', value: data.gps, tone: 'code' as const }] : [])]} />
        </div>
      </section>
      {data.sections.map((section) => (
        <section key={section.key} className={`${CARD} px-5 py-4`} aria-label={section.title}>
          <div className="flex items-center gap-3">
            <span className="text-blue-600 dark:text-blue-400"><Icon path={section.icon} className="h-5 w-5" /></span>
            <h5 className="flex-1 text-base font-semibold text-zinc-900 dark:text-zinc-100">
              {section.title}{section.optional && <span className="ml-2 text-xs font-normal text-zinc-500 dark:text-zinc-400">optional</span>}
            </h5>
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${section.rows.length > 0 ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-400' : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300'}`}>
              {section.rows.length > 0 ? `${section.rows.length} filled` : 'Nothing filled in'}
            </span>
          </div>
          {section.rows.length > 0 && (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-x-10 gap-y-2.5 border-t border-zinc-200 dark:border-zinc-800 pt-3">
              <Values rows={section.rows} />
            </div>
          )}
        </section>
      ))}
    </div>
  )
}
