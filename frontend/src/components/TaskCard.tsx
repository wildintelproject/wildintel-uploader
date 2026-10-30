import type { ReactNode } from 'react'

export const taskCard = 'rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 transition-colors hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer'

/** A line icon (24×24, stroke) in the colour of the text, from the paths it is drawn with. */
export const LineIcon = ({ children, size = 18 }: { children: ReactNode; size?: number }) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>
)

export const ArrowIcon = ({ back = false }: { back?: boolean }) => (
  <LineIcon size={16}>{back ? <path d="M19 12H5M11 6l-6 6 6 6" /> : <path d="M5 12h14M13 6l6 6-6 6" />}</LineIcon>
)

/** The icon of each task of the menu: the card of the menu and the title of its page draw the same one. */
export const MENU_ICONS: Record<string, ReactNode> = {
  visits: <><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></>,
  deployment: <><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></>,
  session: <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />,
  upload: <><path d="M20 16.2A4.5 4.5 0 0 0 17.5 8h-1.8A7 7 0 1 0 4 14.9" /><path d="M12 12v9M8 16l4-4 4 4" /></>,
  utils: <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />,
}

/** The icon of each of the utilities, drawn the same in the list of Utils and in the title of its page. */
export const UTIL_ICONS = {
  timefix: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  repair: <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />,
  sync: <><path d="M21 12a9 9 0 0 0-15.5-6.2L3 8" /><path d="M3 3v5h5" /><path d="M3 12a9 9 0 0 0 15.5 6.2L21 16" /><path d="M16 16h5v5" /></>,
}

/** Where a page hangs from: the section before it, to go back to, and the page itself. */
export function Breadcrumb({ parent, onParent, current }: { parent: string; onParent?: () => void; current: string }) {
  return (
    <nav aria-label="You are here" className="mb-3 flex items-center gap-1.5 text-sm text-zinc-500 dark:text-zinc-400">
      {onParent ? <button type="button" className="hover:text-zinc-900 dark:hover:text-zinc-100 hover:underline" onClick={onParent}>{parent}</button> : <span>{parent}</span>}
      <span aria-hidden="true">›</span>
      <span aria-current="page" className="font-medium text-zinc-900 dark:text-zinc-100">{current}</span>
    </nav>
  )
}

/** The title of a page: the way back to the section it hangs from, the icon, the title and what it is for. */
export function PageHeader({ icon, title, description, parent, onParent, aside }: { icon: ReactNode; title: string; description: ReactNode; parent: string; onParent?: () => void; aside?: ReactNode }) {
  return (
    <>
      <Breadcrumb parent={parent} onParent={onParent} current={title} />
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="w-12 h-12 flex items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300 shrink-0"><LineIcon size={22}>{icon}</LineIcon></span>
          <div>
            <h1 className="text-2xl font-bold">{title}</h1>
            <p className="text-zinc-500 dark:text-zinc-400 text-sm">{description}</p>
          </div>
        </div>
        {aside}
      </header>
    </>
  )
}

/** The title of the page of a task, which hangs from the menu. */
export const SectionHeader = (props: { icon: ReactNode; title: string; description: string; onMenu: () => void }) =>
  <PageHeader icon={props.icon} title={props.title} description={props.description} parent="Menu" onParent={props.onMenu} />

/** A task to choose, in a card of its own: its icon and an arrow on top, then its title and what it does. */
export default function TaskCard({ icon, title, description, onClick, selected = false }: { icon: ReactNode; title: string; description: string; onClick: () => void; selected?: boolean }) {
  return (
    <button type="button" onClick={onClick} aria-pressed={selected} className={`${taskCard} ${selected ? '!border-blue-500 !bg-blue-50 dark:!bg-blue-950/30' : ''} flex flex-col items-stretch gap-3 p-5 text-left`}>
      <span className="flex items-center justify-between">
        <span className="w-10 h-10 flex items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:text-blue-300"><LineIcon>{icon}</LineIcon></span>
        <span className="text-zinc-500 dark:text-zinc-400"><ArrowIcon /></span>
      </span>
      <strong className="text-base text-zinc-900 dark:text-zinc-100">{title}</strong>
      <span className="text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">{description}</span>
    </button>
  )
}
