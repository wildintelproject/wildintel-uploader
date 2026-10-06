import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { Report } from '../types'
import CheckFailures from './CheckFailures'
import { SmallSpinner, btnOutline, btnPrimary } from '../pages/ImportDeploymentPage'

export interface DashboardContext {
  report: Report | null
  /** The check whose failures are open, if any. */
  openCheck: string | null
  open: (check: string) => void
}

const formatRun = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function Kpi({ icon, tone, value, label }: { icon: string; tone: string; value: number | string; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-zinc-200 dark:border-zinc-700 p-3">
      <span aria-hidden="true" className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg ${tone}`}>{icon}</span>
      <div>
        <p className="text-xl font-bold leading-tight text-zinc-900 dark:text-zinc-100">{typeof value === 'number' ? value.toLocaleString() : value}</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{label}</p>
      </div>
    </div>
  )
}

/** The validation as a dashboard: what it was run on and when, how many images are fine, the checks with how each ended — and,
 * opened from one, the images that failed it. The table of checks is the page's (it has the choosing of them): it goes in `children`. */
export default function ValidationDashboard({ title, subtitle, reportId, running, canRun, onRun, runLabel = 'Run validation', runningLabel = 'Validating…', children }: {
  title: string
  subtitle: string
  /** The report of the last run, once there is one. */
  reportId: string | null
  running: boolean
  canRun: boolean
  onRun: () => void
  runLabel?: string
  runningLabel?: string
  children: (context: DashboardContext) => ReactNode
}) {
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [openCheck, setOpenCheck] = useState<string | null>(null)

  useEffect(() => {
    setOpenCheck(null)
    if (!reportId) { setReport(null); setError(null); return }
    let cancelled = false
    api.getReport(reportId)
      .then((r) => { if (!cancelled) { setReport(r); setError(null) } })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the report.') })
    return () => { cancelled = true }
  }, [reportId])

  const checks = report ? Object.values(report.checks) : []
  const withIssues = report?.totals.images_with_issues ?? 0
  const shown = report && !running ? report : null

  return (
    <div>
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40 text-xl">🛡️</span>
          <div>
            <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h5>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 break-all">{subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {report && <span className="text-xs text-zinc-500 dark:text-zinc-400">Last run: {formatRun(report.created_at)}</span>}
          {report && (
            <span className="flex gap-2 text-xs">
              <a className="text-blue-600 dark:text-blue-400 hover:underline" href={api.reportUrl(report.id, 'csv')} download>Download CSV</a>
              <a className="text-blue-600 dark:text-blue-400 hover:underline" href={api.reportUrl(report.id, 'json')} download>Download JSON</a>
            </span>
          )}
          <button type="button" className={`${report ? btnOutline : btnPrimary} flex items-center gap-2`} disabled={running || !canRun} onClick={onRun}>
            {running && <SmallSpinner />}{running ? runningLabel : runLabel}
          </button>
        </div>
      </div>

      {shown && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4" aria-label="Summary">
          <Kpi icon="✔" tone="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400" value={Math.max(0, shown.checked - withIssues)} label="Valid images" />
          <Kpi icon="⚠" tone="bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400" value={withIssues} label="Images with issues" />
          <Kpi icon="🧪" tone="bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400" value={checks.length} label="Tests executed" />
          <Kpi icon="❗" tone="bg-violet-100 dark:bg-violet-900/40 text-violet-600 dark:text-violet-400" value={checks.filter((c) => c.failed > 0).length} label="Tests with errors" />
        </div>
      )}
      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}

      {children({ report: shown, openCheck, open: (check) => setOpenCheck((current) => (current === check ? null : check)) })}

      {shown && openCheck && shown.checks[openCheck] && <CheckFailures report={shown} check={openCheck} onBack={() => setOpenCheck(null)} />}
    </div>
  )
}
