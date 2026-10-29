import { useState } from 'react'
import TaskCard, { MENU_ICONS, SectionHeader } from '../components/TaskCard'
import type { ClosedVisitTarget } from '../types'
import { btnOutline } from './ImportDeploymentPage'
import VisitBookPage from './VisitBookPage'
import type { VisitFocus } from './VisitBookPage'
import VisitsPage from './VisitsPage'

type View = 'register' | 'book'

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — the page is left as it is under them. */
  onOpenSettings?: (section?: 'general' | 'trappers' | 'sdcards' | 'cameras' | 'locations', researchProjectId?: string) => void
  settingsOpen?: boolean
  /** Goes to Import deployment for a visit that was just closed. */
  onImportImages?: (target: ClosedVisitTarget) => void
  /** Goes to the status of the deployments, on one of them. */
  onShowDeployment?: (deploymentId: string) => void
  /** The visit the dashboard opens on, when a link of the deployments dashboard sent the user here. */
  focusVisit?: VisitFocus
}

/** Manage the visits: register new ones, or look at the visit book. */
export default function VisitsHomePage({ onBack, onOpenSettings, settingsOpen, onImportImages, onShowDeployment, focusVisit }: Props) {
  const [view, setView] = useState<View | null>(focusVisit ? 'book' : null)

  if (view === 'register') return <VisitsPage onBack={() => setView(null)} onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} onImportImages={onImportImages} />
  if (view === 'book') return <VisitBookPage onBack={() => setView(null)} onImportImages={onImportImages} onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} onShowDeployment={onShowDeployment} focus={focusVisit} />

  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <SectionHeader icon={MENU_ICONS.visits} title="Manage visits" description="The visits to the camera traps, from which the deployments are worked out." onMenu={onBack} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <TaskCard icon={<><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></>} title="Visit dashboard"
                  description="The visits kept to a research project: which were made, which have the camera out or the card collected, and which are still to do." onClick={() => setView('book')} />
        <TaskCard icon={<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />} title="Register visits"
                  description="Record the visits to the camera traps: who went, when, to which site and what was done. The deployments are worked out from them." onClick={() => setView('register')} />
      </div>
      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
