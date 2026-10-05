import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import Combobox from '../components/Combobox'
import type { LocalResearchProject, UploadCollection, UploadDeploymentInfo, UploadEvent, UploadMode, UploadStep } from '../types'

const btnPrimary = 'px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
const btnOutline = 'px-4 py-2 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50'
const labelClass = 'block text-sm font-semibold mb-1.5 text-zinc-700 dark:text-zinc-300'
const inputClass = 'w-full px-3 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono'

const STEPS: { step: UploadStep; label: string }[] = [
  { step: 'connect', label: 'Connect to Trapper' },
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
export default function UploadDeploymentPage() {
  const [projects, setProjects] = useState<LocalResearchProject[]>([])
  const [projectId, setProjectId] = useState('')
  const [collections, setCollections] = useState<UploadCollection[]>([])
  const [collectionName, setCollectionName] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [maxZipMb, setMaxZipMb] = useState('500')
  const [mode, setMode] = useState<UploadMode>('upload')
  const [trapper, setTrapper] = useState<{ base_url: string | null; user_name: string | null; has_password: boolean } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [runs, setRuns] = useState<Record<string, Run>>({})
  const [order, setOrder] = useState<string[]>([])
  const [uploading, setUploading] = useState(false)
  const [finished, setFinished] = useState(false)

  useEffect(() => {
    api.listResearchProjects().then(({ results }) => setProjects(results)).catch((e) => setLoadError(e instanceof Error ? e.message : 'Could not read the collections folder.'))
    api.trapperGetConfig().then(setTrapper).catch(() => setTrapper(null))
  }, [])

  async function loadCollections(id: string) {
    setCollections([]); setCollectionName(''); setSelected(new Set()); setLoadError(null)
    if (!id) return
    try {
      const { results } = await api.uploadCollections(id)
      setCollections(results)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Could not read the collections.')
    }
  }

  function chooseProject(id: string) {
    setProjectId(id)
    setRuns({}); setOrder([]); setFinished(false)
    void loadCollections(id)
  }

  function chooseCollection(name: string) {
    setCollectionName(name)
    setRuns({}); setOrder([]); setFinished(false)
    const found = collections.find((c) => c.name === name)
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
  const zipMb = Number(maxZipMb)
  const zipValid = maxZipMb.trim() !== '' && Number.isInteger(zipMb) && zipMb >= 1 && zipMb <= 5000
  const connected = Boolean(trapper?.base_url && trapper.user_name && trapper.has_password)
  // Generating the files needs no account — the others look at Trapper.
  const accountOk = mode === 'generate' || connected
  const modeInfo = MODES.find((m) => m.value === mode)!
  const toUpload = (collection?.deployments ?? []).filter((d) => selected.has(d.deployment_id) && canUpload(d))

  async function handleUpload() {
    if (!collection) return
    const ids = toUpload.map((d) => d.deployment_id)
    setUploading(true); setFinished(false); setOrder(ids)
    setRuns(Object.fromEntries(ids.map((id) => [id, EMPTY_RUN])))
    for (const id of ids) {
      try {
        await api.uploadDeployment(projectId, collection.name, id, zipMb, mode, (event) => setRuns((r) => ({ ...r, [id]: reduceRun(r[id] ?? EMPTY_RUN, event) })))
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

      <Card title="Trapper" description={mode === 'generate' ? 'The account saved in the settings — not needed just to generate the files.' : 'The account saved in the settings.'}>
        {trapper === null ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the settings…</p>
        ) : connected ? (
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            <span className="font-mono">{trapper.user_name}</span> at <span className="font-mono">{trapper.base_url}</span>
          </p>
        ) : (
          <p className="text-sm text-amber-600 dark:text-amber-400">
            There is no Trapper account saved yet — set its URL, username and password in Settings › Trapper first
            {mode === 'generate' ? ' (to look up a research project that was not filled in from Trapper).' : '.'}
          </p>
        )}
      </Card>

      <Card title="What to upload" description="The research projects, collections and deployments kept in the collections folder.">
        <div className="mb-4">
          <label className={labelClass} htmlFor="upload-research-project">Research project</label>
          <Combobox
            id="upload-research-project" options={projects.map((p) => ({ value: p.acronym, label: `${p.acronym} — ${p.name}` }))}
            value={projectId} onChange={chooseProject} disabled={uploading}
            placeholder={projects.length === 0 ? 'No research projects yet' : 'Select a research project…'} clearLabel="Clear research project"
          />
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
          </div>
        )}

        {collection && (
          <div>
            <p className={labelClass}>Deployments</p>
            {collection.deployments.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">This collection has no deployments.</p>}
            <ul className="divide-y divide-zinc-200 dark:divide-zinc-700 rounded border border-zinc-200 dark:border-zinc-700">
              {collection.deployments.map((d) => (
                <li key={d.deployment_id} className="px-3 py-2">
                  <label className="flex items-start gap-2 text-sm cursor-pointer">
                    <input type="checkbox" className="mt-1" aria-label={d.deployment_id} checked={selected.has(d.deployment_id) && canUpload(d)}
                           disabled={!canUpload(d) || uploading} onChange={() => toggle(d.deployment_id)} />
                    <span className="flex-1">
                      <span className="font-mono text-zinc-900 dark:text-zinc-100">{d.deployment_id}</span>
                      <span className="block text-xs text-zinc-500 dark:text-zinc-400">
                        {d.images} image(s){d.start_date ? ` · ${d.start_date.slice(0, 10)} → ${(d.end_date ?? '').slice(0, 10)}` : ''}
                      </span>
                      {!d.preprocessed && (
                        <span className="block text-xs text-red-600 dark:text-red-400">Not preprocessed — import it again through the wizard before uploading it.</span>
                      )}
                      {d.uploaded_at && <span className="block text-xs text-emerald-600 dark:text-emerald-400">Uploaded {d.uploaded_at.slice(0, 10)}</span>}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
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
        <Card title="Packages" description="A deployment's images go up in zips of at most this size, each with its own yaml.">
          <div className="max-w-xs">
            <label className={labelClass} htmlFor="upload-max-zip">Largest zip (MB)</label>
            <input id="upload-max-zip" type="number" min={1} max={5000} step={1} className={inputClass} value={maxZipMb} disabled={uploading}
                   onChange={(e) => setMaxZipMb(e.target.value)} aria-invalid={zipValid ? undefined : true} />
            {!zipValid && <p className="text-xs text-red-600 dark:text-red-400 mt-1">A whole number from 1 to 5000.</p>}
          </div>
        </Card>
      )}

      {collection && (
        <div className="flex justify-end mb-6">
          <button type="button" className={btnPrimary} disabled={uploading || !accountOk || toUpload.length === 0 || !zipValid} onClick={handleUpload}>
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
