import { useEffect, useState } from 'react'
import { api } from '../api'
import { defaultResearchProject } from '../defaultResearchProject'
import type { LocalResearchProject } from '../types'

/** The research project the general settings say is the default — the active one — read again when the settings are closed, as it may have been changed. */
export function useDefaultResearchProject(settingsOpen?: boolean): { project: LocalResearchProject | undefined; defaultAcronym: string | null; error: string | null } {
  const [project, setProject] = useState<LocalResearchProject | undefined>(undefined)
  const [defaultAcronym, setDefaultAcronym] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (settingsOpen) return
    let cancelled = false
    void (async () => {
      const acronym = await defaultResearchProject()
      if (cancelled) return
      setDefaultAcronym(acronym)
      try {
        const { results } = await api.listResearchProjects()
        if (!cancelled) setProject(results.find((p) => p.acronym.toLowerCase() === acronym.toLowerCase()))
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not read the research projects.')
      }
    })()
    return () => { cancelled = true }
  }, [settingsOpen])
  return { project, defaultAcronym, error }
}

/** The card that says which research project the page is of — the default one — with the link to the settings where it is changed. */
export default function DefaultResearchProject({ project, defaultAcronym, of, onOpenSettings }: {
  project: LocalResearchProject | undefined; defaultAcronym: string | null; of: string; onOpenSettings?: (section?: 'general') => void
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 px-6 py-5 mb-5">
      <h5 className="text-base font-semibold mb-2">Research project</h5>
      {project ? (
        <p className="text-base"><span className="font-mono font-semibold">{project.acronym}</span> — {project.name}</p>
      ) : defaultAcronym === null ? <p className="text-sm text-zinc-500 dark:text-zinc-400">Reading the settings…</p>
        : defaultAcronym ? <p className="text-sm text-amber-700 dark:text-amber-400">The default research project, <span className="font-mono">{defaultAcronym}</span>, is not in the collections folder.</p>
        : <p className="text-sm text-amber-700 dark:text-amber-400">No default research project is set.</p>}
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
        {of} is of the default research project.{' '}
        {onOpenSettings
          ? <button type="button" className="text-blue-600 dark:text-blue-400 hover:underline" onClick={() => onOpenSettings('general')}>Change it in the settings</button>
          : 'Change it in Settings › General.'}
      </p>
    </div>
  )
}
