import type { SdCard } from '../types'
import PickTable, { Glyph, LabelFrame, PickedTick, type PickColumn, type PickFilter } from './PickTable'

const STATUS: Record<string, { label: string; tone: string }> = {
  planned: { label: 'Planned', tone: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' },
  ready: { label: 'Ready', tone: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
  active: { label: 'Active', tone: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' },
  archived: { label: 'Archived', tone: 'bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-300' },
}
const statusOf = (c: SdCard) => STATUS[c.status ?? 'active'] ?? { label: String(c.status), tone: STATUS.archived.tone }
/** A capacity as gigabytes, to sort by — "64 GB", "1 TB", "512MB" —; the ones with none go first. */
const capacityInGb = (capacity: string | null | undefined) => {
  const m = /([\d.]+)\s*([KMGT]?)B?/i.exec(capacity ?? '')
  return m ? Number(m[1]) * ({ K: 1 / 1048576, M: 1 / 1024, G: 1, T: 1024, '': 1 } as Record<string, number>)[m[2].toUpperCase()] : -1
}

const COLUMNS: PickColumn<SdCard>[] = [
  { label: 'Card', className: 'px-4 py-3 font-mono font-semibold text-zinc-900 dark:text-zinc-200', cell: (c) => c.label, sort: (c) => c.label },
  { label: 'Brand', cell: (c) => c.brand ?? '—', sort: (c) => c.brand ?? '' },
  { label: 'Capacity', className: 'px-4 py-3 font-mono', cell: (c) => c.capacity ?? '—', sort: (c) => capacityInGb(c.capacity) },
  { label: 'Status', sort: (c) => Object.keys(STATUS).indexOf(c.status ?? 'active'), cell: (c) => <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${statusOf(c).tone}`}>{statusOf(c).label}</span> },
]

/** An SD card as a label: its id, its status, and what it is. */
function CardLabel({ card, picked, onPress }: { card: SdCard; picked: boolean; onPress: () => void }) {
  return (
    <LabelFrame picked={picked} name={`the SD card ${card.label}`} onPress={onPress}>
      <span className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-2 font-mono text-lg font-bold text-zinc-900 dark:text-white">
          <span className="text-blue-500"><Glyph className="h-5 w-5"><path d="M7 3h7l4 4v14H7z" /><path d="M10 7v3M13 7v3" /></Glyph></span>{card.label}
        </span>
        <span className="flex items-center gap-2">
          <span className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${statusOf(card).tone}`}>{statusOf(card).label}</span>
          {picked && <PickedTick />}
        </span>
      </span>
      <span className="my-3 block border-t border-zinc-200 dark:border-zinc-700/70" />
      <span className="flex items-center justify-between gap-3 font-mono text-sm text-zinc-600 dark:text-zinc-300">
        <span>{card.brand ?? 'No brand'}</span>
        <span className="font-bold text-zinc-900 dark:text-white">{card.capacity ?? '—'}</span>
      </span>
    </LabelFrame>
  )
}

/** The SD cards of a research project, in the table of a dashboard or as labels: pressing one picks it, and pressing it again lets it go. */
export default function SdCardsTable({ cards, selected, onSelect, empty }: { cards: SdCard[]; selected: string; onSelect: (label: string) => void; empty: string }) {
  // the statuses the cards have, in the order of their life
  const filter: PickFilter<SdCard> = { label: 'Status', valueOf: (c) => statusOf(c).label,
    options: [...new Set(cards.map((c) => statusOf(c).label))].sort((a, b) => Object.values(STATUS).findIndex((s) => s.label === a) - Object.values(STATUS).findIndex((s) => s.label === b)).map((label) => ({ value: label, label })) }
  return (
    <PickTable items={cards} keyOf={(c) => c.label} selectedKey={selected} onSelect={(c) => onSelect(c?.label ?? '')} columns={COLUMNS}
      searchText={(c) => [c.label, c.brand, c.capacity, statusOf(c).label].filter(Boolean).join(' ')}
      renderLabel={(c, picked, press) => <CardLabel card={c} picked={picked} onPress={press} />}
      names={{ table: 'SD cards', search: 'Filter the SD cards', items: 'SD cards', pick: (c) => `the SD card ${c.label}`, pickPlaceholder: 'Select the SD card the images come from…' }}
      optionLabel={(c) => [c.label, [c.brand, c.capacity].filter(Boolean).join(' ')].filter(Boolean).join(' — ')}
      searchPlaceholder="Search by card, brand, capacity…" empty={empty} perPage={4} defaultView="labels" defaultSort="Card" filter={filter} />
  )
}
