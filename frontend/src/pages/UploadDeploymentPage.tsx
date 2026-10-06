import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import Combobox from '../components/Combobox'
import type { AccessCheck, ClassificationProject, LocalResearchProject, UploadCollection, UploadTarget, UploadDeploymentInfo, UploadEvent, UploadMode, UploadStep } from '../types'

const btnPrimary = 'px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
const btnOutline = 'px-4 py-2 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50'
const labelClass = 'block text-sm font-semibold mb-1.5 text-zinc-700 dark:text-zinc-300'
const inputClass = 'w-full px-3 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono'

const STEPS: { step: UploadStep; label: string }[] = [
  { step: 'connect', label: 'Connect to Trapper' },
  { step: 'classification', label: 'Classification project' },
  { step: 'location', label: 'Location' },
  { step: 'deployment', label: 'Deployment' },
  { step: 'package', label: 'Pack the images' },
  { step: 'csv', label: 'Deployments csv' },
  { step: 'upload', label: 'Upload' },
  { step: 'process', label: 'Process' },
  { step: 'wait', label: 'Collection created' },
]

/** One deployment's upload as it goes. */
interface Run {
  steps: Partial<Record<UploadStep, { status: 'running' | 'done' | 'skipped'; message: string }>>
  progress: { file: string; bytes: number; total: number } | null
  result: Extract<UploadEvent, { type: 'done' }> | null
  error: string | null
}

const ACCESS_LABELS: Record<AccessCheck['check'], string> = {
  research_project: 'Research project', collection: 'Collection', classification_project: 'Classification project', location: 'Locations', uploader: 'Uploader',
}

const EMPTY_RUN: Run = { steps: {}, progress: null, result: null, error: null }

function reduceRun(run: Run, event: UploadEvent): Run {
  if (event.type === 'step') return { ...run, steps: { ...run.steps, [event.step]: { status: event.status, message: event.message } } }
  if (event.type === 'upload_progress') return { ...run, progress: { file: event.file, bytes: event.bytes, total: event.total } }
  return { ...run, result: event, progress: null }
}

const MODES: { value: UploadMode; title: string; description: string; button: (n: number) => string; busy: string }[] = [
  { value: 'upload', title: 'Upload to Trapper', description: 'Create what is missing in Trapper, pack the images and send them.',
    button: (n) => `Upload ${n} deployment${n === 1 ? '' : 's'}`, busy: 'Uploading…' },
  { value: 'dry_run', title: 'Dry run', description: 'Look at Trapper and say what would be created and how the images would be packed — nothing is created, sent or written.',
    button: (n) => `Dry run ${n} deployment${n === 1 ? '' : 's'}`, busy: 'Checking…' },
  { value: 'generate', title: 'Only generate the files', description: 'Write the zips, the yamls and the collection’s deployments csv, and leave them — to send some other way.',
    button: (n) => `Generate the files of ${n} deployment${n === 1 ? '' : 's'}`, busy: 'Generating…' },
]

function megabytes(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)
}

