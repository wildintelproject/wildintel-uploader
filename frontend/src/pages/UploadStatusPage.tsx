import { useEffect, useState } from 'react'
import { api } from '../api'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import FieldDeployments from '../components/FieldDeployments'
import type { FieldDeployment } from '../types'
import { btnOutline } from './ImportDeploymentPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
}

/** What a revision has of the upload: its deployments that are closed with their images stored, and how many of them are on Trapper. */
export function uploadsOf(deployments: FieldDeployment[]) {
  const revisions = [...new Set(deployments.map((d) => d.collection))].sort((a, b) => b.localeCompare(a))
  return revisions.map((collection) => {
    const own = deployments.filter((d) => d.collection === collection)
    const ready = own.filter((d) => d.status === 'closed' && d.images_stored)
    const onTrapper = own.filter((d) => d.on_trapper).length
    return { collection, total: own.length, ready: ready.length, onTrapper, toUpload: ready.filter((d) => !d.on_trapper).length }
  })
}

/** The status of the uploads to Trapper of the default research project: each revision with how many of its deployments are on Trapper and how many wait, and the deployments below. */
export default function UploadStatusPage({ onBack, onOpenSettings, settingsOpen }: Props) {
  const { project, defaultAcronym, error: projectError } = useDefaultResearchProject(settingsOpen)
  const [deployments, setDeployments] = useState<FieldDeployment[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const error = projectError ?? loadError

  useEffect(() => {
    setDeployments(null); setLoadError(null)
    if (!project) return
    let cancelled = false
    api.fieldDeployments(project.acronym)
      .then(({ results }) => { if (!cancelled) setDeployments(results) })
      .catch((e) => { if (!cancelled) setLoadError(e instanceof Error ? e.message : 'Could not read the deployments.') })
    return () => { cancelled = true }
  }, [project?.acronym]) // eslint-disable-line react-hooks/exhaustive-deps

  const revisions = deployments ? uploadsOf(deployments) : []
  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Uploads status</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">What is on Trapper and what is still to be uploaded, by revision and by deployment.</p>

      <DefaultResearchProject project={project} defaultAcronym={defaultAcronym} of="The status" onOpenSettings={onOpenSettings} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && deployments === null && <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p>}
      {deployments !== null && <FieldDeployments deployments={deployments} initialFilter="to_upload" belowSummary={revisions.length > 0 && (
  <section aria-label="Uploads by revision" className="mb-6">
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
      <table className="w-full text-sm" aria-label="Revisions">
        <thead className="bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
          <tr>{['Revision', 'Deployments', 'Ready to upload', 'On Trapper', 'Progress'].map((h) => <th key={h} scope="col" className="px-3 py-2.5 text-left font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
          {revisions.map((r) => (
            <tr key={r.collection}>
              <td className="px-3 py-3 font-mono text-xs font-semibold">{r.collection}</td>
              <td className="px-3 py-3">{r.total}</td>
              <td className="px-3 py-3">{r.toUpload}</td>
              <td className="px-3 py-3">{r.onTrapper} of {r.total}</td>
              <td className="px-3 py-3 w-48">
                <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700" role="progressbar" aria-label={`${r.collection} on Trapper`} aria-valuemin={0} aria-valuemax={r.total} aria-valuenow={r.onTrapper}>
                  <div className="h-2 rounded-full bg-emerald-500" style={{ width: `${r.total ? Math.round((r.onTrapper / r.total) * 100) : 0}%` }} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
      )} />}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
