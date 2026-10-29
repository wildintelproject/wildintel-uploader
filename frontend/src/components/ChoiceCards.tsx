import type { ReactNode } from 'react'
import { LineIcon } from './TaskCard'

/** One answer of a question asked with cards: its icon, what it says and, below it, a few words more. */
export interface Choice<V extends string> {
  value: V
  label: string
  description?: string
  icon: ReactNode
  /** The colour of the card when it is the answer: blue, or red for the answers that tell of a loss. */
  tone?: 'blue' | 'red'
}

/** A question answered by pressing a card — one of a few, shown at a size that is easy to press —: the cards are radios, so they are read and used as such.
 * `large` puts them two to a row, with their description; `compact` stacks them, one to a line. */
export default function ChoiceCards<V extends string>({ label, value, choices, onChange, size = 'large' }: {
  label: string
  value: V | null
  choices: Choice<V>[]
  onChange: (value: V) => void
  size?: 'large' | 'compact'
}) {
  const large = size === 'large'
  return (
    <div role="radiogroup" aria-label={label} className={large ? 'grid grid-cols-1 sm:grid-cols-2 gap-3' : 'space-y-2.5'}>
      {choices.map((c) => {
        const on = value === c.value
        const red = c.tone === 'red'
        const accent = red ? 'border-red-500 bg-red-50 dark:bg-red-950/30 shadow-[0_3px_0_0_rgba(239,68,68,0.45)]' : 'border-blue-500 bg-blue-50 dark:bg-blue-950/40 shadow-[0_3px_0_0_rgba(59,130,246,0.45)]'
        return (
          <button
            key={c.value} type="button" role="radio" aria-checked={on} aria-label={c.label} onClick={() => onChange(c.value)}
            className={`group flex w-full items-center gap-3 rounded-xl border text-left transition-all duration-150 active:translate-y-0.5 active:shadow-none ${large ? 'p-4' : 'p-3.5'} ${on ? `${accent} -translate-y-px` : 'border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/60 hover:border-zinc-400 dark:hover:border-zinc-500 hover:-translate-y-0.5'}`}
          >
            <span aria-hidden="true" className={`flex shrink-0 items-center justify-center rounded-lg border ${large ? 'h-10 w-10' : 'h-8 w-8'} ${on ? (red ? 'border-red-300 dark:border-red-800 text-red-600 dark:text-red-400' : 'border-blue-300 dark:border-blue-800 text-blue-600 dark:text-blue-400') : 'border-zinc-200 dark:border-zinc-700 text-zinc-500 dark:text-zinc-400'}`}>
              <LineIcon size={large ? 20 : 16}>{c.icon}</LineIcon>
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-zinc-900 dark:text-zinc-100">{c.label}</span>
              {c.description && <span className="mt-0.5 block text-xs text-zinc-500 dark:text-zinc-400">{c.description}</span>}
            </span>
            <span aria-hidden="true" className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${on ? (red ? 'border-red-500' : 'border-blue-500') : 'border-zinc-400 dark:border-zinc-600'}`}>
              <span className={`h-2.5 w-2.5 rounded-full transition-transform duration-200 ${red ? 'bg-red-500' : 'bg-blue-500'} ${on ? 'scale-100' : 'scale-0'}`} />
            </span>
          </button>
        )
      })}
    </div>
  )
}
