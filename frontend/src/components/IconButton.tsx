import type { ReactNode } from 'react'
import { btnOutline } from '../pages/ImportDeploymentPage'

/** A button that is only an icon: its name and its tip say what it does. The same in every table that has a row of options. */
export default function IconButton({ label, title, path, onClick, expanded, disabled }: { label: string; title: string; path: ReactNode; onClick: () => void; expanded?: boolean; disabled?: boolean }) {
  return (
    <button type="button" aria-label={label} title={title} aria-expanded={expanded} disabled={disabled} onClick={onClick}
            className={`${btnOutline} inline-flex h-9 w-9 items-center justify-center !p-0`}>
      <svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" className="fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{path}</svg>
    </button>
  )
}

/** The icons the rows of the dashboards share. */
export const ICON_PATHS = {
  view: <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>,
  before: <><path d="M3 12a9 9 0 109-9 9 9 0 00-6.4 2.6L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l3 2" /></>,
  after: <><path d="M21 12a9 9 0 11-9-9 9 9 0 016.4 2.6L21 8" /><path d="M21 3v5h-5" /><path d="M12 7v5l3 2" /></>,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" /></>,
}
