import { useState } from 'react'
import type { ReactNode } from 'react'
import TaskCard, { ArrowIcon } from '../components/TaskCard'
import RepairPage from './RepairPage'
import SyncCollectionsPage from './SyncCollectionsPage'
import TimeFixPage from './TimeFixPage'

export type Util = 'timefix' | 'repair' | 'sync'

const UTILS: { value: Util; icon: ReactNode; title: string; description: string }[] = [
  { value: 'timefix', icon: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>, title: 'Check and fix dates and times', description: 'Compare the dates of the images in a folder with the period of the visit, when the camera clock went wrong. Shift a run of images, or remove the ones whose time cannot be trusted. Every fix is written down.' },
  { value: 'repair', icon: <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />, title: 'Repair local deployments', description: 'Check which deployments of a local collection are still valid, and write the description files of the others again from what their folders hold.' },
  { value: 'sync', icon: <><path d="M21 12a9 9 0 0 0-15.5-6.2L3 8" /><path d="M3 3v5h5" /><path d="M3 12a9 9 0 0 0 15.5 6.2L21 16" /><path d="M16 16h5v5" /></>, title: 'Sync local collections', description: 'Check the local folders against what Trapper has for a classification project, and create what is missing: research project, locations, collections and deployments.' },
]

interface Props {
  onBack: () => void
}

/** The maintenance tasks besides importing and uploading — each shown in place of the list once chosen. */
export default function UtilsPage({ onBack }: Props) {
  const [util, setUtil] = useState<Util | null>(null)

  if (util) {
    return (
      <div>
        {util === 'timefix' ? <TimeFixPage onBack={() => setUtil(null)} /> : util === 'repair' ? <RepairPage onBack={() => setUtil(null)} /> : <SyncCollectionsPage onBack={() => setUtil(null)} />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <h1 className="text-2xl font-bold mb-1">Utilities</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">Maintenance of the local collections.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {UTILS.map((u) => <TaskCard key={u.value} icon={u.icon} title={u.title} description={u.description} onClick={() => setUtil(u.value)} />)}
      </div>
      <div className="mt-10">
        <button type="button" className="inline-flex items-center gap-2 px-4 h-10 text-sm font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded-lg hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors" onClick={onBack}><ArrowIcon back /> Back</button>
      </div>
    </div>
  )
}
