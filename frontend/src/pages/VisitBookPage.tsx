import { useEffect, useState } from 'react'
import { api } from '../api'
import FieldDeployments from '../components/FieldDeployments'
import ResearchProjectPicker from '../components/ResearchProjectPicker'
import Notice from '../components/Notice'
import type { FieldDeployment, FieldLogsResult, LocalResearchProject, StoredVisit } from '../types'
import { btnOutline, inputClass } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
}

type View = 'visits' | 'deployments'

/** The visit book of a research project: the visits kept to it, and the deployments they say — closed, and the ones whose camera is still out — with the logs of their collections. */
export default function VisitBookPage({ onBack }: Props) {
  const [project, setProject] = useState<LocalResearchProject | undefined>(undefined)
  const [view, setView] = useState<View>('visits')
  const [visits, setVisits] = useState<StoredVisit[] | null>(null)
  const [deployments, setDeployments] = useState<FieldDeployment[] | null>(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<FieldLogsResult | null>(null)

  useEffect(() => {
    setVisits(null); setDeployments(null); setLogs(null); setError(null)
    if (!project) return
    let cancelled = false
    api.listVisits(project.acronym)
      .then(({ results }) => { if (!cancelled) setVisits(results) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the visits.') })
    api.fieldDeployments(project.acronym)
      .then(({ results }) => { if (!cancelled) setDeployments(results) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the deployments.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  async function writeLogs() {
    if (!project) return
    setError(null)
    try { setLogs(await api.writeFieldLogs(project.acronym)) } catch (e) { setError(e instanceof Error ? e.message : 'Could not write the logs.') }
  }

  const needle = filter.trim().toLowerCase()
  const shown = (visits ?? [])
    .filter((v) => !needle || `${v.location_id} ${v.session} ${v.camera_id ?? ''} ${v.sd ?? ''} ${v.trappers ?? ''} ${v.actions.join(' ')}`.toLowerCase().includes(needle))
    .sort((a, b) => `${b.date}T${b.time}`.localeCompare(`${a.date}T${a.time}`))

  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Visit book</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">The visits kept to a research project, and the deployments they say.</p>

      <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 px-6 py-5 mb-5">
        <h5 className="text-base font-semibold mb-3">Research project</h5>
        <ResearchProjectPicker value={project?.acronym ?? ''} onSelect={setProject} />
      </div>

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {project && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div className="inline-flex overflow-hidden rounded-lg border border-zinc-300 dark:border-zinc-700" role="tablist" aria-label="Show">
              {([['visits', 'Visits', visits?.length], ['deployments', 'Deployments', deployments?.length]] as const).map(([id, label, n]) => (
                <button key={id} type="button" role="tab" aria-selected={view === id} onClick={() => setView(id)}
                        className={`px-4 py-2.5 text-sm font-medium border-l first:border-l-0 border-zinc-300 dark:border-zinc-700 ${view === id ? 'bg-blue-600 text-white' : 'text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'}`}>{label}{n !== undefined ? ` ${n}` : ''}</button>
              ))}
            </div>
            {view === 'visits' && <input aria-label="Filter the visits" className={`${inputClass} !w-64`} placeholder="Site, session, camera, card, who…" value={filter} onChange={(e) => setFilter(e.target.value)} />}
          </div>

          {view === 'visits' && (
            visits === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the visits…</p> : (
              <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
                <table className="w-full text-sm" aria-label="Visits">
                  <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
                    <tr>{['When', 'Site', 'Session', 'Actions', 'Camera', 'Card', 'Photos', 'Who', 'Deployment'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}</tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                    {shown.map((v) => (
                      <tr key={`${v.location_id}|${v.date}|${v.time}`}>
                        <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{v.date} {v.time.slice(0, 5)}</td>
                        <td className="px-3 py-2 font-mono">{v.location_id}</td>
                        <td className="px-3 py-2 font-mono">{v.session}</td>
                        <td className="px-3 py-2">{v.actions.join(' + ')}</td>
                        <td className="px-3 py-2 font-mono">{v.camera_id ?? ''}</td>
                        <td className="px-3 py-2 font-mono">{v.sd ?? ''}</td>
                        <td className="px-3 py-2">{v.num_photos ?? ''}</td>
                        <td className="px-3 py-2">{v.trappers ?? ''}</td>
                        <td className="px-3 py-2 font-mono text-xs">{v.deployment_id ?? ''}</td>
                      </tr>
                    ))}
                    {shown.length === 0 && <tr><td colSpan={9} className="px-4 py-3 text-zinc-500 dark:text-zinc-400">{visits.length === 0 ? 'No visit has been registered to this research project yet.' : 'No visit matches.'}</td></tr>}
                  </tbody>
                </table>
              </div>
            )
          )}

          {view === 'deployments' && (
            <>
              {deployments === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p> : <FieldDeployments deployments={deployments} />}
              <div className="mt-4">
                <Notice kind="info" action={<button type="button" className={btnOutline} onClick={() => void writeLogs()}>Write the logs of all the collections again</button>}>
                  Each collection has a <strong>FileTimestampLog</strong> (the closed deployments) and a <strong>FieldworkLog</strong> (every one, closed or still out), made when a visit is registered.
                </Notice>
                {logs && (
                  <ul aria-label="Logs written" className="mt-2 list-disc pl-6 text-sm space-y-1">
                    {logs.collections.length === 0 && <li>No deployment yet: no visit has left a camera that another has collected, or is still out.</li>}
                    {logs.collections.map((c) => <li key={c.collection}><span className="font-mono">{c.collection}</span>: {c.closed} closed, {c.open} open — {c.files.map((f) => f.split(/[\\\\/]/).pop()).join(', ')}</li>)}
                    {logs.warnings.map((w) => <li key={w} className="text-amber-700 dark:text-amber-400">{w}</li>)}
                  </ul>
                )}
              </div>
            </>
          )}
        </>
      )}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
