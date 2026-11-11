import DefaultResearchProject, { useDefaultResearchProject } from './DefaultResearchProject'

/** The card at the right of a page's title that says which research project is the active one — the default of the settings — and links to where it is changed. */
export default function ActiveProjectCard({ of, onOpenSettings, settingsOpen }: { of: string; onOpenSettings?: (section?: 'general') => void; settingsOpen?: boolean }) {
  const { project, defaultAcronym } = useDefaultResearchProject(settingsOpen)
  if (project === undefined && defaultAcronym === null) return null
  return <DefaultResearchProject compact project={project} defaultAcronym={defaultAcronym} of={of} onOpenSettings={onOpenSettings} />
}
