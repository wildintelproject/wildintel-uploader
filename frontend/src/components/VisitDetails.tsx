import type { ReactNode } from 'react'
import { daysBetween } from '../dateFormat'
import type { StoredVisit } from '../types'
import { btnOutline } from '../pages/ImportDeploymentPage'
import SidePanel from './SidePanel'

/** A labelled value: the label in small capitals, the value under it. */
function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? 'col-span-2' : undefined}>
      <dt className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-1 font-mono text-sm text-zinc-900 dark:text-zinc-100 break-words">{children}</dd>
    </div>
  )
}

/** How something was found, as a pill: fine in green, a thing to look at in amber, a thing that went wrong in red. */
function Pill({ value }: { value: string }) {
  const fine = /^(ok|working|yes)$/i.test(value), look = /^(cardfull|altered)$/i.test(value)
  const tone = fine ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300' : look ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300' : 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300'
  return <span className={`inline-flex items-center rounded-full px-3 py-1 font-sans text-xs font-semibold ${tone}`}>{value}</span>
}

/** A box with what the visit noted. */
function Notes({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 px-4 py-3">
      <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Notes</p>
      <p className="mt-1 font-mono text-sm text-zinc-900 dark:text-zinc-100 break-words">{children}</p>
    </div>
  )
}

/** One of the two visits on the line: its marker, its title and revision, and what it says. */
function Stage({ title, visit, kind, children }: { title: string; visit: StoredVisit; kind: 'left' | 'collected'; children: ReactNode }) {
  return (
    <section aria-label={title} className="relative pl-10">
      <span aria-hidden="true" className={`absolute left-0 top-1 h-4 w-4 rounded-full ${kind === 'left' ? 'border-2 border-zinc-400 dark:border-zinc-500 bg-white dark:bg-zinc-900' : 'bg-emerald-400'}`} />
      <div className="flex items-center justify-between gap-3">
        <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h5>
        <span className="rounded-lg border border-purple-500/30 bg-purple-500/10 px-2.5 py-0.5 font-mono text-xs text-purple-700 dark:text-purple-300">{visit.session}</span>
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  )
}

/** Everything else a visit can say, in the order the details have always shown it: each with the name it is told by. */
const MORE: [keyof StoredVisit, string][] = [
  ['setup_by', 'Set up by'], ['camera_model', 'Camera model'], ['sd', 'SD card left'], ['camera_status', 'Status of the camera'], ['battery_status', 'Batteries'], ['card_status', 'SD card status'],
  ['calibration', 'Camera calibrated'], ['latitude', 'Latitude'], ['longitude', 'Longitude'], ['camera_interval', 'Camera delay (s)'], ['camera_height', 'Camera height (m)'], ['camera_depth', 'Camera depth (m)'],
  ['camera_tilt', 'Camera tilt (°)'], ['camera_heading', 'Camera heading (°)'], ['detection_distance', 'Detection distance (m)'], ['timestamp_issues', 'Photo dates may be wrong'], ['bait_use', 'Bait use'],
  ['feature_type', 'Feature type'], ['habitat', 'Habitat'], ['deployment_groups', 'Deployment groups'], ['tags', 'Tags'], ['actions', 'Actions'], ['when', 'Instant (UTC)'], ['deployment_id', 'Deployment imported'],
]
const told = (v: unknown) => (typeof v === 'boolean' ? (v ? 'Yes' : 'No') : Array.isArray(v) ? v.join(', ') : String(v))

/** The rest of what a visit says — every field with something in it that the cards above do not tell —, so that nothing the visit holds is left out. */
function MoreData({ visit, shown }: { visit: StoredVisit; shown: (keyof StoredVisit)[] }) {
  const lines = MORE.filter(([k]) => !shown.includes(k)).map(([k, label]) => [label, visit[k]] as const)
    .filter(([, v]) => v !== null && v !== undefined && v !== '' && !(Array.isArray(v) && v.length === 0))
  if (lines.length === 0) return null
  return (
    <div className="border-t border-zinc-200 dark:border-zinc-700/70 pt-4">
      <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">More data</p>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">{lines.map(([label, v]) => <Field key={label} label={label}>{told(v)}</Field>)}</dl>
    </div>
  )
}

const when = (v: StoredVisit) => `${v.date} ${v.time.slice(0, 5)}`

/** The icon of a visit: the book the visits are kept in, as the visit dashboard has it. */
const VISIT_ICON = (
  <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>
)

