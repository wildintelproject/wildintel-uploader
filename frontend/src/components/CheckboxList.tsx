import { useMemo, useState } from 'react'

const inputClass = 'w-full px-3 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono'

export interface CheckboxListOption {
  value: string
  label: string
}

interface Props {
  /** Accessible name of the filter box, e.g. "Filter Trapper research projects". */
  filterLabel: string
  options: CheckboxListOption[]
  selected: string[]
  onChange: (selected: string[]) => void
  disabled?: boolean
  emptyText: string
}

/** Several options to tick, filtered as you type — for choosing more than one. */
export default function CheckboxList({ filterLabel, options, selected, onChange, disabled = false, emptyText }: Props) {
  const [query, setQuery] = useState('')
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? options.filter((o) => o.label.toLowerCase().includes(q)) : options
  }, [options, query])

  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value])
  }

  return (
    <div>
      <input aria-label={filterLabel} className={`${inputClass} mb-2`} placeholder="Type to filter…" value={query} onChange={(e) => setQuery(e.target.value)} disabled={disabled} />
      <div className="max-h-56 overflow-y-auto rounded border border-zinc-200 dark:border-zinc-700 divide-y divide-zinc-200 dark:divide-zinc-700">
        {options.length === 0 && <p className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">{emptyText}</p>}
        {options.length > 0 && shown.length === 0 && <p className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">Nothing matches.</p>}
        {shown.map((o) => (
          <label key={o.value} className="flex items-center gap-2 px-3 py-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50">
            <input type="checkbox" checked={selected.includes(o.value)} disabled={disabled} onChange={() => toggle(o.value)} />
            {o.label}
          </label>
        ))}
      </div>
    </div>
  )
}
