import { useEffect, useState } from 'react'

/** How far a long step has gone, as it is told in batches: when it started, when the last batch ended and how many items were done by then. */
export interface BatchTiming { start: number; at: number; done: number; total: number }

/** The time left, said plainly: "about 40 s", "about 3 min", "about 1 h 10 min". */
export function timeLeftText(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `about ${Math.max(5, Math.ceil(s / 5) * 5)} s`
  const min = Math.round(s / 60)
  return min < 60 ? `about ${min} min` : `about ${Math.floor(min / 60)} h${min % 60 ? ` ${min % 60} min` : ''}`
}

/** The time left of a step told in batches: as long as the batches took so far for each item, for the items still to do, counted down each second. */
export function timeLeft(t: BatchTiming, now: number): number | null {
  if (t.done <= 0 || t.at <= t.start) return null
  const whole = ((t.at - t.start) / t.done) * t.total
  return Math.max(0, whole - (now - t.start))
}

/** A bar with how many items a long step has done, of how many, and the time left — "Estimating the time left…" until the first batch ends. */
export default function TimeLeftBar({ timing, noun, label }: { timing: BatchTiming; noun: string; label: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(tick)
  }, [])
  const left = timeLeft(timing, now)
  const share = timing.total > 0 ? Math.min(100, (timing.done / timing.total) * 100) : 0
  return (
    <div className="mt-2">
      <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={timing.total} aria-valuenow={timing.done} className="h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
        <div className="h-full bg-blue-500 transition-[width] duration-500" style={{ width: `${share}%` }} />
      </div>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400" aria-live="polite">
        {timing.done.toLocaleString('en-US')} of {timing.total.toLocaleString('en-US')} {noun}
        {' · '}{left === null ? 'estimating the time left…' : `${timeLeftText(left)} left`}
      </p>
    </div>
  )
}
