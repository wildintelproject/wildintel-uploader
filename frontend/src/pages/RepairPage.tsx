import { useEffect, useState } from 'react'
import { api } from '../api'
import Combobox from '../components/Combobox'
import ReportPanel from '../components/ReportPanel'
import { SmallSpinner, btnOutline, btnPrimary } from './ImportDeploymentPage'
import type { LocalResearchProject, RepairCollection, RepairDeployment, RepairEvent, RepairState, RepairStep } from '../types'

const labelClass = 'block text-sm font-semibold mb-1.5 text-zinc-700 dark:text-zinc-300'

const STEPS: { step: RepairStep; label: string }[] = [
  { step: 'inspect', label: 'Look at the folder' },
  { step: 'dates', label: 'Dates and timestamp log' },
  { step: 'deployment', label: 'deployment.json' },
  { step: 'preprocessing', label: 'preprocessing.json' },
  { step: 'images', label: 'images.json' },
  { step: 'seal', label: 'Validate and seal' },
]

interface Run {
  steps: Partial<Record<RepairStep, { status: 'running' | 'done' | 'skipped'; message: string }>>
  result: Extract<RepairEvent, { type: 'done' }> | null
  error: string | null
}

const EMPTY_RUN: Run = { steps: {}, result: null, error: null }

function reduceRun(run: Run, event: RepairEvent): Run {
  if (event.type === 'step') return { ...run, steps: { ...run.steps, [event.step]: { status: event.status, message: event.message } } }
  return { ...run, result: event }
}

