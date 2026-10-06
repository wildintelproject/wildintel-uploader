import type { ComponentProps } from 'react'
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
    writeTimestampLog: vi.fn(), validateDeployment: vi.fn(), previousDeployments: vi.fn(), existingDeployments: vi.fn(), collectionPath: vi.fn(), importLocal: vi.fn(), openFolder: vi.fn(),
    trapperGetConfig: vi.fn(), trapperTestConnection: vi.fn(), trapperResearchProjects: vi.fn(), nextRevision: vi.fn(),
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
  camera_model: images ? 'Reconyx HC600' : null, camera_id: null as string | null, warnings: [] as string[], from_timestamp_log: false, log_deployment_id: null as string | null,
})

const SCAN: SessionScan = {
  deployments: [
    scanned('DONA_01', 10, '2024-09-04T13:10:00', '2024-11-04T14:28:00'),
    scanned('DONA_02', 5, '2024-09-05T09:00:00', '2024-11-05T10:00:00'),
    scanned('EMPTY', 0, null, null),
  ],
  loose_files: 0, warnings: [], timestamp_log: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  pageProps = {}
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
  mockedApi.trapperGetConfig.mockResolvedValue({ base_url: 'https://trapper.example.org', user_name: 'alice@example.org', has_password: true })
  mockedApi.existingDeployments.mockResolvedValue({ results: {} })
  mockedApi.nextRevision.mockRejectedValue(new Error('no suggestion'))  // the revision stays to be typed, unless a test says otherwise
  mockedApi.previousDeployments.mockResolvedValue({ results: {} })
})

// Props the page is rendered with — reset for every test.
let pageProps: ComponentProps<typeof ImportSessionPage> = {}

async function scanSession() {
  render(<ImportSessionPage {...pageProps} />)
  await userEvent.click(screen.getByRole('button', { name: 'Browse…' }))
  await screen.findByDisplayValue('/s')
  await userEvent.click(screen.getByRole('button', { name: 'Scan' }))
  await screen.findByRole('checkbox', { name: 'DONA_01' })
}

const next = () => userEvent.click(screen.getByRole('button', { name: 'Continue' }))

async function pickProject() {
  await userEvent.click(await screen.findByLabelText('Research project'))
  await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
}

async function toOrigin() {
  await scanSession()
  await next() // validate
  await next() // origin
  await pickProject()
}

