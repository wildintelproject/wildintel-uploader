import type { ReactNode } from 'react'

/** A line icon, drawn with the stroke of the text colour. */
export function Icon({ path, className }: { path: ReactNode; className: string }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className={`${className} fill-none stroke-current`} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{path}</svg>
}

/** The percentage as a ring. */
export function Ring({ percent }: { percent: number }) {
  const r = 38, c = 2 * Math.PI * r
  return (
    <svg aria-hidden="true" viewBox="0 0 96 96" className="h-20 w-20 shrink-0 -rotate-90">
      <circle cx="48" cy="48" r={r} fill="none" strokeWidth="9" className="stroke-zinc-200 dark:stroke-zinc-700" />
      <circle cx="48" cy="48" r={r} fill="none" strokeWidth="9" strokeLinecap="round" className="stroke-blue-500" strokeDasharray={c} strokeDashoffset={c * (1 - percent / 100)} />
      <text x="48" y="48" textAnchor="middle" dominantBaseline="central" className="fill-current text-[22px] font-semibold" transform="rotate(90 48 48)">{percent}%</text>
    </svg>
  )
}

/** A card of a dashboard that counts one state and, pressed, shows only what is in it. */
export function StateCard({ label, note, count, tone, badge, icon, pressed, onPress }: {
  label: string; note: string; count: number; tone: string; badge: string; icon: ReactNode; pressed: boolean; onPress: () => void
}) {
  return (
    <button type="button" aria-label={label} aria-pressed={pressed} onClick={onPress}
            className={`rounded-2xl border px-4 py-4 text-left transition-colors ${pressed ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-800/60'}`}>
      <span aria-hidden="true" className={`mb-2 flex h-9 w-9 items-center justify-center rounded-full ${badge}`}>{icon}</span>
      <span className={`block text-3xl font-semibold leading-tight ${tone}`}>{count}</span>
      <span className={`block text-sm font-semibold ${tone}`}>{label}</span>
      <span className="block text-xs text-zinc-500 dark:text-zinc-400">{note}</span>
    </button>
  )
}

/** A card of the legend at the foot of a dashboard. */
export function LegendCard({ title, tone, children }: { title: string; tone: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 p-4">
      <h5 className={`mb-1.5 font-semibold ${tone}`}>{title}</h5>
      <div className="text-zinc-500 dark:text-zinc-400">{children}</div>
    </div>
  )
}