/** The badge of a deployment: valid is what its seal says — anything else is not. */
function StateBadge({ state, repairing }: { state: RepairState | undefined; repairing: boolean }) {
  if (repairing) return <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400"><SmallSpinner />Repairing…</span>
  const [text, tone] = !state ? ['Not checked', 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400']
    : state.status === 'valid' ? ['✔ Valid', 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300']
    : state.status === 'synced' ? ['From Trapper', 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300']
    : state.status === 'unsealed' ? ['⚠ Not sealed', 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300']
    : ['⚠ Not valid', 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300']
  return <span className={`inline-block whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>{text}</span>
}

/** Checks the deployments kept in a local collection — a deployment is valid if its seal.json still matches it — and repairs the ones that
 * are not: their metadata files (deployment.json, images.json, preprocessing.json, seal.json) are written again from what the folder
 * holds, taking the period from the collection's timestamp log when it has the deployment. */
export default function RepairPage() {
  const [projects, setProjects] = useState<LocalResearchProject[]>([])
  const [projectId, setProjectId] = useState('')
  const [collections, setCollections] = useState<RepairCollection[]>([])
  const [collectionName, setCollectionName] = useState('')
  const [states, setStates] = useState<Record<string, RepairState>>({})
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [checking, setChecking] = useState(false)
  const [repairing, setRepairing] = useState<string | null>(null)
  const [runs, setRuns] = useState<Record<string, Run>>({})
  const [order, setOrder] = useState<string[]>([])
  const [finished, setFinished] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const message = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

  useEffect(() => {
    api.listResearchProjects().then(({ results }) => setProjects(results)).catch((e) => setError(message(e, 'Could not read the collections folder.')))
  }, [])

  const collection = collections.find((c) => c.name === collectionName)
  const deployments = collection?.deployments ?? []
  const repairable = deployments.filter((d) => !d.synced)
  const busy = checking || repairing !== null

  function reset() { setStates({}); setRuns({}); setOrder([]); setFinished(false); setError(null) }

  async function chooseProject(id: string) {
    setProjectId(id); setCollections([]); setCollectionName(''); setSelected(new Set()); reset()
    if (!id) return
    try {
      setCollections((await api.repairCollections(id)).results)
    } catch (e) {
      setError(message(e, 'Could not read the collections.'))
    }
  }

  function chooseCollection(name: string) {
    setCollectionName(name); reset()
    setSelected(new Set((collections.find((c) => c.name === name)?.deployments ?? []).filter((d) => !d.synced).map((d) => d.deployment_id)))
  }

  const toggle = (id: string) => setSelected((s) => { const next = new Set(s); if (!next.delete(id)) next.add(id); return next })

  /** Looks at every deployment of the collection: which seals still match, and what is wrong with the others. */
  async function handleCheck() {
    if (!collection) return
    setChecking(true); setError(null); setFinished(false)
    const found: Record<string, RepairState> = {}
    try {
      for (const d of deployments) {
        found[d.deployment_id] = await api.repairInspect(projectId, collection.name, d.deployment_id)
        setStates({ ...found })
      }
      // What is left to do: the ones that are not valid.
      setSelected(new Set(deployments.filter((d) => found[d.deployment_id]?.status === 'broken' || found[d.deployment_id]?.status === 'unsealed').map((d) => d.deployment_id)))
    } catch (e) {
      setError(message(e, 'Could not check the deployments.'))
    } finally {
      setChecking(false)
    }
  }

  async function handleRepair() {
    if (!collection) return
    const ids = deployments.filter((d) => selected.has(d.deployment_id) && !d.synced).map((d) => d.deployment_id)
    setError(null); setFinished(false); setOrder(ids)
    setRuns(Object.fromEntries(ids.map((id) => [id, EMPTY_RUN])))
    for (const id of ids) {
      setRepairing(id)
      try {
        await api.repairDeployment(projectId, collection.name, id, (event) => setRuns((r) => ({ ...r, [id]: reduceRun(r[id] ?? EMPTY_RUN, event) })))
      } catch (e) {
        setRuns((r) => ({ ...r, [id]: { ...(r[id] ?? EMPTY_RUN), error: message(e, 'The repair failed.') } }))
      }
      try {
        const state = await api.repairInspect(projectId, collection.name, id) // how it ended
        setStates((s) => ({ ...s, [id]: state }))
      } catch { /* the repair's own result says it */ }
    }
    setRepairing(null); setFinished(true)
    void api.repairCollections(projectId).then(({ results }) => setCollections(results)).catch(() => {})
  }

  const checked = deployments.some((d) => states[d.deployment_id])
  const notValid = (d: RepairDeployment) => !d.synced && states[d.deployment_id] !== undefined && states[d.deployment_id].status !== 'valid'
  const chosen = repairable.filter((d) => selected.has(d.deployment_id))
  const failures = order.filter((id) => runs[id]?.error).length

  return (
    <div className="mx-auto px-4 py-8" style={{ maxWidth: 760 }}>
      <h1 className="text-2xl font-bold mb-1">Repair local deployments</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">
        Pick a research project and a collection kept in the collections folder. A deployment is <strong>valid</strong> when its <span className="font-mono">seal.json</span> still
        matches it. For the ones that are not, the metadata files are written again from what the folder holds — the dates of the images, their camera, the location&rsquo;s details —
        and the images are validated and postvalidated again. If the collection&rsquo;s <span className="font-mono">FileTimestampLog.csv</span> has the deployment, it says its period.
      </p>

      <div className="mb-4">
        <label className={labelClass} htmlFor="repair-research-project">Research project</label>
        <Combobox
          id="repair-research-project" options={projects.map((p) => ({ value: p.acronym, label: `${p.acronym} — ${p.name}` }))}
          value={projectId} onChange={chooseProject} disabled={busy}
          placeholder={projects.length === 0 ? 'No research projects yet' : 'Select a research project…'} clearLabel="Clear research project"
        />
      </div>

      {projectId && (
        <div className="mb-4">
          <label className={labelClass} htmlFor="repair-collection">Collection</label>
          <Combobox
            id="repair-collection" options={collections.map((c) => ({ value: c.name, label: `${c.name} — ${c.deployments.length} deployment(s)` }))}
            value={collectionName} onChange={chooseCollection} disabled={busy}
            placeholder={collections.length === 0 ? 'No collections yet' : 'Select a collection…'} clearLabel="Clear collection"
          />
        </div>
      )}

      {collection && (
        <div className="mb-4">
          <div className="flex items-center justify-between flex-wrap gap-2 mb-1.5">
            <p className={`${labelClass} !mb-0`}>Deployments</p>
            <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={busy || deployments.length === 0} onClick={handleCheck}>
              {checking && <SmallSpinner />}{checking ? 'Checking…' : 'Check the deployments'}
            </button>
          </div>
          {deployments.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">This collection has no deployment folders.</p>}
          {deployments.length > 0 && (
            <div className="overflow-x-auto rounded border border-zinc-200 dark:border-zinc-700">
              <div className="flex items-center gap-3 flex-wrap px-3 py-2 text-xs border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
                <span className="text-zinc-500 dark:text-zinc-400">{chosen.length} of {repairable.length} selected</span>
                <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={busy || repairable.length === 0}
                        onClick={() => setSelected(new Set(repairable.map((d) => d.deployment_id)))}>Select all</button>
                <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={busy || !deployments.some(notValid)}
                        onClick={() => setSelected(new Set(deployments.filter(notValid).map((d) => d.deployment_id)))}>Select the not valid</button>
                <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={busy || selected.size === 0}
                        onClick={() => setSelected(new Set())}>Select none</button>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500 dark:text-zinc-400">
                    <th scope="col" className="px-3 py-2 w-10">
                      <input type="checkbox" aria-label="Select all deployments" disabled={busy || repairable.length === 0}
                             checked={repairable.length > 0 && chosen.length === repairable.length}
                             ref={(el) => { if (el) el.indeterminate = chosen.length > 0 && chosen.length < repairable.length }}
                             onChange={() => setSelected(chosen.length === repairable.length ? new Set() : new Set(repairable.map((d) => d.deployment_id)))} />
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">Deployment</th>
                    <th scope="col" className="px-3 py-2 font-medium text-right">Images</th>
                    <th scope="col" className="px-3 py-2 font-medium">State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                  {deployments.map((d) => {
                    const state = states[d.deployment_id]
                    return (
                      <tr key={d.deployment_id} className="align-top">
                        <td className="px-3 py-2">
                          <input type="checkbox" aria-label={d.deployment_id} checked={selected.has(d.deployment_id) && !d.synced} disabled={d.synced || busy} onChange={() => toggle(d.deployment_id)} />
                        </td>
                        <td className="px-3 py-2 font-mono text-zinc-900 dark:text-zinc-100">{d.deployment_id}</td>
                        <td className="px-3 py-2 text-right">{state?.images ?? d.images}</td>
                        <td className="px-3 py-2">
                          <StateBadge state={state} repairing={repairing === d.deployment_id} />
                          {state && state.status !== 'valid' && state.problems.length > 0 && (
                            <ul className="mt-1 space-y-0.5 text-xs text-amber-700 dark:text-amber-400" aria-label={`Problems of ${d.deployment_id}`}>
                              {state.problems.map((p) => <li key={p}>• {p}</li>)}
                            </ul>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {!checked && deployments.length > 0 && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5">Check the deployments to see which are valid; reading their seals takes a moment.</p>}
        </div>
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400 mb-3">{error}</p>}

      {collection && deployments.length > 0 && (
        <div className="flex justify-end mb-6">
          <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={busy || chosen.length === 0} onClick={handleRepair}>
            {repairing !== null && <SmallSpinner />}{repairing !== null ? 'Repairing…' : `Repair ${chosen.length} deployment${chosen.length === 1 ? '' : 's'}`}
          </button>
        </div>
      )}

      {order.length > 0 && (
        <div className="space-y-3" aria-live="polite">
          {order.map((id) => {
            const run = runs[id] ?? EMPTY_RUN
            return (
              <section key={id} className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-700" aria-label={`Repair of ${id}`}>
                <h5 className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-2">{id}</h5>
                <ol className="space-y-1 text-sm">
                  {STEPS.filter(({ step }) => run.steps[step]).map(({ step, label }) => {
                    const info = run.steps[step]!
                    return (
                      <li key={step} className={info.status === 'done' ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-600 dark:text-zinc-400'}>
                        {info.status === 'done' ? '✔' : info.status === 'skipped' ? '–' : '…'} <span className="font-medium">{label}</span> — {info.message}
                      </li>
                    )
                  })}
                </ol>
                {run.error && <p className="text-sm text-red-600 dark:text-red-400 mt-2">⚠ {run.error}</p>}
                {run.result && (
                  <div className="mt-2 text-sm">
                    <p className={run.result.status === 'valid' ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}>
                      {run.result.status === 'valid' ? '✔ Valid again' : '⚠ Not valid yet'} — wrote {run.result.written.join(', ') || 'nothing'}.
                    </p>
                    {run.result.report_id && <ReportPanel reportId={run.result.report_id} />}
                  </div>
                )}
              </section>
            )
          })}
          {finished && (
            <p className={`text-sm ${failures ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {order.length - failures} deployment(s) repaired{failures ? `, ${failures} failed` : ''}.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
