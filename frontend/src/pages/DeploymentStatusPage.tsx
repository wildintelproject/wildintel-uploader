import { useEffect, useState } from 'react'
import { api } from '../api'
import { PageHeader } from '../components/TaskCard'
import DefaultResearchProject, { useDefaultResearchProject } from '../components/DefaultResearchProject'
import FieldDeployments from '../components/FieldDeployments'
import { readDeployment } from '../deploymentDetails'
import type { FieldDeployment } from '../types'
import { btnOutline } from './ImportDeploymentPage'
import type { VisitFocus } from './VisitBookPage'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — where the default research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
  /** The deployment shown highlighted, on its revision and its page: the one a link of the visit book goes to. */
  focus?: string
  /** Goes to the visit dashboard, on a visit: the one that started a deployment. */
  onShowVisit?: (visit: VisitFocus) => void
}

/** The dashboard of the deployments of the default research project — the statistics: which are closed with their images stored, which still have the camera out, which are not on Trapper yet. */
export default function DeploymentStatusPage({ onBack, onOpenSettings, settingsOpen, focus, onShowVisit }: Props) {
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
      <PageHeader icon={<path d="M18 20V10M12 20V4M6 20v-6" />} title="Deployments dashboard" description="The deployments the visits say, and how far each one is."
        parent="Manage deployments" onParent={onBack}
        aside={project !== undefined || defaultAcronym !== null ? <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of="The dashboard" onOpenSettings={onOpenSettings} /> : undefined} />

      {error && <p role="alert" className="mb-3 text-sm text-red-600 dark:text-red-400">{error}</p>}
      {project && (deployments === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the deployments…</p> : <FieldDeployments deployments={deployments} highlight={focus} onShowVisit={onShowVisit} loadDetails={(id) => readDeployment(project.acronym, id)} />)}

      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
