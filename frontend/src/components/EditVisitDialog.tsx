import { useState } from 'react'
import { api } from '../api'
import type { BookVisit, StoredVisit } from '../types'
import { btnOutline, btnPrimary, inputClass } from '../pages/ImportDeploymentPage'

const ACTIONS = ['Installation', 'Revision', 'Desinstallation', 'Stolen', 'Archive'] as const
const CARD_CODES = ['', 'OK', 'CarFull', 'NoBatteries', 'CarFullNoBatteries'] as const

/** What the book says of a row that is not what a visit keeps. */
const BOOK_ONLY = ['deployment', 'deployment_status', 'deployment_no_images', 'uploaded_at', 'on_trapper', 'not_done', 'not_visited', 'unknown', 'locked', 'state', 'when']

const label = 'block text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-1'

/** Edits a visit that is kept — its site and its revision are its key and do not change — or fills an unknown one, which has nothing yet. The rules of a visit
 * are the server's: what the change would make wrong, in the visit and in the ones after it, is shown as it says it, and nothing is changed. */
export default function EditVisitDialog({ projectId, visit, onClose, onSaved }: { projectId: string; visit: BookVisit; onClose: () => void; onSaved: () => void }) {
  const filling = Boolean(visit.unknown)
  const [form, setForm] = useState({
    date: visit.date || '', time: (visit.time || '').slice(0, 8), actions: filling ? ['Installation'] : [...visit.actions], camera: visit.camera_id ?? '', status: visit.status ?? '',
    card: visit.card_batteries_ok ?? '', photos: visit.num_photos == null ? '' : String(visit.num_photos), sd: visit.sd ?? '', dateTimeOk: visit.date_time_ok ?? '',
    calibration: visit.calibration == null ? '' : visit.calibration ? 'yes' : 'no', trappers: visit.trappers ?? '', comments: visit.comments ?? '',
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }))
  const text = (t: string) => t.trim() || null
  const toggle = (a: string) => set({ actions: form.actions.includes(a) ? form.actions.filter((x) => x !== a) : [...form.actions, a] })
  const ready = Boolean(form.date && form.time) && (form.actions.length > 0 || /not revised/i.test(form.status))

  async function save() {
    setSaving(true); setError(null)
    const kept = Object.fromEntries(Object.entries(visit).filter(([k]) => !BOOK_ONLY.includes(k))) as unknown as StoredVisit
    const stored: StoredVisit = {
      ...(filling ? { location_id: visit.location_id, session: visit.session, tags: [] } : kept) as StoredVisit,
      date: form.date, time: form.time.length === 5 ? `${form.time}:00` : form.time, actions: form.actions as StoredVisit['actions'],
      camera_id: text(form.camera), status: text(form.status), card_batteries_ok: (form.card || null) as StoredVisit['card_batteries_ok'],
      num_photos: form.photos.trim() === '' ? null : Number(form.photos), sd: text(form.sd), date_time_ok: text(form.dateTimeOk),
      calibration: form.calibration === '' ? null : form.calibration === 'yes', trappers: text(form.trappers), comments: text(form.comments),
    }
    try {
      if (filling) await api.saveVisit(projectId, stored)
      else await api.updateVisit(projectId, stored)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the visit.')
      setSaving(false)
    }
  }

  const title = filling ? `Fill in ${visit.session} of ${visit.location_id}` : `Edit ${visit.session} of ${visit.location_id}`
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4" role="presentation">
      <section role="dialog" aria-modal="true" aria-label={title} className="my-8 w-full max-w-2xl rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-6 space-y-5">
        <div>
          <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">{title}</h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            {filling ? 'Nothing is known of this visit yet. What you say here takes the place of the unknown one.' : 'The site and the revision are the key of the visit: they do not change.'}
            {' '}The rules of a visit are checked with the visits before and after it.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className={label} htmlFor="ev-date">Day</label><input id="ev-date" type="date" className={inputClass} value={form.date} onChange={(e) => set({ date: e.target.value })} /></div>
          <div><label className={label} htmlFor="ev-time">Time</label><input id="ev-time" type="time" step={1} className={inputClass} value={form.time} onChange={(e) => set({ time: e.target.value })} /></div>
        </div>
        <fieldset>
          <legend className={label}>What was done</legend>
          <div className="flex flex-wrap gap-2">
            {ACTIONS.map((a) => (
              <button key={a} type="button" aria-pressed={form.actions.includes(a)} onClick={() => toggle(a)} disabled={a === 'Archive' && !filling}
                      className={`px-3 py-1.5 rounded-full text-sm border transition-colors disabled:opacity-50 ${form.actions.includes(a) ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/40' : 'border-zinc-200 dark:border-zinc-700'}`}>{a}</button>
            ))}
          </div>
        </fieldset>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div><label className={label} htmlFor="ev-camera">Camera</label><input id="ev-camera" className={inputClass} value={form.camera} onChange={(e) => set({ camera: e.target.value })} /></div>
          <div><label className={label} htmlFor="ev-sd">SD card left</label><input id="ev-sd" className={inputClass} value={form.sd} onChange={(e) => set({ sd: e.target.value })} /></div>
          <div><label className={label} htmlFor="ev-photos">Photos on the card collected</label><input id="ev-photos" type="number" min={0} className={inputClass} value={form.photos} onChange={(e) => set({ photos: e.target.value })} /></div>
          <div>
            <label className={label} htmlFor="ev-card">Card and batteries</label>
            <select id="ev-card" className={inputClass} value={form.card} onChange={(e) => set({ card: e.target.value })}>
              {CARD_CODES.map((c) => <option key={c} value={c}>{c || 'Not said'}</option>)}
            </select>
          </div>
          <div><label className={label} htmlFor="ev-status">Status of the camera</label><input id="ev-status" className={inputClass} value={form.status} onChange={(e) => set({ status: e.target.value })} /></div>
          <div><label className={label} htmlFor="ev-dtok">Camera date and time OK</label><input id="ev-dtok" className={inputClass} value={form.dateTimeOk} onChange={(e) => set({ dateTimeOk: e.target.value })} /></div>
          <div>
            <label className={label} htmlFor="ev-calibration">Camera calibrated</label>
            <select id="ev-calibration" className={inputClass} value={form.calibration} onChange={(e) => set({ calibration: e.target.value })}>
              <option value="">Not said</option><option value="yes">Yes</option><option value="no">No</option>
            </select>
          </div>
          <div><label className={label} htmlFor="ev-trappers">Who went</label><input id="ev-trappers" className={inputClass} value={form.trappers} onChange={(e) => set({ trappers: e.target.value })} /></div>
        </div>
        <div><label className={label} htmlFor="ev-comments">Notes</label><textarea id="ev-comments" rows={3} className={inputClass} value={form.comments} onChange={(e) => set({ comments: e.target.value })} /></div>
        {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <div className="flex justify-end gap-3">
          <button type="button" className={btnOutline} onClick={onClose}>Cancel</button>
          <button type="button" className={btnPrimary} disabled={!ready || saving} onClick={() => void save()}>{filling ? 'Fill in' : 'Save changes'}</button>
        </div>
      </section>
    </div>
  )
}
