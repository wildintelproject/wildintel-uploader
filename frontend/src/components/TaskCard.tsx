import type { ReactNode } from 'react'

export const taskCard = 'rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 transition-colors hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer'

/** A line icon (24×24, stroke) in the colour of the text, from the paths it is drawn with. */
export const LineIcon = ({ children, size = 18 }: { children: ReactNode; size?: number }) => (
  <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{children}</svg>
)

export const ArrowIcon = ({ back = false }: { back?: boolean }) => (
  <LineIcon size={16}>{back ? <path d="M19 12H5M11 6l-6 6 6 6" /> : <path d="M5 12h14M13 6l6 6-6 6" />}</LineIcon>
)

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
