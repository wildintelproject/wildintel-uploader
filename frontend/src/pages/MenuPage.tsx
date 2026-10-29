import type { ReactNode } from 'react'
import TaskCard, { ArrowIcon, LineIcon, taskCard } from '../components/TaskCard'
import type { Task } from '../types'

const ICONS: Record<string, ReactNode> = {
  visits: <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />,
  deployment: <><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></>,
  session: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />,
  upload: <><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>,
  utils: <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />,
}

const TASKS: { value: Task; icon: string; title: string; description: string }[] = [
  { value: 'visits', icon: 'visits', title: 'Manage visits', description: 'Register the visits to the camera traps — who went, when, to which site and what was done — or look at the visit book. The deployments are worked out from the visits.' },
  { value: 'deployment', icon: 'deployment', title: 'Manage deployments', description: 'Import a folder of camera-trap images as a deployment, or see the status of the deployments: which are closed, which still have the camera out and which are on Trapper.' },
  { value: 'upload', icon: 'upload', title: 'Manage uploads to Trapper', description: 'Send a deployment kept on this computer to Trapper, or see the status of the uploads: which deployments and revisions are on Trapper and which are still to be uploaded.' },
]

interface Props {
  onChoose: (task: Task) => void
}

export default function MenuPage({ onChoose }: Props) {
  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <h1 className="text-2xl font-bold mb-1">What do you want to do?</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">Choose one of the following.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {TASKS.map((t) => <TaskCard key={t.value} icon={ICONS[t.icon]} title={t.title} description={t.description} onClick={() => onChoose(t.value)} />)}
      </div>
      <button type="button" onClick={() => onChoose('utils')} className={`${taskCard} mt-4 w-full flex items-center gap-4 px-5 py-4 text-left`}>
        <span className="w-10 h-10 flex items-center justify-center rounded-xl bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300 shrink-0"><LineIcon>{ICONS.utils}</LineIcon></span>
        <span className="flex-1 min-w-0">
          <strong className="block text-sm text-zinc-900 dark:text-zinc-100">Utils</strong>
          <span className="block text-xs text-zinc-500 dark:text-zinc-400">Fix dates, repair local deployments, sync local collections.</span>
        </span>
        <span className="inline-flex items-center gap-2 px-4 h-9 rounded-lg bg-zinc-200 dark:bg-zinc-800 text-sm font-medium text-zinc-800 dark:text-zinc-200 shrink-0">Open utilities <ArrowIcon /></span>
      </button>
    </div>
  )
}