/** Everything a closed visit says — the visit that left the card and the one that collected it, on a line of the days between them — in a panel at the right, as the details of an image are. */
export default function VisitDetails({ closed, onClose, onOpenVisit }: { closed: { visit: StoredVisit; end?: StoredVisit | null }; onClose: () => void
  /** Goes to the visit — the one that left the card, or the one that collected it — in the dashboard of the visits: a button under each, when it is given. */
  onOpenVisit?: (session: string) => void }) {
  const { visit, end } = closed
  const days = end ? daysBetween(visit.date, end.date) : null
  const coordinates = visit.latitude != null && visit.longitude != null ? `${visit.latitude}, ${visit.longitude}` : null
  const camera = [visit.camera_id, visit.camera_model].filter(Boolean).join(' · ')
  return (
    <SidePanel label={`Details of the visit ${visit.session} to ${visit.location_id}`} title={visit.location_id} icon={VISIT_ICON} subtitle={end ? `${visit.session} · ${when(visit)} → ${end.date}` : `${visit.session} · ${when(visit)} · the camera is still out`} onClose={onClose}>
      <div className="relative mt-6">
        <span aria-hidden="true" className="absolute bottom-2 left-[7px] top-3 w-px bg-zinc-300 dark:bg-zinc-700" />
        <Stage title="The visit that left the card" visit={visit} kind="left">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
            <Field label="When">{when(visit)}</Field>
            {visit.trappers && <Field label="Who went">{visit.trappers}</Field>}
            <Field label="Location">{visit.location_id}</Field>
            {coordinates && <Field label="Coordinates">{coordinates}</Field>}
            {camera && <Field label="Camera">{camera}</Field>}
            {visit.sd && <Field label="SD card">{visit.sd}</Field>}
            {visit.num_photos != null && <Field label="Photos counted">{visit.num_photos.toLocaleString('en-US')}</Field>}
          </dl>
          {visit.comments && <Notes>{visit.comments}</Notes>}
          <MoreData visit={visit} shown={['trappers', 'latitude', 'longitude', 'camera_id', 'camera_model', 'sd', 'num_photos', 'comments', 'date_time_ok']} />
          {onOpenVisit && <button type="button" className={btnOutline} onClick={() => onOpenVisit(visit.session)}>Open visit {visit.session} <span aria-hidden="true">→</span></button>}
        </Stage>
        {end && (
          <>
            <div className="relative my-5 pl-10">
              {days !== null && <span className="inline-block rounded-full border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/60 px-3 py-1 text-xs text-zinc-500 dark:text-zinc-400">{days === 1 ? '1 day' : `${days} days`} in the field</span>}
            </div>
            <Stage title="The visit that collected it" visit={end} kind="collected">
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
                <Field label="When">{when(end)}</Field>
                {end.trappers && <Field label="Who went">{end.trappers}</Field>}
              </dl>
              {end.num_photos != null && (
                <div className="flex items-center gap-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800/50 px-4 py-3">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6 shrink-0 fill-none stroke-emerald-500" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="8.500" cy="10" r="1.500" /><path d="M21 16l-5-5-8 8" /></svg>
                  <div>
                    <p className="text-[11px] font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Photos</p>
                    <p className="font-mono text-2xl font-bold text-emerald-600 dark:text-emerald-400">{end.num_photos.toLocaleString('en-US')} photos</p>
                  </div>
                </div>
              )}
              {(end.camera_status || end.battery_status || end.card_status || end.date_time_ok) && (
                <dl className="grid grid-cols-[repeat(auto-fit,minmax(6.5rem,1fr))] gap-x-4 gap-y-3">
                  {end.camera_status && <Field label="Camera"><Pill value={end.camera_status} /></Field>}
                  {end.battery_status && <Field label="Batteries"><Pill value={end.battery_status} /></Field>}
                  {end.card_status && <Field label="SD card"><Pill value={end.card_status} /></Field>}
                  {end.date_time_ok && <Field label="Camera date & time OK"><Pill value={end.date_time_ok} /></Field>}
                </dl>
              )}
              {end.comments && <Notes>{end.comments}</Notes>}
            <MoreData visit={end} shown={['trappers', 'num_photos', 'camera_status', 'battery_status', 'card_status', 'date_time_ok', 'comments']} />
            {onOpenVisit && <button type="button" className={btnOutline} onClick={() => onOpenVisit(end.session)}>Open visit {end.session} <span aria-hidden="true">→</span></button>}
            </Stage>
          </>
        )}
      </div>
    </SidePanel>
  )
}
