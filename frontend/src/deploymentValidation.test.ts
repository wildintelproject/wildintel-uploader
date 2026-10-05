import { describe, expect, it } from 'vitest'
import { EMPTY_DEPLOYMENT_FIELDS } from './types'
import type { DeploymentFields } from './types'
import { offsetAt, shownErrors, stampTimezone, validateDeployment } from './deploymentValidation'

const VALID: DeploymentFields = {
  ...EMPTY_DEPLOYMENT_FIELDS, deployment_id: 'dep1', latitude: 52.70442, longitude: 23.84995,
  start_date: '2020-03-01T22:00:00+01:00', end_date: '2020-04-01T22:00:00+02:00',
}

describe('validateDeployment', () => {
  it('accepts a deployment with the standard\'s required fields', () => {
    expect(validateDeployment(VALID, 'Europe/Madrid')).toEqual({})
  })

  it.each(['deployment_id', 'latitude', 'longitude', 'start_date', 'end_date'] as const)('requires %s', (key) => {
    const value = key === 'deployment_id' || key.endsWith('_date') ? '' : null
    const errors = validateDeployment({ ...VALID, [key]: key === 'end_date' ? null : value }, 'Europe/Madrid')
    expect(errors[key]).toBe('Required')
  })

  it('requires a known timezone', () => {
    expect(validateDeployment(VALID, '').timezone).toBe('Required')
    expect(validateDeployment(VALID, 'Mars/Olympus').timezone).toMatch(/Not a known/)
  })

  it('bounds latitude and longitude', () => {
    expect(validateDeployment({ ...VALID, latitude: 91 }, 'Europe/Madrid').latitude).toMatch(/-90 and 90/)
    expect(validateDeployment({ ...VALID, longitude: -181 }, 'Europe/Madrid').longitude).toMatch(/-180 and 180/)
    expect(validateDeployment({ ...VALID, latitude: -90, longitude: 180 }, 'Europe/Madrid')).toEqual({})
  })

  it('needs dates with a timezone designator', () => {
    expect(validateDeployment({ ...VALID, start_date: '2020-03-01T22:00:00' }, 'Europe/Madrid').start_date).toMatch(/valid date/)
    expect(validateDeployment({ ...VALID, start_date: '2020-03-01T22:00:00Z' }, 'Europe/Madrid')).toEqual({})
  })

  it('needs the deployment to start before it ends', () => {
    const errors = validateDeployment({ ...VALID, start_date: '2020-04-01T22:00:00+02:00', end_date: '2020-03-01T22:00:00+01:00' }, 'Europe/Madrid')
    expect(errors.end_date).toBe('Must be later than the start date.')
    expect(errors.start_date).toBeUndefined()
    expect(validateDeployment({ ...VALID, end_date: VALID.start_date }, 'Europe/Madrid').end_date).toMatch(/later than/) // not the same instant either
  })

  it('compares the dates as instants, so their timezone designators count', () => {
    // 10:00 at +05:00 is 05:00 UTC — before 08:00 at +01:00 (07:00 UTC), though 10 > 08 on the clock.
    expect(validateDeployment({ ...VALID, start_date: '2020-03-01T10:00:00+05:00', end_date: '2020-03-01T08:00:00+01:00' }, 'Europe/Madrid')).toEqual({})
    expect(validateDeployment({ ...VALID, start_date: '2020-03-01T08:00:00+01:00', end_date: '2020-03-01T10:00:00+05:00' }, 'Europe/Madrid').end_date).toMatch(/later than/)
  })

  it('does not compare the dates while one of them is missing or has no timezone yet', () => {
    expect(validateDeployment({ ...VALID, end_date: null }, 'Europe/Madrid').end_date).toBe('Required')
    expect(validateDeployment({ ...VALID, start_date: '2020-04-01T22:00:00', end_date: '2020-03-01T22:00:00' }, '').end_date).toBeUndefined()
  })

  it('keeps integer fields whole and within range', () => {
    const errors = validateDeployment({ ...VALID, coordinate_uncertainty: 0, camera_interval: 1.5, camera_tilt: 91, camera_heading: 361 }, 'Europe/Madrid')
    expect(errors.coordinate_uncertainty).toMatch(/at least 1/)
    expect(errors.camera_interval).toMatch(/whole number/)
    expect(errors.camera_tilt).toMatch(/-90 and 90/)
    expect(errors.camera_heading).toMatch(/0 and 360/)
  })

  it('keeps distances non-negative', () => {
    const errors = validateDeployment({ ...VALID, camera_height: -1, detection_distance: -0.5 }, 'Europe/Madrid')
    expect(errors.camera_height).toMatch(/0 or more/)
    expect(errors.detection_distance).toMatch(/0 or more/)
  })

  it('does not allow camera height and depth together', () => {
    const errors = validateDeployment({ ...VALID, camera_height: 1.2, camera_depth: 4.8 }, 'Europe/Madrid')
    expect(errors.camera_height).toMatch(/Not to be combined/)
    expect(errors.camera_depth).toMatch(/Not to be combined/)
  })
})

describe('shownErrors', () => {
  it('leaves out the fields that are only empty', () => {
    expect(shownErrors({ deployment_id: 'Required', latitude: 'Must be between -90 and 90.' })).toEqual({ latitude: 'Must be between -90 and 90.' })
  })
})

describe('timezone designators', () => {
  it('finds the offset in force at that moment', () => {
    expect(offsetAt('Europe/Madrid', '2024-07-01T12:00:00')).toBe('+02:00')
    expect(offsetAt('Europe/Madrid', '2024-12-01T12:00:00')).toBe('+01:00')
    expect(offsetAt('UTC', '2024-07-01T12:00:00')).toBe('Z')
    expect(offsetAt('America/St_Johns', '2024-12-01T12:00:00')).toBe('-03:30')
    expect(offsetAt('Mars/Olympus', '2024-07-01T12:00:00')).toBeNull()
  })

  it('stamps a local timestamp, replacing any earlier designator', () => {
    expect(stampTimezone('2024-07-01T12:00:00', 'Europe/Madrid')).toBe('2024-07-01T12:00:00+02:00')
    expect(stampTimezone('2024-07-01T12:00:00+02:00', 'Atlantic/Canary')).toBe('2024-07-01T12:00:00+01:00')
    expect(stampTimezone('2024-07-01T12:00:00', '')).toBe('2024-07-01T12:00:00')
    expect(stampTimezone('', 'Europe/Madrid')).toBe('')
  })
})
