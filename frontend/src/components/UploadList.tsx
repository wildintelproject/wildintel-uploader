import { formatDay } from '../dateFormat'
import type { UploadEntry } from '../types'
import { destinationLabel } from '../uploadDestinations'

const when = (iso: string) => `${formatDay(iso, true)}, ${iso.slice(11, 16)}`

/** What an upload did, in a few words: how many packages, and whether its location and its deployment were created there. */
function whatItDid(u: UploadEntry): string {
  const parts = u.parts != null ? `${u.parts} ${u.parts === 1 ? 'package' : 'packages'}` : ''
  const made = [u.location_created && 'location', u.deployment_created && 'deployment'].filter(Boolean).join(' and ')
  return [parts, made && `${made} created there`].filter(Boolean).join(' · ')
}

/** The uploads of a deployment, as a list: where it went, when, what it did there, and a link to reach it on the platform. */
export default function UploadList({ deployment, uploads }: { deployment: string; uploads: UploadEntry[] }) {
  return (
    <ul aria-label={`Uploads of ${deployment}`} className="space-y-2 text-sm">
      {uploads.map((u) => (
        <li key={u.destination} className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="min-w-[6rem] font-semibold">{destinationLabel(u.destination)}</span>
          <span className="text-zinc-600 dark:text-zinc-300">
            {u.uploaded_at ? `Uploaded on ${when(u.uploaded_at)}` : 'It came from there: it was not sent from here'}
            {whatItDid(u) && ` · ${whatItDid(u)}`}
          </span>
          {u.url && <a href={u.url} target="_blank" rel="noreferrer" aria-label={`Open ${deployment} in ${destinationLabel(u.destination)}`} className="text-blue-600 dark:text-blue-400 hover:underline">Open in {destinationLabel(u.destination)} ↗</a>}
        </li>
      ))}
    </ul>
  )
}
