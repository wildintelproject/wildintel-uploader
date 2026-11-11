import { useState } from 'react'
import type { ClosedVisitTarget, UploadTarget } from '../types'
import ImportDeploymentPage from './ImportDeploymentPage'
import ImportSessionPage from './ImportSessionPage'

/** Import deployments: pick the closed visits the images are of. With one, it is Import deployment — a folder with the images; with several, a folder with a
 * subfolder of images for each, and the subfolder of each visit is said. */
export default function ImportDeploymentsPage({ onUpload, onOpenSettings, settingsOpen = false, onBack }: {
  onUpload?: (target: UploadTarget) => void; onOpenSettings?: (section?: 'epicollect' | 'general') => void; settingsOpen?: boolean; onBack?: () => void
}) {
  const [single, setSingle] = useState<ClosedVisitTarget | null>(null)
  if (single) return <ImportDeploymentPage closedVisit={single} onUpload={onUpload} settingsOpen={settingsOpen} onOpenSettings={onOpenSettings} onBack={() => setSingle(null)} />
  return <ImportSessionPage title="Import deployments" onSingleVisit={setSingle} onUpload={onUpload} settingsOpen={settingsOpen} onOpenSettings={onOpenSettings} onBack={onBack} />
}
