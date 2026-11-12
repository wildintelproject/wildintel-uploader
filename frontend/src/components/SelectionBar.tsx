import { useEffect, useRef, useState } from 'react'

export interface SelectionChoice {
  label: string
  /** How many it picks: told at the right of the choice. */
  count?: number
  onPick: () => void
  disabled?: boolean
}

/** The bar of a list that lets many be picked, as a mailbox has it: a box that picks all of them or none — with a dash when only some are picked —, a chevron with the choices
 * (all the results, the ones not uploaded, none), what is picked — "1 of 3 selected · 24 images" — and, at the right, the way to clear the selection. */
export default function SelectionBar({ total, selected, detail, choices, onToggleAll, onClear, disabled = false, noun = 'selected' }: {
  /** How many can be picked. */
  total: number
  /** How many are. */
  selected: number
  /** What the ones picked come to — "24 images" —, after the count. */
  detail?: string
  /** The choices of the chevron. */
  choices: SelectionChoice[]
  /** The box: picks all when not all are picked, and none when they are. */
  onToggleAll: () => void
  onClear: () => void
  disabled?: boolean
  noun?: string
}) {
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false) }
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', key) }
  }, [open])
  const all = total > 0 && selected >= total
  const some = selected > 0 && !all
  return (
    <div ref={box} className={`relative flex flex-wrap items-center gap-3 border-b border-zinc-200 dark:border-zinc-800 px-4 py-3 text-sm ${selected > 0 ? 'bg-blue-50 dark:bg-[#1b2540]' : 'bg-zinc-50 dark:bg-zinc-800/50'}`}>
      <button type="button" role="checkbox" aria-checked={all ? true : some ? 'mixed' : false} aria-label={all ? 'Select none' : 'Select all'} disabled={disabled || total === 0} onClick={onToggleAll}
              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 transition-colors disabled:opacity-50 ${all || some ? 'border-blue-500 bg-blue-500 text-white' : 'border-zinc-400 dark:border-zinc-500 text-transparent'}`}>
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">{all ? <path d="M5 12.5l4.5 4.5L19 7" /> : some ? <path d="M6 12h12" /> : null}</svg>
      </button>
      <button type="button" aria-label="Choose what to select" aria-haspopup="menu" aria-expanded={open} disabled={disabled} onClick={() => setOpen(!open)}
              className="rounded-md p-1 text-zinc-500 dark:text-zinc-300 hover:bg-zinc-200/60 dark:hover:bg-zinc-700/60 disabled:opacity-50">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      <span aria-live="polite" data-selection-count className="text-zinc-900 dark:text-zinc-100">{selected} of {total} {noun}{detail ? <span className="text-zinc-500 dark:text-zinc-400"> · {detail}</span> : null}</span>
      {selected > 0 && (
        <button type="button" disabled={disabled} onClick={onClear} className="ml-auto text-blue-600 dark:text-blue-300 hover:underline disabled:opacity-50">Clear selection</button>
      )}
      {open && (
        <ul role="menu" aria-label="What to select" className="absolute left-3 top-full z-20 mt-1 w-64 overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 py-2 text-base shadow-2xl">
          {choices.map((c) => (
            <li key={c.label} role="none">
              <button type="button" role="menuitem" disabled={c.disabled} onClick={() => { setOpen(false); c.onPick() }}
                      className="flex w-full items-center justify-between gap-4 px-5 py-3 text-left text-zinc-900 dark:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-700/70 disabled:opacity-40">
                <span>{c.label}</span>{c.count !== undefined && <span className="text-sm text-zinc-500 dark:text-zinc-400">{c.count}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
