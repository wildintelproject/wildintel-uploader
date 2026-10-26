import { useState } from 'react'
import OptionCards from '../components/OptionCards'
import type { Option } from '../components/OptionCards'
import RepairPage from './RepairPage'
import SyncCollectionsPage from './SyncCollectionsPage'
import TimeFixPage from './TimeFixPage'

export type Util = 'timefix' | 'repair' | 'sync'

const UTIL_OPTIONS: Option<Util>[] = [
  { value: 'timefix', emoji: '🕑', title: 'Check and fix dates and times', description: 'Look at the dates of the images in a folder whose camera clock went wrong, against the period of the visit that left the camera: shift a run of images, or remove the ones with no time to trust. Every fix is written down.', available: true },
  { value: 'repair', emoji: '🛠️', title: 'Repair local deployments', description: 'Check which deployments of a local collection are still valid — as their seal says — and write the metadata files of the others again from what their folders hold.', available: true },
  { value: 'sync', emoji: '🔄', title: 'Sync local collections', description: 'Check the local folders against what Trapper has for a classification project, and create the ones missing: research project, locations, collections and deployments.', available: true },
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
      <h4 className="text-lg font-semibold mb-1">Utilities</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">Maintenance of the local collections.</p>
      <OptionCards options={UTIL_OPTIONS} selected={null} onChoose={setUtil} />
      <div className="mt-10">
        <button type="button" className="px-4 py-2 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors" onClick={onBack}>Back</button>
      </div>
    </div>
  )
}
