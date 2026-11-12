import { useState, type KeyboardEvent, type ReactNode } from 'react'
import { ActiveFilters, TABLE, TableCard, TableFooter, TableToolbar } from './DashboardParts'
import SelectionBar from './SelectionBar'
import { Glyph, ViewSwitch, type View } from './ViewSwitch'

export { Glyph }

const PER_PAGE = 10
const CARDS = 8

/** The blue tick of the label that is picked. */
export function PickedTick() {
  return <span className="text-blue-500"><svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6"><circle cx="12" cy="12" r="11" fill="currentColor" /><path d="M7 12.500l3.500 3.500L17 9" fill="none" stroke="white" strokeWidth="2.200" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
}

/** The frame of a label: a button that picks, the one picked marked. */
export function LabelFrame({ picked, name, onPress, children }: { picked: boolean; name: string; onPress: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-pressed={picked} aria-label={`${picked ? 'Let go of' : 'Pick'} ${name}`} onClick={onPress}
            className={`w-full rounded-2xl border p-5 text-left transition-all ${picked ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/30 ring-1 ring-blue-500/50' : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-zinc-300 dark:hover:border-zinc-600 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'}`}>
      {children}
    </button>
  )
}

export interface PickColumn<T> { label: string; cell: (item: T) => ReactNode; className?: string }

/** What a list needs to let many be picked, not one: the keys picked and how they change, which can be picked at all, what the ones picked come to, and the choices of the chevron of the bar. */
export interface PickMany<T> {
  selected: Set<string>
  onChange: (next: Set<string>) => void
  /** Which of the items can be picked: all of them when it is not said. Those that cannot have a box that is off. */
  selectable?: (item: T) => boolean
  /** What the ones picked come to — "24 images" —, told after how many they are. */
  detail?: (picked: T[]) => string
  /** The choices of the chevron, each giving the items it picks out of the ones that match the search; "All results" and "None" when it is not said. */
  choices?: { label: string; pick: (items: T[]) => T[]; showCount?: boolean }[]
  /** What is told of the count: "selected". */
  noun?: string
  disabled?: boolean
}

/** The things to pick from — visits, SD cards — in the table of a dashboard: search, rows, pages, and a button to see them as labels. Pressing a row or a label picks its
 * item, the one picked marked, and pressing it again lets it go. */
