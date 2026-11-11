import { useEffect, type ReactNode } from 'react'
import { btnOutline } from '../pages/ImportDeploymentPage'

/** A panel at the right, over the page, as the details of an image are: a title in monospace, a line under it, a Close button, a line, and what it holds. Escape or a press outside closes it. */
export default function SidePanel({ label, title, subtitle, icon, onClose, children }: { label: string; title: string; subtitle?: ReactNode; onClose: () => void; children: ReactNode
  /** An icon beside the title. */
  icon?: ReactNode }) {
  useEffect(() => {
    const close = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={label}>
      <button type="button" aria-label="Close the details" tabIndex={-1} className="absolute inset-0 cursor-default bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-y-auto border-l border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-6 shadow-2xl">
        <div className="mb-2 flex items-start justify-between gap-3 border-b border-zinc-200 dark:border-zinc-700 pb-4">
          <div className="min-w-0">
            <h4 className="flex items-center gap-2 font-mono text-lg font-bold break-all text-zinc-900 dark:text-zinc-100">{icon && <span aria-hidden="true" className="shrink-0 text-blue-500">{icon}</span>}{title}</h4>
            {subtitle && <p className="text-sm text-zinc-500 dark:text-zinc-400">{subtitle}</p>}
          </div>
          <button type="button" className={`${btnOutline} !px-3 !py-1.5`} onClick={onClose}>Close</button>
        </div>
        {children}
      </aside>
    </div>
  )
}
