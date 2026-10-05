import { useEffect, useState } from 'react'
import { api } from '../api'
import type { ClassificationProject, ResearchProject, SyncResult } from '../types'

const btnPrimary = 'px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
const labelClass = 'block text-sm font-semibold mb-1.5 text-zinc-700 dark:text-zinc-300'
const inputClass = 'w-full px-3 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500'

const KINDS: { key: keyof SyncResult['created']; label: string }[] = [
  { key: 'research_project', label: 'Research project' },
  { key: 'locations', label: 'Locations' },
  { key: 'collections', label: 'Collections' },
  { key: 'deployments', label: 'Deployments' },
  { key: 'timestamp_log', label: 'Timestamp log rows' },
  { key: 'images', label: 'Images files (images.json)' },
]

/** Checks the local collections folder against what Trapper has for a classification project, and creates what it lacks. */
export default function SyncCollectionsPage() {
  const [projects, setProjects] = useState<ResearchProject[]>([])
  const [projectPk, setProjectPk] = useState('')
  const [classifications, setClassifications] = useState<ClassificationProject[]>([])
  const [classificationPk, setClassificationPk] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [result, setResult] = useState<SyncResult | null>(null)

  const message = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback)

  useEffect(() => {
    api.trapperResearchProjects({})
      .then(({ results }) => setProjects(results))
      .catch((e) => setError(message(e, 'The research projects could not be read from Trapper.')))
  }, [])

  async function chooseProject(pk: string) {
    setProjectPk(pk); setClassificationPk(''); setClassifications([]); setResult(null); setError(null)
    if (!pk) return
    try {
      setClassifications((await api.trapperClassificationProjects({}, Number(pk))).results)
    } catch (e) {
      setError(message(e, 'The classification projects could not be read from Trapper.'))
    }
  }

  async function handleSync() {
    const project = projects.find((p) => String(p.pk) === projectPk)
    if (!project || !classificationPk) return
    setSyncing(true); setError(null); setResult(null)
    try {
      setResult(await api.syncCollections({}, project, Number(classificationPk)))
    } catch (e) {
      setError(message(e, 'The sync failed.'))
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="mx-auto px-4 py-8" style={{ maxWidth: 700 }}>
      <h1 className="text-2xl font-bold mb-1">Sync local collections</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">
        Pick a classification project of Trapper. The local folders are checked against it, and what is missing is created: the research
        project and its locations, the collections starting with R (each with its timestamp log) and the deployment of each. What is
        already there is left as it is, and the images are not downloaded.
      </p>

      <label className={labelClass} htmlFor="sync-research-project">Research project</label>
      <select id="sync-research-project" className={`${inputClass} mb-4`} value={projectPk} onChange={(e) => chooseProject(e.target.value)}>
        <option value="">Choose one…</option>
        {projects.map((p) => <option key={p.pk} value={p.pk}>{p.acronym ? `${p.acronym} — ${p.name}` : p.name}</option>)}
      </select>

      <label className={labelClass} htmlFor="sync-classification-project">Classification project</label>
      <select id="sync-classification-project" className={`${inputClass} mb-4`} value={classificationPk} disabled={!projectPk}
              onChange={(e) => { setClassificationPk(e.target.value); setResult(null) }}>
        <option value="">Choose one…</option>
        {classifications.map((c) => <option key={c.pk} value={c.pk}>{c.name}</option>)}
      </select>

      <button type="button" className={btnPrimary} disabled={!classificationPk || syncing} onClick={handleSync}>
        {syncing ? 'Syncing…' : 'Sync'}
      </button>

      {error && <p className="text-sm text-red-600 dark:text-red-400 mt-4">{error}</p>}

      {result && (
        <section className="mt-6 p-5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50/60 dark:bg-zinc-800/40" aria-label="Sync result">
          <h2 className="text-sm font-semibold mb-1">Synced into <span className="font-mono">{result.folder}</span></h2>
          <ul className="text-sm mt-2 space-y-1">
            {KINDS.map(({ key, label }) => (
              <li key={key}>
                <strong>{label}:</strong> {result.created[key].length} created, {result.kept[key].length} already there
                {result.created[key].length > 0 && <span className="block text-xs text-zinc-500 dark:text-zinc-400">{result.created[key].join(', ')}</span>}
              </li>
            ))}
          </ul>
          {result.collections.length === 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-400 mt-3">The classification project has no collection starting with R.</p>
          )}
          {result.unassigned.length > 0 && (
            <p className="text-sm text-amber-700 dark:text-amber-400 mt-3">
              Not in any of its collections, so not created: {result.unassigned.join(', ')}.
            </p>
          )}
        </section>
      )}
    </div>
  )
}
