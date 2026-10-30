import { useState } from 'react'
import type { ReactNode } from 'react'
import ActiveProjectCard from '../components/ActiveProjectCard'
import TaskCard, { ArrowIcon, MENU_ICONS, PageHeader, UTIL_ICONS } from '../components/TaskCard'
import RepairPage from './RepairPage'
import SyncCollectionsPage from './SyncCollectionsPage'
import TimeFixPage from './TimeFixPage'

export type Util = 'timefix' | 'repair' | 'sync'

const UTILS: { value: Util; icon: ReactNode; title: string; description: string }[] = [
  { value: 'timefix', icon: UTIL_ICONS.timefix, title: 'Check and fix dates and times', description: 'Compare the dates of the images in a folder with the period of the visit, when the camera clock went wrong. Shift a run of images, or remove the ones whose time cannot be trusted. Every fix is written down.' },
  { value: 'repair', icon: UTIL_ICONS.repair, title: 'Repair local deployments', description: 'Check which deployments of a local collection are still valid, and write the description files of the others again from what their folders hold.' },
  { value: 'sync', icon: UTIL_ICONS.sync, title: 'Sync local collections', description: 'Check the local folders against what Trapper has for a classification project, and create what is missing: research project, locations, collections and deployments.' },
]

interface Props {
  onBack: () => void
  /** Opens the settings, where the active research project is changed. */
  onOpenSettings?: (section?: 'general') => void
  settingsOpen?: boolean
}

/** The maintenance tasks besides importing and uploading — each shown in place of the list once chosen. */
export default function UtilsPage({ onBack, onOpenSettings, settingsOpen }: Props) {
  const [util, setUtil] = useState<Util | null>(null)

  if (util) {
    return (
      <div>
        {util === 'timefix' ? <TimeFixPage onBack={() => setUtil(null)} onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} /> : util === 'repair' ? <RepairPage onBack={() => setUtil(null)} onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} /> : <SyncCollectionsPage onBack={() => setUtil(null)} onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <PageHeader icon={MENU_ICONS.utils} title="Utilities" description="Maintenance of the local collections." parent="Menu" onParent={onBack}
        aside={<ActiveProjectCard of="The utilities" onOpenSettings={onOpenSettings} settingsOpen={settingsOpen} />} />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {UTILS.map((u) => <TaskCard key={u.value} icon={u.icon} title={u.title} description={u.description} onClick={() => setUtil(u.value)} />)}
      </div>
      <div className="mt-10">
        <button type="button" className="inline-flex items-center gap-2 px-4 h-10 text-sm font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors" onClick={onBack}><ArrowIcon back /> Back</button>
      </div>
    </div>
  )
}
