import { describe, expect, it } from 'vitest'
import { availabilityErrors, cameraAt, cardAt } from './visitAvailability'
import { EMPTY_DEPLOYMENT_FIELDS } from './types'
import type { StoredVisit } from './types'
import type { Visit } from './pages/VisitsPage'

const stored = (over: Partial<StoredVisit>): StoredVisit => ({
  location_id: 'DONA_01', session: 'R0001', date: '2026-06-10', time: '09:00:00', actions: ['Installation'], trappers: null, status: null,
  card_batteries_ok: null, num_photos: null, sd: null, date_time_ok: null, latitude: null, longitude: null, camera_id: null, ...over,
} as StoredVisit)

const visit = (over: Partial<Visit> & { camera?: string }): Visit => ({
  trappers: '', session: '', when: '2026-12-01T09:00:00', site: 'DONA_02', actions: ['Installation'], status: '', card: 'OK', batteries: 'OK', numPhotos: '', sd: '',
  dateTimeOK: 'Yes', longitude: '', latitude: '', details: { ...EMPTY_DEPLOYMENT_FIELDS, camera_id: over.camera ?? null }, ...over,
})

const KEPT = [
  stored({ camera_id: 'C1', sd: 'A1' }),                                                                      // C1 and A1 put up at DONA_01
  stored({ date: '2026-08-01', actions: ['Revision'], camera_id: 'C1', sd: 'A2', num_photos: 100 }),          // A1 collected, A2 left
  stored({ location_id: 'DONA_03', date: '2026-07-01', camera_id: 'C3', sd: 'B1' }),
  stored({ location_id: 'DONA_03', date: '2026-09-01', actions: ['Desinstallation'], camera_id: 'C3', num_photos: 50 }), // C3 taken away with B1
]

describe('where a camera is', () => {
  it('is where it was put up, until it is uninstalled or found stolen', () => {
    expect(cameraAt(KEPT, 'c1', '2026-12-01T00:00:00')).toEqual({ site: 'DONA_01', date: '2026-08-01' })
    expect(cameraAt(KEPT, 'C3', '2026-08-01T00:00:00')).toEqual({ site: 'DONA_03', date: '2026-07-01' })
    expect(cameraAt(KEPT, 'C3', '2026-12-01T00:00:00')).toBeNull()
    expect(cameraAt([...KEPT, stored({ date: '2026-09-15', actions: ['Stolen'], camera_id: 'C1' })], 'C1', '2026-12-01T00:00:00')).toBeNull()
    expect(cameraAt(KEPT, 'NEVER', '2026-12-01T00:00:00')).toBeNull()
  })

  it('counts only the visits before the moment asked', () => {
    expect(cameraAt(KEPT, 'C1', '2026-06-10T09:00:00')).toBeNull() // the installation itself is not before itself
  })
})

describe('where an SD card is', () => {
  it('is in the camera it was left in, until a revision, an uninstallation or a theft collects it', () => {
    expect(cardAt(KEPT, 'A1', '2026-07-01T00:00:00')).toEqual({ site: 'DONA_01', date: '2026-06-10' })
    expect(cardAt(KEPT, 'A1', '2026-12-01T00:00:00')).toBeNull() // collected by the revision
    expect(cardAt(KEPT, 'A2', '2026-12-01T00:00:00')).toEqual({ site: 'DONA_01', date: '2026-08-01' })
    expect(cardAt(KEPT, 'B1', '2026-12-01T00:00:00')).toBeNull() // went with the camera
  })
})

describe('availabilityErrors', () => {
  it('refuses to put up a camera that is installed somewhere else', () => {
    expect(availabilityErrors(KEPT, visit({ camera: 'C1' })).camera).toBe('Camera C1 is installed at DONA_01 (since 2026-08-01): it has to be uninstalled there before it is installed here.')
    expect(availabilityErrors(KEPT, visit({ camera: 'C3' }))).toEqual({}) // it was uninstalled
    expect(availabilityErrors(KEPT, visit({ camera: 'C9' }))).toEqual({})
  })

  it('says a camera is already installed when it is at the very site', () => {
    expect(availabilityErrors(KEPT, visit({ camera: 'C1', site: 'DONA_01' })).camera).toMatch(/already installed here/)
    expect(availabilityErrors(KEPT, visit({ camera: 'C1', site: 'DONA_01', actions: ['Revision', 'Installation'] })).camera).toBeUndefined()
  })

  it('asks nothing of the camera of a visit that does not put one up', () => {
    expect(availabilityErrors(KEPT, visit({ camera: 'C1', actions: ['Revision'] })).camera).toBeUndefined()
    expect(availabilityErrors(KEPT, visit({ camera: 'C1', actions: ['Desinstallation'] })).camera).toBeUndefined()
  })

  it('refuses to leave a card that is in another camera or the one this visit collects, but not one that was collected', () => {
    expect(availabilityErrors(KEPT, visit({ sd: 'A2' })).sd).toBe('SD card A2 is in the camera at DONA_01 (left on 2026-08-01): it has to be collected before it is left here.')
    expect(availabilityErrors(KEPT, visit({ sd: 'A1' }))).toEqual({})
    expect(availabilityErrors(KEPT, visit({ sd: 'A2', site: 'DONA_01', actions: ['Revision'] })).sd).toBe('SD card A2 is the one this visit collects (left on 2026-08-01): the card left in the camera has to be another.')
    expect(availabilityErrors(KEPT, visit({ sd: 'A9', site: 'DONA_01', actions: ['Revision'] }))).toEqual({})
    expect(availabilityErrors(KEPT, visit({ sd: 'A2', site: 'DONA_01', actions: ['Installation'] })).sd).toMatch(/is in the camera at DONA_01/)
  })

  it('looks at where things were on the day of the visit, not today', () => {
    expect(availabilityErrors(KEPT, visit({ camera: 'C1', when: '2026-07-01T09:00:00' })).camera).toMatch(/since 2026-06-10/)
    expect(availabilityErrors(KEPT, visit({ camera: 'C3', when: '2026-08-01T09:00:00' })).camera).toMatch(/installed at DONA_03/)
  })
})
