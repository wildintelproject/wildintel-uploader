import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../api'
import ImportSessionPage, { matchLocation } from './ImportSessionPage'
import { EMPTY_DEPLOYMENT_FIELDS, EMPTY_RESEARCH_PROJECT } from '../types'
import type { LocalLocation, LocalResearchProject, SessionScan } from '../types'
import { APP_SETTINGS } from '../test/fixtures'

vi.mock('../api', () => ({
  api: {
    getSettings: vi.fn(), exiftoolStatus: vi.fn(), browseFolder: vi.fn(), scanSession: vi.fn(), validateImages: vi.fn(),
    listResearchProjects: vi.fn(), saveResearchProject: vi.fn(), listLocalLocations: vi.fn(), saveLocalLocation: vi.fn(),
    writeTimestampLog: vi.fn(), validateDeployment: vi.fn(), previousDeployments: vi.fn(), collectionPath: vi.fn(), importLocal: vi.fn(), openFolder: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const COLLECTION = '/home/me/Documents/wildintel-uploader/collections/DONA/R0003'
const DONA: LocalResearchProject = { ...EMPTY_RESEARCH_PROJECT, name: 'Doñana', acronym: 'DONA', trapper_pk: 2 }
const loc = (id: string, over: Partial<LocalLocation> = {}): LocalLocation => ({
  location_id: id, name: null, timezone: 'Europe/Madrid', latitude: 37, longitude: -6.5, coordinate_uncertainty: null, trapper_pk: null, ...over,
})

const scanned = (name: string, images: number, start: string | null, end: string | null) => ({
  name, path: `/s/${name}`, file_count: images, image_count: images, start_date: start, end_date: end,
  camera_model: images ? 'Reconyx HC600' : null, camera_id: null as string | null, warnings: [] as string[],
})

const SCAN: SessionScan = {
  deployments: [
    scanned('DONA_01', 10, '2024-09-04T13:10:00', '2024-11-04T14:28:00'),
    scanned('DONA_02', 5, '2024-09-05T09:00:00', '2024-11-05T10:00:00'),
    scanned('EMPTY', 0, null, null),
  ],
  loose_files: 0, warnings: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.getSettings.mockResolvedValue(APP_SETTINGS)
  mockedApi.exiftoolStatus.mockResolvedValue({ available: true, path: '/usr/bin/exiftool' })
  mockedApi.browseFolder.mockResolvedValue({ path: '/s' })
  mockedApi.scanSession.mockResolvedValue(SCAN)
  mockedApi.validateImages.mockResolvedValue({ checked_count: 10, corrupted: [] })
  mockedApi.listResearchProjects.mockResolvedValue({ results: [DONA] })
  mockedApi.listLocalLocations.mockResolvedValue({ results: [loc('DONA_01'), loc('DONA_02')] })
  mockedApi.writeTimestampLog.mockResolvedValue({ path: '/c/R0003_FileTimestampLog.csv', action: 'added', rows: 1, collection: 'R0003' })
  mockedApi.validateDeployment.mockResolvedValue({ checked_count: 10, deployment_id: { ok: true, message: 'fine' } })
  mockedApi.collectionPath.mockResolvedValue({ path: COLLECTION, collection: 'R0003', exists: false, name: null })
  mockedApi.importLocal.mockImplementation(async (_s, _d, _n, deployment, _p, onEvent) => {
    onEvent({ type: 'done', dest_dir: `${COLLECTION}/${deployment.deployment_id}`, processed: 1, skipped: 0 })
  })
  mockedApi.openFolder.mockResolvedValue({ opened: COLLECTION })
})

async function scanSession() {
  render(<ImportSessionPage />)
  await userEvent.click(screen.getByRole('button', { name: 'Browse…' }))
  await screen.findByDisplayValue('/s')
  await userEvent.click(screen.getByRole('button', { name: 'Scan' }))
  await screen.findByRole('checkbox', { name: 'DONA_01' })
}

const next = () => userEvent.click(screen.getByRole('button', { name: 'Continue' }))

async function toOrigin() {
  await scanSession()
  await next() // validate
  await next() // origin
  await userEvent.selectOptions(await screen.findByLabelText('Research project'), 'DONA')
}

async function toDetails() {
  await toOrigin()
  await next()
  fireEvent.change(await screen.findByLabelText('Revision number'), { target: { value: '3' } })
}

describe('matchLocation', () => {
  const locations = [loc('DONA_01'), loc('DONA_02')]
  it('finds the location a folder is named after', () => {
    expect(matchLocation('dona_01', locations)?.location_id).toBe('DONA_01')
    expect(matchLocation('R0003-DONA_02 (copy)', locations)?.location_id).toBe('DONA_02')
  })
  it('finds none when it is not clear', () => {
    expect(matchLocation('SITE', locations)).toBeUndefined()
    expect(matchLocation('DONA_01 and DONA_02', locations)).toBeUndefined()
  })
})

describe('ImportSessionPage', () => {
  it('lists the session’s subfolders, leaving out the ones with no images', async () => {
    await scanSession()

    expect(screen.getByRole('checkbox', { name: 'DONA_01' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'DONA_02' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'EMPTY' })).not.toBeChecked()
    expect(mockedApi.scanSession).toHaveBeenCalledWith('/s')
  })

  it('cannot go on with no subfolder ticked', async () => {
    await scanSession()
    await userEvent.click(screen.getByRole('checkbox', { name: 'DONA_01' }))
    await userEvent.click(screen.getByRole('checkbox', { name: 'DONA_02' }))

    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('shows why a folder cannot be scanned', async () => {
    mockedApi.scanSession.mockRejectedValue(new Error('This folder has no subfolders'))
    render(<ImportSessionPage />)
    await userEvent.type(screen.getByLabelText('Folder path'), '/empty')
    await userEvent.click(screen.getByRole('button', { name: 'Scan' }))

    expect(await screen.findByText(/no subfolders/)).toBeInTheDocument()
  })

  it('validates every chosen deployment and holds back when a required check fails in one of them', async () => {
    mockedApi.validateImages.mockImplementation(async (path) => ({ checked_count: 5, corrupted: path === '/s/DONA_02' ? [{ path: 'bad.jpg', error: 'truncated' }] : [] }))
    await scanSession()
    await next()
    await userEvent.click(screen.getAllByRole('checkbox', { name: 'Required to continue' })[0]) // corrupted images
    await userEvent.click(screen.getByRole('button', { name: 'Run validation' }))

    await screen.findByText(/1 corrupted image/)
    expect(mockedApi.validateImages.mock.calls.map((c) => c[0])).toEqual(['/s/DONA_01', '/s/DONA_02'])
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('ticks and unticks all the checks to run, or all the required ones, from the table header', async () => {
    await scanSession()
    await next()
    await userEvent.click(screen.getByLabelText('Require all checks'))
    expect(screen.getAllByLabelText('Required to continue').every((b) => (b as HTMLInputElement).checked)).toBe(true)
    await userEvent.click(screen.getByLabelText('Run all checks')) // none run now, so none is required either
    expect(screen.getByLabelText('Require all checks')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled()
    await userEvent.click(screen.getByLabelText('Run all checks'))
    expect(screen.getByLabelText('Require all checks')).not.toBeChecked()
  })

  it('needs a research project before the details', async () => {
    await scanSession()
    await next()
    await next()
    await screen.findByLabelText('Research project')

    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('fills each deployment’s location from its folder name, and its dates from the scan', async () => {
    await toDetails()

    expect(await screen.findByLabelText('Deployment id')).toHaveValue('R0003-DONA_01')
    expect(screen.getByLabelText('Location')).toHaveValue('DONA_01')
    expect(screen.getByLabelText('Start date')).toHaveValue('2024-09-04T13:10')
    await userEvent.click(screen.getByRole('button', { name: 'DONA_02' }))
    expect(screen.getByLabelText('Location')).toHaveValue('DONA_02')
    expect(screen.getByLabelText('Deployment id')).toHaveValue('R0003-DONA_02')
    expect(screen.getByLabelText('Start date')).toHaveValue('2024-09-05T09:00')
    expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled()
  })

  it('does not accept two deployments with the same location', async () => {
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'DONA_02' }))
    await userEvent.selectOptions(screen.getByLabelText('Location'), 'DONA_01')

    expect(await screen.findByText(/Another deployment of the session has this id/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('needs the revision', async () => {
    await toDetails()
    fireEvent.change(screen.getByLabelText('Revision number'), { target: { value: '' } })

    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('adds a location by hand to a deployment', async () => {
    mockedApi.listLocalLocations.mockResolvedValue({ results: [loc('DONA_01')] })
    mockedApi.saveLocalLocation.mockImplementation(async (_rp, location) => location)
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'DONA_02' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add a location' }))
    expect(screen.getByLabelText('Location id')).toHaveValue('DONA_02')
    fireEvent.change(screen.getByLabelText('Location timezone'), { target: { value: 'Europe/Madrid' } })
    fireEvent.change(screen.getByLabelText('Location latitude'), { target: { value: '37.1' } })
    fireEvent.change(screen.getByLabelText('Location longitude'), { target: { value: '-6.4' } })
    await userEvent.click(screen.getByRole('button', { name: 'Save location' }))

    await waitFor(() => expect(screen.getByLabelText('Location')).toHaveValue('DONA_02'))
    expect(mockedApi.saveLocalLocation).toHaveBeenCalledWith('DONA', expect.objectContaining({ location_id: 'DONA_02', latitude: 37.1, longitude: -6.4 }))
  })

  it('writes each deployment’s timestamp log and checks each one after the details', async () => {
    await toDetails()
    await next()
    await userEvent.click(await screen.findByRole('button', { name: 'Run checks' }))

    await waitFor(() => expect(mockedApi.validateDeployment).toHaveBeenCalledTimes(2))
    expect(mockedApi.writeTimestampLog.mock.calls.map((c) => c[1].deployment_id)).toEqual(['R0003-DONA_01', 'R0003-DONA_02'])
    expect(mockedApi.validateDeployment.mock.calls.map((c) => c[1].deployment_id)).toEqual(['R0003-DONA_01', 'R0003-DONA_02'])
    expect(mockedApi.validateDeployment.mock.calls[0][1].start_date).toBe('2024-09-04T13:10:00+02:00')
  })

  it('imports every deployment into the revision’s collection and offers to open it', async () => {
    await toDetails()
    await next() // checks
    await next() // preprocessing
    await next() // import
    await userEvent.click(await screen.findByRole('button', { name: 'Import 2 deployments' }))

    await screen.findByText(/Session imported — 2 deployment/)
    expect(mockedApi.importLocal.mock.calls.map((c) => [c[0], c[1], c[3].deployment_id])).toEqual([
      ['/s/DONA_01', COLLECTION, 'R0003-DONA_01'], ['/s/DONA_02', COLLECTION, 'R0003-DONA_02'],
    ])
    expect(mockedApi.importLocal.mock.calls[0][2]).toBe('R0003')
    expect(mockedApi.importLocal.mock.calls[0][4]).toEqual(expect.objectContaining({ rename: true, timezone: 'Europe/Madrid', research_project: 'Doñana' }))
    await userEvent.click(screen.getByRole('button', { name: 'Open folder in file explorer' }))
    expect(mockedApi.openFolder).toHaveBeenCalledWith(COLLECTION)
  })

  it('goes on past a failed deployment and retries only what is left', async () => {
    let failing = true
    mockedApi.importLocal.mockImplementation(async (_s, _d, _n, deployment, _p, onEvent) => {
      if (failing && deployment.deployment_id.endsWith('01')) throw new Error('disk full')
      onEvent({ type: 'done', dest_dir: `${COLLECTION}/${deployment.deployment_id}`, processed: 1, skipped: 0 })
    })
    await toDetails()
    await next(); await next(); await next()
    await userEvent.click(await screen.findByRole('button', { name: 'Import 2 deployments' }))

    await screen.findByText(/disk full/)
    expect(mockedApi.importLocal).toHaveBeenCalledTimes(2)
    failing = false
    await userEvent.click(screen.getByRole('button', { name: 'Import the 1 left' }))

    await screen.findByText(/Session imported/)
    expect(mockedApi.importLocal).toHaveBeenCalledTimes(3)
    expect(mockedApi.importLocal.mock.calls[2][3].deployment_id).toBe('R0003-DONA_01')
  })

  it('asks the same fields as a single deployment — and sends them with the deployment', async () => {
    await toDetails()
    await userEvent.click(await screen.findByLabelText('Camera setup, habitat, bait and comments'))
    fireEvent.change(screen.getByLabelText('Set up by'), { target: { value: 'Ana' } })
    fireEvent.change(screen.getByLabelText('Comments'), { target: { value: 'Near the pond' } })
    fireEvent.change(screen.getByLabelText('Camera height (m)'), { target: { value: '1.2' } })
    await next(); await next(); await next()
    await userEvent.click(await screen.findByRole('button', { name: 'Import 2 deployments' }))

    await screen.findByText(/Session imported/)
    expect(mockedApi.importLocal.mock.calls[0][3]).toEqual(expect.objectContaining({ setup_by: 'Ana', comments: 'Near the pond', camera_height: 1.2 }))
    expect(mockedApi.importLocal.mock.calls[1][3].setup_by).toBeNull() // each deployment has its own
  })

  const previous = (id: string, over: Record<string, unknown> = {}) => ({
    revision: 1, deployment_id: id,
    deployment: {
      ...EMPTY_DEPLOYMENT_FIELDS, deployment_id: id, location_id: 'X', latitude: 1, longitude: 2,
      start_date: '2024-01-01T00:00:00+01:00', end_date: '2024-02-01T00:00:00+01:00',
      habitat: 'Pine forest', setup_by: 'Ana', comments: 'Near the pond', camera_height: 1.2, tags: ['forest'], timestamp_issues: true, ...over,
    },
  })

  it('fills one deployment from its previous revision, keeping its own id, location and dates', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': previous('R0002-DONA_01') } })
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'Fill from the previous revision' }))

    expect(await screen.findByText('Filled in from R0002-DONA_01.')).toBeInTheDocument()
    expect(mockedApi.previousDeployments).toHaveBeenCalledWith('DONA', ['R0003-DONA_01'])
    expect(screen.getByLabelText('Habitat')).toHaveValue('Pine forest')
    expect(screen.getByLabelText('Set up by')).toHaveValue('Ana')
    expect(screen.getByLabelText('Comments')).toHaveValue('Near the pond')
    expect(screen.getByLabelText('Tags (comma-separated)')).toHaveValue('forest')
    expect(screen.getByLabelText('Deployment id')).toHaveValue('R0003-DONA_01')
    expect(screen.getByLabelText('Location')).toHaveValue('DONA_01')
    expect(screen.getByLabelText('Start date')).toHaveValue('2024-09-04T13:10') // this revision's own
    expect(screen.getByLabelText('Timestamps have issues')).not.toBeChecked() // not carried over
  })

  it('says when there is no previous revision to fill in from', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': null } })
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'Fill from the previous revision' }))

    expect(await screen.findByText(/no previous revision of this deployment/)).toBeInTheDocument()
  })

  it('fills all the deployments at once, each from its own previous revision', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: {
      'R0003-DONA_01': previous('R0002-DONA_01', { habitat: 'Pine forest' }), 'R0003-DONA_02': null,
    } })
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'Fill all from the previous revision' }))

    expect(await screen.findByText(/Filled in 1 of 2 from their previous revision — the other 1 have none/)).toBeInTheDocument()
    expect(mockedApi.previousDeployments).toHaveBeenCalledWith('DONA', ['R0003-DONA_01', 'R0003-DONA_02'])
    expect(screen.getByLabelText('Habitat')).toHaveValue('Pine forest')
    await userEvent.click(screen.getByRole('button', { name: 'DONA_02' }))
    expect(screen.getByLabelText('Location')).toHaveValue('DONA_02')
    expect(screen.queryByLabelText('Habitat')).not.toBeInTheDocument() // nothing filled in, so the form stays closed
  })

  it('does not fill from a previous revision without a revision', async () => {
    await toDetails()
    fireEvent.change(screen.getByLabelText('Revision number'), { target: { value: '' } })

    expect(screen.getByRole('button', { name: 'Fill all from the previous revision' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Fill from the previous revision' })).toBeDisabled()
  })

  describe('with a big session', () => {
    const names = Array.from({ length: 66 }, (_, i) => `DONA_${String(i + 1).padStart(2, '0')}`)
    beforeEach(() => {
      mockedApi.scanSession.mockResolvedValue({
        deployments: names.map((n) => scanned(n, 3, '2024-09-04T13:10:00', '2024-11-04T14:28:00')), loose_files: 0, warnings: [],
      })
      // Only 60 of the 66 folders are named after a location of the project.
      mockedApi.listLocalLocations.mockResolvedValue({ results: names.slice(0, 60).map((n) => loc(n)) })
    })

    it('says how many are complete, and filters the list', async () => {
      await toDetails()

      expect(await screen.findByRole('status')).toHaveTextContent('60 of 66 deployment(s) complete.')
      fireEvent.change(screen.getByLabelText('Filter deployments'), { target: { value: '_6' } })
      const rows = screen.getAllByRole('row').slice(1)
      expect(rows.map((r) => r.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('DONA_60'), expect.stringContaining('DONA_66')]))
      expect(rows).toHaveLength(7) // DONA_06 and DONA_60 to DONA_66
    })

    it('lists only the incomplete ones, and jumps to the next one that is', async () => {
      await toDetails()
      await userEvent.click(await screen.findByLabelText('Only the incomplete ones'))

      expect(screen.getAllByRole('row').slice(1)).toHaveLength(6)
      expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
      await userEvent.click(screen.getByRole('button', { name: 'Next incomplete' }))
      expect(screen.getByRole('group', { name: 'Details of DONA_61' })).toBeInTheDocument()
      await userEvent.selectOptions(screen.getByLabelText('Location'), 'DONA_01')
      expect(await screen.findByText(/Another deployment of the session has this id/)).toBeInTheDocument()
    })
  })
})