export default function PickTable<T>({ items, keyOf, selectedKey = '', onSelect, many, columns, searchText, renderLabel, names, searchPlaceholder, empty = 'Nothing matches.', perPage, optionLabel, filters, total, defaultView = 'table' }: {
  items: T[]; keyOf: (item: T) => string; selectedKey?: string; onSelect?: (item: T | undefined) => void
  /** Many can be picked, not one: the table has a box in each row, and the bar of the selection is over the rows. */
  many?: PickMany<T>
  columns: PickColumn<T>[]
  /** What the search looks at in an item. */
  searchText: (item: T) => string
  /** An item as a label, given what to do when it is pressed and whether it is the one picked. */
  renderLabel: (item: T, picked: boolean, press: () => void) => ReactNode
  /** How it is called: the table (and the group of labels), the search, what the buttons of the view and the foot say of the items, a pick button, and what the field says when it only picks from a list. */
  names: { table: string; search: string; items: string; pick: (item: T) => string; pickPlaceholder: string }
  /** An item as one line of the list the search field picks from. */
  optionLabel: (item: T) => string
  searchPlaceholder: string
  empty?: string
  /** How many go in a page, in the table and in the labels: ten rows and eight labels when it is not said. */
  perPage?: number
  /** The filters already applied to `items` from outside — the revision picked, say —, told in the line of the active filters, and how many there were before them. */
  filters?: { label: string; tone: 'blue' | 'green' }[]
  total?: number
  /** The view it opens on: the table when it is not said; the search field alone is the collapsed one. */
  defaultView?: View
}) {
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const [view, setView] = useState<View>(defaultView)
  // In the view of only the search field: whether its list is open, and the option the keys are on.
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const words = text.toLowerCase().split(/\s+/).filter(Boolean)
  const shown = items.filter((c) => { const line = searchText(c).toLowerCase(); return words.every((w) => line.includes(w)) })
  const size = perPage ?? (view === 'labels' ? CARDS : PER_PAGE)
  const pages = Math.max(1, Math.ceil(shown.length / size)), current = Math.min(page, pages)
  const onPage = shown.slice((current - 1) * size, current * size)
  const canPick = (c: T) => !many || !many.selectable || many.selectable(c)
  const isPicked = (c: T) => (many ? many.selected.has(keyOf(c)) && canPick(c) : keyOf(c) === selectedKey)
  const press = (c: T) => {
    if (many) {
      if (!canPick(c) || many.disabled) return
      const next = new Set(many.selected)
      if (next.has(keyOf(c))) next.delete(keyOf(c)); else next.add(keyOf(c))
      many.onChange(next)
    } else onSelect?.(keyOf(c) === selectedKey ? undefined : c)
  }
  const picked = items.find((c) => keyOf(c) === selectedKey)
  // the bar of the selection: over what matches the search
  const pool = items.filter(canPick), matching = shown.filter(canPick), pickedNow = pool.filter(isPicked)
  const choices = (many?.choices ?? [{ label: 'All results', pick: (x: T[]) => x }, { label: 'None', pick: () => [] as T[], showCount: false }])
  const setPicked = (list: T[]) => many?.onChange(new Set(list.map(keyOf)))
  const searching = view === 'search'
  const choose = (c: T) => { press(c); if (!many) { setOpen(false); setText('') } }
  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (!searching) return
    if (e.key === 'ArrowDown') { e.preventDefault(); if (text.trim() !== '') setOpen(true); setActive((i) => Math.min(i + 1, shown.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && open && text.trim() !== '' && shown[active]) { e.preventDefault(); choose(shown[active]) }
    else if (e.key === 'Escape') setOpen(false)
  }
  return (
    <TableCard label={`${names.table} table`}>
      <TableToolbar searchLabel={names.search} placeholder={searching ? names.pickPlaceholder : searchPlaceholder} onReset={() => { setText(''); setPage(1); setOpen(false) }}
        text={searching && !open && picked && text === '' ? optionLabel(picked) : text} onText={(t) => { setText(t); setPage(1); if (searching) { setOpen(true); setActive(0) } }}
        trailing={<ViewSwitch view={view} items={names.items} onChange={(v) => { setView(v); setPage(1); setOpen(false) }} />}
        onSearchBlur={() => setOpen(false)} onSearchKeyDown={onKey} />
      {searching && open && text.trim() !== '' && (
        <ul role="listbox" aria-label={names.table} className="max-h-64 overflow-y-auto border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 py-1 text-sm">
          {shown.map((c, i) => (
            <li key={keyOf(c)} role="option" aria-selected={isPicked(c)} aria-disabled={!canPick(c) || undefined} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(c)}
                className={`cursor-pointer px-4 py-2 font-mono text-xs ${i === active ? 'bg-blue-50 dark:bg-zinc-800' : ''} ${isPicked(c) ? 'font-bold text-blue-700 dark:text-blue-300' : canPick(c) ? 'text-zinc-800 dark:text-zinc-200' : 'text-zinc-400 dark:text-zinc-600'}`}>{many && isPicked(c) ? '✓ ' : ''}{optionLabel(c)}</li>
          ))}
          {shown.length === 0 && <li className="px-4 py-2 text-xs text-zinc-500 dark:text-zinc-400">{empty}</li>}
        </ul>
      )}
      {many && (
        <SelectionBar total={pool.length} selected={pickedNow.length} detail={many.detail?.(pickedNow)} disabled={many.disabled} noun={many.noun}
          onToggleAll={() => setPicked(matching.length > 0 && matching.every(isPicked) ? [] : matching)} onClear={() => setPicked([])}
          choices={choices.map((c) => ({ label: c.label, count: c.showCount === false ? undefined : c.pick(matching).length, disabled: c.showCount === false ? false : c.pick(matching).length === 0, onPick: () => setPicked(c.pick(matching)) }))} />
      )}
      {!searching && (
        <ActiveFilters filters={[...(filters ?? []), { label: `Search: ${text.trim() ? `“${text.trim()}”` : 'None'}`, tone: 'green' }]} summary={`${shown.length} of ${total ?? items.length} ${names.items} match`} />
      )}
      {searching ? null : view === 'table' ? (
        <div className="overflow-x-auto">
          <table className={TABLE.table} aria-label={names.table}>
            <thead className={TABLE.head}>
              <tr>
                <th scope="col" className="w-10 px-2 py-3"><span className="sr-only">{many ? 'Selected' : 'Pick'}</span></th>
                {columns.map((col) => <th key={col.label} scope="col" className={TABLE.th}>{col.label}</th>)}
              </tr>
            </thead>
            <tbody className={TABLE.body}>
              {onPage.map((c) => {
                const key = keyOf(c), picked = isPicked(c)
                return (
                  <tr key={key} className={`${TABLE.row(picked)} ${many && !canPick(c) ? '' : 'cursor-pointer'}`} onClick={() => press(c)}>
                    <td className={`w-10 border-l-2 px-2 py-3 text-center ${picked ? 'border-l-blue-500' : 'border-l-transparent'}`}>
                      {many ? (
                        <input type="checkbox" aria-label={names.pick(c)} checked={picked} disabled={!canPick(c) || many.disabled} onClick={(e) => e.stopPropagation()} onChange={() => press(c)} />
                      ) : (
                        <button type="button" aria-pressed={picked} aria-label={`${picked ? 'Let go of' : 'Pick'} ${names.pick(c)}`} title={picked ? 'Let go of this one' : 'Pick this one'}
                                className={`h-4 w-4 rounded-full border-2 align-middle ${picked ? 'border-blue-500 bg-blue-500 ring-2 ring-blue-500/30' : 'border-zinc-400 dark:border-zinc-600'}`} />
                      )}
                    </td>
                    {columns.map((col) => <td key={col.label} className={col.className ?? 'px-4 py-3'}>{col.cell(c)}</td>)}
                  </tr>
                )
              })}
              {onPage.length === 0 && (
                <tr><td colSpan={columns.length + 1} className="px-4 py-6 text-center text-sm font-normal text-zinc-500 dark:text-zinc-400">{empty}</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div role="group" aria-label={names.table} className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
          {onPage.map((c) => <div key={keyOf(c)}>{renderLabel(c, isPicked(c), () => press(c))}</div>)}
          {onPage.length === 0 && <p className="col-span-full py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">{empty}</p>}
        </div>
      )}
      {!searching && shown.length > 0 && <TableFooter from={(current - 1) * size + 1} to={Math.min(current * size, shown.length)} total={shown.length} noun={names.items} page={current} pages={pages} onPage={setPage} />}
    </TableCard>
  )
}