function Card({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="mb-5 p-5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50/60 dark:bg-zinc-800/40">
      <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h5>
      {description && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** What can be sent: a preprocessed deployment (the yaml needs the dates its preprocessing recorded). */
const canUpload = (d: UploadDeploymentInfo) => d.preprocessed && d.images > 0

/** Sends a deployment kept in a local collection to Trapper — pick the research project, the
 * collection and the deployments in it; each goes through creating its location and the
 * deployment in Trapper if they're missing, packing its images into a zip and a yaml, and uploading
 * them for Trapper to process into a collection. */
interface Props {
  /** Where to start from — the research project and collection a finished import went into. */
  initial?: UploadTarget
}

export default function UploadDeploymentPage({ initial }: Props = {}) {
  const [projects, setProjects] = useState<LocalResearchProject[]>([])
  const [projectId, setProjectId] = useState('')
  const [collections, setCollections] = useState<UploadCollection[]>([])
  const [collectionName, setCollectionName] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [mode, setMode] = useState<UploadMode>('upload')
  const [trapper, setTrapper] = useState<{ base_url: string | null; user_name: string | null; has_password: boolean } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [runs, setRuns] = useState<Record<string, Run>>({})
  const [order, setOrder] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [finished, setFinished] = useState(false)
  // The classification project the collection goes to: the ones Trapper has, and the chosen pk (a text, for when they can't be listed).
  const [classifications, setClassifications] = useState<ClassificationProject[]>([])
  const [classificationError, setClassificationError] = useState<string | null>(null)
  const [classificationPk, setClassificationPk] = useState('')
  const [access, setAccess] = useState<AccessCheck[] | null>(null)
  // Whether the account has access to the research project and the collection chosen — looked up as soon as both are.
  const [selectionChecks, setSelectionChecks] = useState<AccessCheck[] | null>(null)
  const [checkingSelection, setCheckingSelection] = useState(false)
  const [selectionError, setSelectionError] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [accessError, setAccessError] = useState<string | null>(null)

  useEffect(() => {
    if (initial) chooseProject(initial.researchProjectId, initial.collection)
    api.listResearchProjects().then(({ results }) => setProjects(results)).catch((e) => setLoadError(e instanceof Error ? e.message : 'Could not read the collections folder.'))
    api.trapperGetConfig().then(setTrapper).catch(() => setTrapper(null))
  }, [])

  async function loadCollections(id: string, pick?: string) {
    setCollections([]); setCollectionName(''); setSelected(new Set()); setLoadError(null)
    if (!id) return
    try {
      const { results } = await api.uploadCollections(id)
      setCollections(results)
      if (pick) selectCollection(pick, results)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not read the collections.')
    }
  }

  /** The classification projects Trapper has for the research project: with only one, it is the one chosen. */
  async function loadClassifications(id: string) {
    setClassifications([]); setClassificationPk(''); setClassificationError(null)
    if (!id || !connected) return
    try {
      const { results } = await api.uploadClassificationProjects(id)
      setClassifications(results)
      if (results.length === 1) setClassificationPk(String(results[0].pk))
    } catch (e) {
      setClassificationError(e instanceof Error ? e.message : 'Could not read the classification projects.')
    }
  }

  function chooseProject(id: string, pick?: string) {
    setProjectId(id)
    setRuns({}); setOrder([]); setFinished(false); setAccess(null); setAccessError(null)
    void loadCollections(id, pick)
  }

  function chooseCollection(name: string) {
    setRuns({}); setOrder([]); setFinished(false); setAccess(null); setAccessError(null)
    selectCollection(name, collections)
  }

  function selectCollection(name: string, from: UploadCollection[]) {
    setCollectionName(name)
    const found = from.find((c) => c.name === name)
    // What is left to send: preprocessed, and not sent before.
    setSelected(new Set((found?.deployments ?? []).filter((d) => canUpload(d) && !d.uploaded_at).map((d) => d.deployment_id)))
  }

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const collection = collections.find((c) => c.name === collectionName)
  const connected = Boolean(trapper?.base_url && trapper.user_name && trapper.has_password)
  // Generating the files needs no account — the others look at Trapper.
  const accountOk = mode === 'generate' || connected
  const modeInfo = MODES.find((m) => m.value === mode)!
  // The classification projects are looked up once the research project and the account are both known.
  useEffect(() => {
    void loadClassifications(projectId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, connected])

  useEffect(() => {
    setSelectionChecks(null); setSelectionError(null)
    if (!projectId || !collectionName || !connected) { setCheckingSelection(false); return }
    let cancelled = false
    setCheckingSelection(true)
    ;(async () => {
      try {
        const { checks } = await api.checkUploadSelection(projectId, collectionName)
        if (!cancelled) setSelectionChecks(checks)
      } catch (e) {
        if (!cancelled) setSelectionError(e instanceof Error ? e.message : 'Could not check the access.')
      } finally {
        if (!cancelled) setCheckingSelection(false)
      }
    })()
    return () => { cancelled = true }
  }, [projectId, collectionName, connected])

  const classificationValue = classificationPk.trim() === '' ? null : Number(classificationPk)
  const classificationValid = classificationValue === null || (Number.isInteger(classificationValue) && classificationValue >= 1)
  // The yaml needs one: with an account it is the one picked (or the only one); offline, the pk typed in.
  const classificationReady = classificationValue !== null && classificationValid
  const selectable = (collection?.deployments ?? []).filter(canUpload)
  const toUpload = (collection?.deployments ?? []).filter((d) => selected.has(d.deployment_id) && canUpload(d))

  /** Whether the account can reach the research project, its locations and the uploader — before sending anything. */
  async function handleTestAccess() {
    setTesting(true); setAccess(null); setAccessError(null)
    try {
      const { checks } = await api.checkUploadAccess(projectId, collection?.name ?? null, toUpload.map((d) => d.deployment_id), classificationValue)
      setAccess(checks)
    } catch (e) {
      setAccessError(e instanceof Error ? e.message : 'Could not test the connection.')
    } finally {
      setTesting(false)
    }
  }

  async function handleUpload() {
    if (!collection) return
    const ids = toUpload.map((d) => d.deployment_id)
    setUploading(true); setFinished(false); setOrder(ids)
    setRuns(Object.fromEntries(ids.map((id) => [id, EMPTY_RUN])))
    for (const id of ids) {
      try {
        await api.uploadDeployment(projectId, collection.name, id, mode, (event) => setRuns((r) => ({ ...r, [id]: reduceRun(r[id] ?? EMPTY_RUN, event) })), classificationValue)
      } catch (e) {
        setRuns((r) => ({ ...r, [id]: { ...(r[id] ?? EMPTY_RUN), progress: null, error: e instanceof Error ? e.message : 'The upload failed.' } }))
      }
    }
    setUploading(false); setFinished(true)
    if (mode === 'upload') void loadCollections(projectId).then(() => setCollectionName(collection.name)) // shows what was uploaded
  }

  const failures = order.filter((id) => runs[id]?.error).length
  const succeeded = order.filter((id) => runs[id]?.result).length

  return (
    <div className="max-w-screen-md mx-auto px-4 py-8">
      <h2 className="text-xl font-bold mb-1 text-zinc-900 dark:text-zinc-100">Upload deployment to Trapper</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        Sends a deployment kept in your collections folder to Trapper. Its location and the deployment are created there if they are
        missing; then its images are packed into a zip and a yaml and uploaded for Trapper to process.
      </p>

      {trapper === null ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">Reading the settings…</p>
      ) : connected ? (
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4 rounded border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30 px-3 py-2">
          <span aria-hidden="true">ℹ️ </span>Uploading with the Trapper account saved in the settings: <span className="font-mono">{trapper.user_name}</span> at <span className="font-mono">{trapper.base_url}</span>
          {mode === 'generate' ? ' (not needed just to generate the files).' : '.'}
        </p>
      ) : (
        <p className="text-sm text-amber-700 dark:text-amber-400 mb-4 rounded border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-3 py-2">
          <span aria-hidden="true">ℹ️ </span>There is no Trapper account saved yet — set its URL, username and password in Settings › Trapper first
          {mode === 'generate' ? ' (to look up a research project that was not filled in from Trapper).' : '.'}
        </p>
      )}

      <Card title="What to upload" description="The research projects, collections and deployments kept in the collections folder.">
        <div className="mb-4">
          <label className={labelClass} htmlFor="upload-research-project">Research project</label>
          <Combobox
            id="upload-research-project" options={projects.map((p) => ({ value: p.acronym, label: `${p.acronym} — ${p.name}` }))}
            value={projectId} onChange={chooseProject} disabled={uploading}
            placeholder={projects.length === 0 ? 'No research projects yet' : 'Select a research project…'} clearLabel="Clear research project"
          />
          {selectionChecks?.filter((c) => c.check === 'research_project').map((c) => (
            <p key={c.check} className={`text-xs mt-1 ${c.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>{c.ok ? '✔' : '⚠'} {c.message}</p>
          ))}
          {projects.length === 0 && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Nothing is kept in the collections folder yet — import a deployment first.</p>}
        </div>

        {projectId && (
          <div className="mb-4">
            <label className={labelClass} htmlFor="upload-collection">Collection</label>
            <Combobox
              id="upload-collection" options={collections.map((c) => ({ value: c.name, label: `${c.name} — ${c.deployments.length} deployment(s)` }))}
              value={collectionName} onChange={chooseCollection} disabled={uploading}
              placeholder={collections.length === 0 ? 'No collections yet' : 'Select a collection…'} clearLabel="Clear collection"
            />
            {checkingSelection && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Checking your access in Trapper…</p>}
            {selectionError && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{selectionError}</p>}
            {selectionChecks?.filter((c) => c.check === 'collection').map((c) => (
              <p key={c.check} className={`text-xs mt-1 ${c.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>{c.ok ? '✔' : '⚠'} {c.message}</p>
            ))}
          </div>
        )}

        {collection && (
          <div>
            <p className={labelClass}>Deployments</p>
            {collection.deployments.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">This collection has no deployments.</p>}
            {collection.deployments.length > 0 && (
              <div className="overflow-x-auto rounded border border-zinc-200 dark:border-zinc-700">
                <div className="flex items-center gap-3 flex-wrap px-3 py-2 text-xs border-b border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50">
                  <span className="text-zinc-500 dark:text-zinc-400">{selectable.filter((d) => selected.has(d.deployment_id)).length} of {selectable.length} selected</span>
                  <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={uploading || selectable.length === 0}
                          onClick={() => setSelected(new Set(selectable.map((d) => d.deployment_id)))}>Select all</button>
                  <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={uploading || selectable.every((d) => d.uploaded_at)}
                          onClick={() => setSelected(new Set(selectable.filter((d) => !d.uploaded_at).map((d) => d.deployment_id)))}>Select the not uploaded</button>
                  <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline disabled:opacity-50" disabled={uploading || selected.size === 0}
                          onClick={() => setSelected(new Set())}>Select none</button>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-zinc-500 dark:text-zinc-400">
                      <th scope="col" className="px-3 py-2 w-10">
                        <input type="checkbox" aria-label="Select all deployments" disabled={uploading || selectable.length === 0}
                               checked={selectable.length > 0 && selectable.every((d) => selected.has(d.deployment_id))}
                               ref={(el) => { if (el) el.indeterminate = selectable.some((d) => selected.has(d.deployment_id)) && !selectable.every((d) => selected.has(d.deployment_id)) }}
                               onChange={() => setSelected(selectable.every((d) => selected.has(d.deployment_id)) ? new Set() : new Set(selectable.map((d) => d.deployment_id)))} />
                      </th>
                      <th scope="col" className="px-3 py-2 font-medium">Deployment</th>
                      <th scope="col" className="px-3 py-2 font-medium text-right">Images</th>
                      <th scope="col" className="px-3 py-2 font-medium">Period</th>
                      <th scope="col" className="px-3 py-2 font-medium">Uploaded</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                    {collection.deployments.map((d) => (
                      <tr key={d.deployment_id}>
                        <td className="px-3 py-2">
                          <input type="checkbox" aria-label={d.deployment_id} checked={selected.has(d.deployment_id) && canUpload(d)}
                                 disabled={!canUpload(d) || uploading} onChange={() => toggle(d.deployment_id)} />
                        </td>
                        <td className="px-3 py-2">
                          <span className="font-mono text-zinc-900 dark:text-zinc-100">{d.deployment_id}</span>
                          {!d.preprocessed && (
                            <span className="block text-xs text-red-600 dark:text-red-400">Not preprocessed — import it again through the wizard before uploading it.</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right">{d.images}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-zinc-600 dark:text-zinc-400">{d.start_date ? `${d.start_date.slice(0, 10)} → ${(d.end_date ?? '').slice(0, 10)}` : '—'}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {d.uploaded_at
                            ? <span className="text-emerald-600 dark:text-emerald-400">✔ {d.uploaded_at.slice(0, 10)}</span>
                            : <span className="text-zinc-500 dark:text-zinc-400">Not uploaded</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
        {collection && (
          <div className="mt-4">
            <label className={labelClass} htmlFor="upload-classification">Classification project</label>
            {classifications.length > 0 || connected ? (
              <Combobox
                id="upload-classification" options={classifications.map((c) => ({ value: String(c.pk), label: `${c.name} (#${c.pk})${c.is_active ? '' : ' — inactive'}` }))}
                value={classificationPk} onChange={setClassificationPk} disabled={uploading}
                placeholder={classifications.length === 0 ? 'No classification projects yet' : 'Select a classification project…'} clearLabel="Clear classification project"
              />
            ) : (
              <input id="upload-classification" type="number" min={1} step={1} className={inputClass} value={classificationPk} disabled={uploading}
                     placeholder="Its pk in Trapper" onChange={(e) => setClassificationPk(e.target.value)} aria-invalid={classificationValid ? undefined : true} />
            )}
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">The collection is created in this classification project of Trapper.</p>
            {classificationError && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{classificationError}</p>}
            {!classificationError && connected && classifications.length === 0 && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Trapper has none for this research project — create it there first.</p>
            )}
            {!connected && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">Without a Trapper account they can’t be listed: type its pk.</p>}
            {connected && classifications.length > 1 && !classificationReady && (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">The research project has several: pick the one the collection goes to.</p>
            )}
          </div>
        )}
        {collection && connected && classificationReady && (
          <div className="mt-4">
            <div className="flex items-center gap-3 flex-wrap">
              <button type="button" className={btnOutline} disabled={testing || uploading} onClick={handleTestAccess}>
                {testing ? 'Testing…' : 'Test connection'}
              </button>
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Checks the research project, the classification project, its locations and the uploader — nothing is created or sent.</span>
            </div>
            {accessError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{accessError}</p>}
            {access && (
              <ul className="mt-2 space-y-1 text-sm" aria-label="Connection test">
                {access.map((c) => (
                  <li key={c.check} className={c.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
                    {c.ok ? '✔' : '⚠'} <span className="font-medium">{ACCESS_LABELS[c.check]}</span> — {c.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {loadError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{loadError}</p>}
      </Card>

      {collection && (
        <Card title="What to do" description="Run the real upload, rehearse it, or just prepare the files.">
          <div className="space-y-2" role="radiogroup" aria-label="What to do">
            {MODES.map((m) => (
              <label key={m.value} className={`flex items-start gap-2 p-3 rounded border cursor-pointer ${mode === m.value ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30' : 'border-zinc-200 dark:border-zinc-700'}`}>
                <input type="radio" name="upload-mode" className="mt-1" checked={mode === m.value} disabled={uploading} onChange={() => { setMode(m.value); setRuns({}); setOrder([]); setFinished(false) }} aria-label={m.title} />
                <span>
                  <span className="block text-sm font-semibold text-zinc-900 dark:text-zinc-100">{m.title}</span>
                  <span className="block text-xs text-zinc-500 dark:text-zinc-400">{m.description}</span>
                </span>
              </label>
            ))}
          </div>
        </Card>
      )}

      {collection && (
        <div className="flex justify-end mb-6">
          <button type="button" className={btnPrimary} disabled={uploading || !accountOk || toUpload.length === 0 || !classificationReady} onClick={handleUpload}>
            {uploading ? modeInfo.busy : modeInfo.button(toUpload.length)}
          </button>
        </div>
      )}

      {order.length > 0 && (
        <div className="space-y-4">
          {order.map((id) => {
            const run = runs[id] ?? EMPTY_RUN
            return (
              <section key={id} className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-700" aria-label={`Upload of ${id}`}>
                <h5 className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-2">{id}</h5>
                <ol className="space-y-1 text-sm">
                  {STEPS.filter(({ step }) => run.steps[step]).map(({ step, label }) => {
                    const info = run.steps[step]!
                    return (
                      <li key={step} className={info.status === 'done' ? 'text-emerald-600 dark:text-emerald-400' : 'text-zinc-600 dark:text-zinc-400'}>
                        {info.status === 'done' ? '✔' : '…'} <span className="font-medium">{label}</span> — {info.message}
                      </li>
                    )
                  })}
                </ol>
                {run.progress && (
                  <div className="mt-2">
                    <progress className="w-full" max={run.progress.total} value={run.progress.bytes} aria-label={`Uploading ${run.progress.file}`} />
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 font-mono">
                      {run.progress.file} — {megabytes(run.progress.bytes)} of {megabytes(run.progress.total)} MB
                    </p>
                  </div>
                )}
                {run.result && run.result.mode === 'upload' && (
                  <p className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">
                    ✔ Uploaded to collection {run.result.collection} in {run.result.parts} package(s).
                  </p>
                )}
                {run.result && run.result.mode === 'dry_run' && (
                  <div className="mt-2 text-sm text-sky-700 dark:text-sky-400">
                    <p>🔍 Dry run — nothing was created, sent or written.</p>
                    <ul className="list-disc ml-6 text-xs">
                      <li>{run.result.would_create_location ? 'The location would be created in Trapper.' : 'The location is already in Trapper.'}</li>
                      <li>{run.result.would_create_deployment ? 'The deployment would be created in Trapper.' : 'The deployment is already in Trapper.'}</li>
                      <li>The images would go up in {run.result.parts} package(s).</li>
                    </ul>
                  </div>
                )}
                {run.result && run.result.mode === 'generate' && (
                  <div className="mt-2 text-sm text-emerald-600 dark:text-emerald-400">
                    <p>✔ Files written to <span className="font-mono break-all">{run.result.output_dir}</span>:</p>
                    <ul className="list-disc ml-6 text-xs font-mono">
                      {(run.result.files ?? []).map((f) => <li key={f}>{f}</li>)}
                    </ul>
                    <button type="button" className={`${btnOutline} mt-2`} onClick={() => void api.openFolder(run.result!.output_dir!).catch(() => {})}>
                      Open folder in file explorer
                    </button>
                  </div>
                )}
                {run.error && <p className="mt-2 text-sm text-red-600 dark:text-red-400">⚠ {run.error}</p>}
              </section>
            )
          })}
          {finished && (
            <p className={`text-sm ${failures ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}`}>
              {succeeded} deployment(s) {mode === 'upload' ? 'uploaded' : mode === 'dry_run' ? 'checked' : 'generated'}{failures ? `, ${failures} failed` : ''}.
            </p>
          )}
        </div>
      )}
      {finished && (
        <div className="flex justify-end mt-4">
          <button type="button" className={btnOutline} onClick={() => { setRuns({}); setOrder([]); setFinished(false) }}>Upload more</button>
        </div>
      )}
    </div>
  )
}
