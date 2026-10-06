import OptionCards from '../components/OptionCards'
import type { Option } from '../components/OptionCards'
import type { Task } from '../types'

const TASK_OPTIONS: Option<Task>[] = [
  { value: 'deployment', emoji: '📷', title: 'Import deployment', description: 'Organize a folder of camera-trap images locally, then register the deployment in Trapper.', available: true },
  { value: 'upload', emoji: '☁️', title: 'Upload deployment to Trapper', description: 'Pick a collection kept locally and send a deployment to Trapper — creating its location and the deployment there if they are missing.', available: true },
  { value: 'session', emoji: '🗂️', title: 'Import session', description: 'A folder with one subfolder per deployment: the revision, the checks and the preprocessing are common, the location and dates are asked for each.', available: true },
  { value: 'upload-session', emoji: '📦', title: 'Upload session to Trapper', description: 'Send every deployment of a session kept locally to Trapper in one go.', available: false },
  { value: 'reports', emoji: '📑', title: 'Reports', description: 'What each validation, postvalidation and preprocessing checked and did, image by image — to look at again or download.', available: true },
  { value: 'sync', emoji: '🔄', title: 'Sync local collections', description: 'Check the local folders against what Trapper has for a classification project, and create the ones missing: research project, locations, collections and deployments.', available: true },
]

interface Props {
  onChoose: (task: Task) => void
}

export default function MenuPage({ onChoose }: Props) {
  return (
    <div className="mx-auto px-4 py-8" style={{ maxWidth: 700 }}>
      <h1 className="text-2xl font-bold mb-1">What do you want to do?</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">Choose one of the following.</p>
      <OptionCards options={TASK_OPTIONS} selected={null} onChoose={onChoose} />
    </div>
  )
}
