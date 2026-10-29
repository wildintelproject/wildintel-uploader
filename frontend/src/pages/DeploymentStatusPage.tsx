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
  /** The deployment shown highlighted, on its revision and its page: the one a link of the visit book goes to. */
  focus?: string
}

/** The status of the deployments of the default research project — the statistics: which are closed with their images stored, which still have the camera out, which are not on Trapper yet. */
export default function DeploymentStatusPage({ onBack, onOpenSettings, settingsOpen, focus }: Props) {
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

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Deployments status</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">The deployments the visits say, and how far each one is.</p>

      <DefaultResearchProject project={project} defaultAcronym={defaultAcronym} of="The status" onOpenSettings={onOpenSettings} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && (deployments === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p> : <FieldDeployments deployments={deployments} highlight={focus} />)}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
