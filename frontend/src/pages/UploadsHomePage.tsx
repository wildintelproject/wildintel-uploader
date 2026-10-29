import TaskCard from '../components/TaskCard'
import { btnOutline } from './ImportDeploymentPage'

export type UploadsView = 'upload' | 'status'

interface Props {
  onBack: () => void
  onChoose: (view: UploadsView) => void
}

/** Manage the uploads to Trapper: send a deployment, or look at the status of the uploads of the deployments and the revisions. */
export default function UploadsHomePage({ onBack, onChoose }: Props) {
  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <h1 className="text-2xl font-bold mb-1">Manage uploads to Trapper</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">Send a deployment to Trapper, or see how far the uploads are.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <TaskCard icon={<><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>} title="Upload deployment to Trapper"
                  description="Pick a collection kept on this computer and send a deployment to Trapper. Its location and the deployment are created there if they are missing." onClick={() => onChoose('upload')} />
        <TaskCard icon={<><path d="M18 20V10M12 20V4M6 20v-6" /></>} title="Show uploads status"
                  description="Which deployments and revisions are on Trapper, and which are closed with their images stored and still to be uploaded." onClick={() => onChoose('status')} />
      </div>
      <div className="mt-10">
        <button type="button" className={btnOutline} onClick={onBack}><span aria-hidden="true">← </span>Back</button>
      </div>
    </div>
  )
}
