import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'

interface Props { onStart: () => void }

const ICONS: Record<string, ReactNode> = {
  visits: <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />,
  deployment: <><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></>,
  session: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />,
  upload: <><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>,
}

const TASKS = [
  { icon: 'visits', title: 'Register visits', description: 'Record who visited each camera trap, when and what was done. The deployments are worked out from the visits.' },
  { icon: 'deployment', title: 'Import deployment', description: 'Organize a folder of images on this computer and register the deployment in Trapper.' },
  { icon: 'session', title: 'Import session', description: 'Several deployments from one folder, with one subfolder each. The checks and image preparation are shared.' },
  { icon: 'upload', title: 'Upload deployment to Trapper', description: 'Send a deployment kept on this computer to Trapper. Its location and the deployment are created there if missing.' },
]

/** Where the app stands: the Trapper it is connected to and the research project that comes filled in. */
function useStanding() {
  const [host, setHost] = useState<string | null>(null)
  const [project, setProject] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    Promise.resolve().then(() => api.getSettings()).then((s) => { if (alive) setProject(s?.GENERAL?.default_research_project?.trim() || null) }).catch(() => {})
    Promise.resolve().then(() => api.trapperTestConnection({})).then(async () => {
      const cfg = await api.trapperGetConfig()
      if (alive && cfg.base_url) setHost(new URL(cfg.base_url).host)
    }).catch(() => {})
    return () => { alive = false }
  }, [])
  return { host, project }
}

export default function WelcomePage({ onStart }: Props) {
  const { host, project } = useStanding()
  return (
    <div className="mx-auto max-w-[900px] px-4 py-10 flex flex-col items-center" style={{ minHeight: 'calc(100vh - 56px)' }}>
      <div className="mb-1 text-4xl">📤</div>
      <h1 className="text-2xl font-bold mb-2 text-center">WildINTEL Uploader</h1>
      <p className="text-zinc-500 dark:text-zinc-400 mb-8 text-lg text-center max-w-prose">
        Bring camera-trap images from a memory card into the WildINTEL project, organized and registered in Trapper.
      </p>
      <ul className="grid sm:grid-cols-2 gap-4 w-full list-none p-0 m-0">
        {TASKS.map((t) => (
          <li key={t.title} className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-5 py-5">
            <div className="flex items-center gap-3 mb-3">
              <span className="w-10 h-10 flex items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 shrink-0">
                <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{ICONS[t.icon]}</svg>
              </span>
              <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100 m-0">{t.title}</h2>
            </div>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed m-0">{t.description}</p>
          </li>
        ))}
      </ul>
      <button type="button" className="mt-8 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-base flex items-center gap-2" onClick={onStart}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Get started
      </button>
      {(host || project) && (
        <p role="status" className="mt-6 inline-flex items-center gap-2 rounded-full border border-zinc-200 dark:border-zinc-800 px-4 py-1.5 text-xs text-zinc-600 dark:text-zinc-400">
          {host && <><span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-emerald-500" />Connected to {host}</>}
          {host && project && <span aria-hidden="true">·</span>}
          {project && <>Default project {project}</>}
        </p>
      )}
    </div>
  )
}
