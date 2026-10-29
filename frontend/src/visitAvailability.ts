/** Where the cameras and the SD cards are, worked out from the visits kept: a camera put up at a site is there until a visit takes it away
 * (a Desinstallation) or finds it stolen; a card left in a camera is there until a visit collects it (a Revision, a Desinstallation, or a
 * stolen camera, which takes its card). So an Installation of a camera, or the leaving of a card, can be told when the camera or the card
 * is somewhere else. */
import type { StoredVisit } from './types'
import type { Visit } from './pages/VisitsPage'

/** Where a camera or a card is, and since when. */
export interface Whereabouts { site: string; date: string }

const same = (a: string | null | undefined, b: string | null | undefined) => (a ?? '').trim().toLowerCase() === (b ?? '').trim().toLowerCase()
const stamp = (v: { date: string; time: string }) => `${v.date}T${v.time}`

/** The visits before a moment, oldest first. */
function before(visits: StoredVisit[], when: string): StoredVisit[] {
  return visits.filter((v) => stamp(v) < when).sort((a, b) => stamp(a).localeCompare(stamp(b)))
}

const takesAway = (v: StoredVisit) => v.actions.includes('Desinstallation') || v.actions.includes('Stolen')
const collectsCard = (v: StoredVisit) => takesAway(v) || v.actions.includes('Revision')

/** The site a camera is put up at on a given moment — null when it is nowhere: never put up, uninstalled or stolen. */
export function cameraAt(visits: StoredVisit[], cameraId: string, when: string): Whereabouts | null {
  let at: Whereabouts | null = null
  for (const v of before(visits, when)) {
    if (!same(v.camera_id, cameraId)) continue
    if (takesAway(v)) at = null
    else if (v.actions.includes('Installation') || v.actions.includes('Revision')) at = { site: v.location_id, date: v.date }
  }
  return at
}

/** The camera that is put up at a site on a given moment — null when none is known: nothing was installed there, or it was taken away or stolen. */
export function cameraAtSite(visits: StoredVisit[], site: string, when: string): { camera: string; date: string } | null {
  let at: { camera: string; date: string } | null = null
  for (const v of before(visits, when)) {
    if (!same(v.location_id, site)) continue
    if (takesAway(v)) at = null
    else if ((v.actions.includes('Installation') || v.actions.includes('Revision')) && v.camera_id) at = { camera: v.camera_id, date: v.date }
  }
  return at
}

/** The site whose camera holds a card on a given moment — null when it is in none: never left, or collected. */
export function cardAt(visits: StoredVisit[], label: string, when: string): Whereabouts | null {
  const inSite = new Map<string, { label: string; date: string; site: string }>()
  for (const v of before(visits, when)) {
    const site = v.location_id.toLowerCase()
    if (collectsCard(v)) inSite.delete(site)
    if (v.sd && (v.actions.includes('Installation') || v.actions.includes('Revision'))) inSite.set(site, { label: v.sd, date: v.date, site: v.location_id })
  }
  for (const card of inSite.values()) if (same(card.label, label)) return { site: card.site, date: card.date }
  return null
}

/** What stops a visit being kept for where its camera or its card is: the camera put up while it is somewhere else, a card left in a camera
 * while it is in another one — or the very one the visit collects. Nothing is said while the visit does not say which. */
export function availabilityErrors(kept: StoredVisit[], visit: Visit): { camera?: string; sd?: string } {
  const errors: { camera?: string; sd?: string } = {}
  const when = visit.when || '9999-12-31T23:59:59'
  const site = visit.site.trim()
  const installs = visit.actions.includes('Installation')
  const revises = visit.actions.includes('Revision')
  const collects = revises || visit.actions.includes('Desinstallation') || visit.actions.includes('Stolen')

  const camera = visit.details.camera_id
  // A visit that does not put a camera up — a Revision, a Desinstallation, a Stolen camera — is of the camera that is at the site.
  if (camera && !installs && collects) {
    const there = cameraAtSite(kept, site, when)
    if (there && !same(there.camera, camera)) {
      errors.camera = `The camera at ${site} is ${there.camera} (since ${there.date}): a ${visit.actions.join(' + ')} is of that camera. If it was replaced, add an Installation to the visit.`
    }
  }
  if (installs && camera) {
    const there = cameraAt(kept, camera, when)
    // A visit that also revises may find the camera in the very site it puts it up at.
    if (there && !(revises && same(there.site, site))) {
      errors.camera = same(there.site, site)
        ? `Camera ${camera} is already installed here (since ${there.date}): it has to be uninstalled first.`
        : `Camera ${camera} is installed at ${there.site} (since ${there.date}): it has to be uninstalled there before it is installed here.`
    }
  }

  const card = visit.sd.trim()
  if ((installs || revises) && card) {
    const there = cardAt(kept, card, when)
    if (there && collects && same(there.site, site)) {
      // The card this visit collects cannot be the one it leaves.
      errors.sd = `SD card ${card} is the one this visit collects (left on ${there.date}): the card left in the camera has to be another.`
    } else if (there) {
      errors.sd = `SD card ${card} is in the camera at ${there.site} (left on ${there.date}): it has to be collected before it is left here.`
    }
  }
  return errors
}