async function toDetails() {
  await toOrigin()
  await next()
  fireEvent.change(await screen.findByLabelText('What revision number are you importing?'), { target: { value: '3' } })
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

  describe('the research project', () => {
    async function openOrigin() {
      await scanSession()
      await next()
      await next()
      await screen.findByLabelText('Research project')
    }

    it('is picked from a list that filters as you type, like in Import deployment, and can be cleared', async () => {
      mockedApi.listResearchProjects.mockResolvedValue({ results: [DONA, { ...DONA, name: 'Tatra', acronym: 'TATR' }] })
      await openOrigin()
      await userEvent.type(screen.getByLabelText('Research project'), 'tat')

      expect(screen.queryByRole('option', { name: 'DONA — Doñana' })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('option', { name: 'TATR — Tatra' }))
      expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled()
      await userEvent.click(screen.getByRole('button', { name: 'Clear research project' }))
      expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
    })

    it('says there is none yet, and offers to add the first one', async () => {
      mockedApi.listResearchProjects.mockResolvedValue({ results: [] })
      await openOrigin()

      expect(screen.getByText(/has no research projects yet — add the first one/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Add a new research project/ })).toBeInTheDocument()
    })

    it('adds one by hand with Trapper’s own fields, and picks it', async () => {
      mockedApi.listResearchProjects.mockResolvedValue({ results: [] })
      mockedApi.saveResearchProject.mockImplementation(async (p) => p)
      await openOrigin()
      await userEvent.click(screen.getByRole('button', { name: /Add a new research project/ }))
      await userEvent.click(screen.getByRole('button', { name: /By hand/ }))
      fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Doñana' } })
      fireEvent.change(screen.getByLabelText('Acronym'), { target: { value: 'DONA' } })
      fireEvent.change(screen.getByLabelText('Event interval'), { target: { value: '120' } })
      expect(screen.getByLabelText('Sampling design')).toBeInTheDocument()
      expect(screen.getByLabelText('Keywords')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Save research project' }))

      await waitFor(() => expect(mockedApi.saveResearchProject).toHaveBeenCalledWith(expect.objectContaining({ name: 'Doñana', acronym: 'DONA', event_interval: 120, trapper_pk: null })))
      expect(await screen.findByLabelText('Research project')).toHaveValue('DONA — Doñana')
      expect(screen.getByRole('button', { name: 'Continue' })).toBeEnabled()
    })

    it('adds the ones ticked in Trapper, and picks the first', async () => {
      mockedApi.listResearchProjects.mockResolvedValue({ results: [] })
      mockedApi.trapperTestConnection.mockResolvedValue({ ok: true, research_projects_count: 2 })
      mockedApi.trapperResearchProjects.mockResolvedValue({ results: [{ pk: 2, name: 'Doñana', acronym: 'DONA' }, { pk: 3, name: 'Tatra', acronym: 'TATR' }] })
      mockedApi.saveResearchProject.mockImplementation(async (p) => p)
      await openOrigin()
      await userEvent.click(screen.getByRole('button', { name: /Add a new research project/ }))
      await userEvent.click(screen.getByRole('button', { name: /From Trapper/ }))
      await userEvent.click(screen.getByRole('button', { name: 'Test Connection' }))
      await userEvent.click(await screen.findByRole('checkbox', { name: 'DONA — Doñana' }))
      await userEvent.click(screen.getByRole('checkbox', { name: 'TATR — Tatra' }))
      await userEvent.click(screen.getByRole('button', { name: 'Add 2 research projects' }))

      await waitFor(() => expect(mockedApi.saveResearchProject).toHaveBeenCalledTimes(2))
      expect(await screen.findByLabelText('Research project')).toHaveValue('DONA — Doñana')
    })
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

  it('says in the details when the dates come from the collection’s FileTimestampLog', async () => {
    mockedApi.scanSession.mockResolvedValue({
      ...SCAN,
      deployments: [{ ...SCAN.deployments[0], start_date: '2024-09-01T08:00:00', end_date: '2024-11-01T09:00:00', from_timestamp_log: true }, SCAN.deployments[1], SCAN.deployments[2]],
      timestamp_log: { name: 'S_FileTimestampLog.csv', path: '/s/S_FileTimestampLog.csv', rows: 1, matched: 1, revision: null },
    })
    await toDetails()
    expect(await screen.findByText(/deployment\(s\) were taken from/)).toHaveTextContent('1 of these 2 deployment(s) were taken from S_FileTimestampLog.csv')
    expect(screen.getByText(/^The dates were taken from/)).toBeInTheDocument()
    expect(screen.queryByText(/guessed from the images/)).not.toBeInTheDocument()
  })

  describe('the next revision', () => {
    const toSuggested = async () => { await toOrigin(); await next() }

    it('suggests the highest next revision of the deployments’ locations, says so, and keeps what is typed', async () => {
      mockedApi.nextRevision.mockImplementation(async (_project, location) => (location === 'DONA_01' ? { last: 2, next: 3 } : { last: 4, next: 5 }))
      await toSuggested()

      await waitFor(() => expect(screen.getByLabelText('What revision number are you importing?')).toHaveValue(5))
      expect(screen.getByText(/Filled in as the next one expected for these locations/)).toBeInTheDocument()
      expect(screen.getByLabelText('Deployment id')).toHaveValue('R0005-DONA_01')

      fireEvent.change(screen.getByLabelText('What revision number are you importing?'), { target: { value: '7' } })
      expect(screen.queryByText(/Filled in as the next one expected/)).not.toBeInTheDocument()
      expect(screen.getByLabelText('Deployment id')).toHaveValue('R0007-DONA_01')
    })

    it('does not ask the timezone nor summer time: it says the location’s', async () => {
      await toSuggested()

      expect(screen.queryByLabelText('Timezone (IANA)')).not.toBeInTheDocument()
      expect(screen.queryByRole('checkbox', { name: /ignore summer time/ })).not.toBeInTheDocument()
      await screen.findByText(/You are entering the details of a deployment taken at location/)
      for (const bold of ['Europe/Madrid', 'ignores']) expect(screen.getAllByText(bold)[0].tagName).toBe('STRONG')
    })
  })

  describe('deducing the revision and the locations', () => {
    // The folders are named nothing like a location: only the log's ids say which one each is.
    const logged = (name: string, id: string) => ({ ...scanned(name, 5, '2024-09-01T08:00:00', '2024-11-01T09:00:00'), from_timestamp_log: true, log_deployment_id: id })
    beforeEach(() => {
      mockedApi.scanSession.mockResolvedValue({
        deployments: [logged('SITE_A', 'R0033-DONA_01'), logged('SITE_B', 'R0033-DONA_02')], loose_files: 0, warnings: [],
        timestamp_log: { name: 'R0033_FileTimestampLog.csv', path: '/s/R0033_FileTimestampLog.csv', rows: 2, matched: 2, revision: 33 },
      })
    })
    const toDeducedDetails = async () => {
      render(<ImportSessionPage {...pageProps} />)
      await userEvent.click(screen.getByRole('button', { name: 'Browse…' }))
      await screen.findByDisplayValue('/s')
      await userEvent.click(screen.getByRole('button', { name: 'Scan' }))
      await screen.findByRole('checkbox', { name: 'SITE_A' })
      await next() // validate
      await next() // origin
      await pickProject()
      await next()
    }

    it('fills in the revision from the ids in the log, says so, and lets it be changed', async () => {
      await toDeducedDetails()
      const field = await screen.findByLabelText('What revision number are you importing?')
      expect(field).toHaveValue(33)
      expect(screen.getByText(/Taken from the deployment ids in R0033_FileTimestampLog.csv/)).toBeInTheDocument()
      expect(screen.getByLabelText('Deployment id')).toHaveValue('R0033-DONA_01')

      fireEvent.change(field, { target: { value: '34' } })
      expect(screen.queryByText(/Taken from the deployment ids/)).not.toBeInTheDocument()
      expect(screen.getByLabelText('Deployment id')).toHaveValue('R0034-DONA_01')
    })

    it('deduces the location from the log’s id when the folder’s name is no help, says so, and lets it be changed', async () => {
      await toDeducedDetails()
      expect(await screen.findByLabelText('Location')).toHaveValue('DONA_01')
      expect(screen.getByText(/of these 2 deployment\(s\) was deduced from the name of their folder or the deployment id in the timestamp log/)).toBeInTheDocument()
      expect(screen.getByText(/Deduced from the deployment id in the timestamp log, R0033-DONA_01/)).toBeInTheDocument()

      await userEvent.selectOptions(screen.getByLabelText('Location'), 'DONA_02')
      expect(screen.queryByText(/Deduced from the deployment id/)).not.toBeInTheDocument()
    })
  })

  it('says a location was deduced from the folder’s name, with no log involved', async () => {
    await toDetails()
    expect(await screen.findByText(/Deduced from the folder's name, DONA_01/)).toBeInTheDocument()
    expect(screen.getByText(/of these 2 deployment\(s\) was deduced from the name of their folder, as it is already registered/)).toBeInTheDocument()
  })

  it('says nothing about a log when the session has none', async () => {
    await toDetails()
    await screen.findByText(/deployment\(s\) complete/)
    expect(screen.queryByText(/FileTimestampLog/)).not.toBeInTheDocument()
  })

  it('does not accept two deployments with the same location', async () => {
    await toDetails()
    await userEvent.click(await screen.findByRole('button', { name: 'DONA_02' }))
    await userEvent.selectOptions(screen.getByLabelText('Location'), 'DONA_01')

    expect(await screen.findByText(/Another deployment of the session has this id/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled()
  })

  it('asks the revision as a question, and explains what it names', async () => {
    await toDetails()

    expect(screen.getByText('Which revision is this?')).toBeInTheDocument()
    expect(screen.getByLabelText('What revision number are you importing?')).toHaveValue(3)
    expect(screen.getByText(/1 for the first visit to these locations/)).toBeInTheDocument()
  })

  it('warns at the revision itself of how many of the deployments already exist', async () => {
    mockedApi.existingDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': `${COLLECTION}/R0003-DONA_01`, 'R0003-DONA_02': `${COLLECTION}/R0003-DONA_02` } })
    await toDetails()

    expect(await screen.findByText(/Revision 3 already has 2 of these 2 deployment\(s\) in the collections folder/)).toBeInTheDocument()
    expect(screen.getByText('R0003-DONA_01, R0003-DONA_02', { selector: 'span' })).toBeInTheDocument()
  })

  it('fills every deployment in from its previous revision as soon as the revision is known, without being asked', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: {
      'R0003-DONA_01': previous('R0002-DONA_01', { habitat: 'Pine forest' }), 'R0003-DONA_02': previous('R0002-DONA_02', { habitat: 'Oak forest' }),
    } })
    await toDetails()

    expect(await screen.findByText(/Filled in 2 of 2 from their previous revision/)).toBeInTheDocument()
    expect(mockedApi.previousDeployments).toHaveBeenCalledWith('DONA', ['R0003-DONA_01', 'R0003-DONA_02'])
    expect(screen.getByLabelText('Habitat')).toHaveValue('Pine forest')
    await userEvent.click(screen.getByRole('button', { name: 'DONA_02' }))
    expect(screen.getByLabelText('Habitat')).toHaveValue('Oak forest')
    expect(screen.getByLabelText('Start date')).toHaveValue('2024-09-05T09:00') // the dates are this revision's own
  })

  it('fills in once: what is typed afterwards is kept, and it says nothing when there is no earlier revision', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': previous('R0002-DONA_01', { habitat: 'Pine forest' }), 'R0003-DONA_02': null } })
    await toDetails()
    await screen.findByText(/Filled in 1 of 2/)
    fireEvent.change(screen.getByLabelText('Habitat'), { target: { value: 'My own habitat' } })
    await userEvent.click(screen.getByRole('button', { name: 'DONA_02' }))
    await userEvent.click(screen.getByRole('button', { name: 'DONA_01' }))

    await waitFor(() => expect(mockedApi.previousDeployments).toHaveBeenCalledTimes(1))
    expect(screen.getByLabelText('Habitat')).toHaveValue('My own habitat')
  })

  it('says which deployments already exist, in the list and in the one being edited', async () => {
    mockedApi.existingDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': `${COLLECTION}/R0003-DONA_01`, 'R0003-DONA_02': null } })
    await toDetails()

    expect(await screen.findByRole('alert')).toHaveTextContent(`${COLLECTION}/R0003-DONA_01`)
    expect(screen.getByRole('alert')).toHaveTextContent('This deployment already exists')
    expect(screen.getAllByText('⚠ Already exists')).toHaveLength(1)
    expect(mockedApi.existingDeployments).toHaveBeenCalledWith('DONA', ['R0003-DONA_01', 'R0003-DONA_02'])
    await userEvent.click(screen.getByRole('button', { name: 'DONA_02' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('needs the revision', async () => {
    await toDetails()
    fireEvent.change(screen.getByLabelText('What revision number are you importing?'), { target: { value: '' } })

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

  it('says in the postvalidation that some checks are customized in the settings, and has no fields for them', async () => {
    await toDetails()
    await next()

    expect(await screen.findByText(/Some of these checks can be customized in the settings \(Settings › Postvalidation\)/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Tolerance (hours)')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Sequence gap (seconds)')).not.toBeInTheDocument()
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
    expect(mockedApi.importLocal.mock.calls[0][4]).toEqual(expect.objectContaining({ rename: true, research_project: 'Doñana' }))
    await userEvent.click(screen.getByRole('button', { name: 'Open folder in file explorer' }))
    expect(mockedApi.openFolder).toHaveBeenCalledWith(COLLECTION)
  })

  it('offers to go on to the upload of the revision’s collection once the session is imported', async () => {
    const onUpload = vi.fn()
    pageProps = { onUpload }
    await toDetails()
    await next() // checks
    await next() // preprocessing
    await next() // import
    expect(screen.queryByRole('button', { name: 'Upload to Trapper' })).not.toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: 'Import 2 deployments' }))

    await screen.findByText(/Session imported — 2 deployment/)
    await userEvent.click(screen.getByRole('button', { name: 'Upload to Trapper' }))
    expect(onUpload).toHaveBeenCalledWith({ researchProjectId: 'DONA', collection: 'R0003' })
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

  it('does not offer to fill in from a previous revision once it is known there is none', async () => {
    mockedApi.previousDeployments.mockResolvedValue({ results: { 'R0003-DONA_01': null, 'R0003-DONA_02': null } })
    await toDetails()
    await waitFor(() => expect(mockedApi.previousDeployments).toHaveBeenCalled())

    await waitFor(() => expect(screen.queryByRole('button', { name: 'Fill all from the previous revision' })).not.toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Fill from the previous revision' })).not.toBeInTheDocument()
  })

  it('does not look for an earlier revision in the first one, which has none', async () => {
    await toDetails()
    fireEvent.change(screen.getByLabelText('What revision number are you importing?'), { target: { value: '1' } })
    await new Promise((resolve) => setTimeout(resolve, 600)) // longer than the wait before looking

    expect(mockedApi.previousDeployments).not.toHaveBeenCalledWith('DONA', expect.arrayContaining(['R0001-DONA_01']))
    expect(screen.queryByRole('button', { name: 'Fill all from the previous revision' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fill from the previous revision' })).not.toBeInTheDocument()
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

  it('does not offer to fill in from a previous revision without a revision', async () => {
    await toDetails()
    fireEvent.change(screen.getByLabelText('What revision number are you importing?'), { target: { value: '' } })

    expect(screen.queryByRole('button', { name: 'Fill all from the previous revision' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Fill from the previous revision' })).not.toBeInTheDocument()
  })

  describe('with a big session', () => {
    const names = Array.from({ length: 66 }, (_, i) => `DONA_${String(i + 1).padStart(2, '0')}`)
    beforeEach(() => {
      mockedApi.scanSession.mockResolvedValue({
        deployments: names.map((n) => scanned(n, 3, '2024-09-04T13:10:00', '2024-11-04T14:28:00')), loose_files: 0, warnings: [], timestamp_log: null,
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
