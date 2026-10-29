import { useEffect, useRef } from 'react'
import type { FieldDeployment } from '../types'

/** The deployments the visits of a research project say, by collection: the closed ones, and the ones whose camera is still out. */
export default function FieldDeployments({ deployments, highlight }: { deployments: FieldDeployment[]; highlight?: string }) {
  // the one a link of the visit book goes to is shown highlighted, and brought into view
  const marked = useRef<HTMLTableRowElement | null>(null)
  useEffect(() => { marked.current?.scrollIntoView?.({ block: 'center' }) }, [highlight, deployments])
  const collections = [...new Set(deployments.map((d) => d.collection))]
  return (
    <div aria-label="Deployments the visits say" role="region" className="space-y-3">
      {deployments.length === 0 && <p className="text-sm text-zinc-500 dark:text-zinc-400">No deployment yet: no visit has left a camera.</p>}
      {collections.map((collection) => (
        <div key={collection} className="rounded-xl border border-zinc-200 dark:border-zinc-700 overflow-x-auto">
          <p className="px-4 py-2 text-sm font-semibold bg-zinc-50 dark:bg-zinc-800">
            <span className="font-mono">{collection}</span> · {deployments.filter((d) => d.collection === collection && d.status === 'closed').length} closed · {deployments.filter((d) => d.collection === collection && d.status === 'open').length} still out
          </p>
          <table className="w-full text-sm">
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
              {deployments.filter((d) => d.collection === collection).map((d) => (
                <tr key={d.deployment_id} ref={d.deployment_id === highlight ? marked : undefined} aria-current={d.deployment_id === highlight ? 'true' : undefined} className={d.deployment_id === highlight ? 'bg-blue-50 dark:bg-blue-950/40' : ''}>
                  <td className="px-4 py-2 font-mono">{d.deployment_id}</td>
                  <td className="px-3 py-2"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${d.status === 'closed' ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' : 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300'}`}>{d.status === 'closed' ? 'Closed' : 'Camera still out'}</span></td>
                  <td className="px-3 py-2 font-mono text-xs">{d.start.slice(0, 16).replace('T', ' ')} → {d.end ? d.end.slice(0, 16).replace('T', ' ') : '…'}</td>
                  <td className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400">{[d.camera_id && `camera ${d.camera_id}`, d.card && `card ${d.card}`, d.photos_counted != null && `${d.photos_counted} photos`, d.setup_by && `set up by ${d.setup_by}`].filter(Boolean).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}
