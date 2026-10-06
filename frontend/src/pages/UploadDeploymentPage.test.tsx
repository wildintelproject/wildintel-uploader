import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../api'
import UploadDeploymentPage from './UploadDeploymentPage'
import { EMPTY_RESEARCH_PROJECT } from '../types'
import type { LocalResearchProject, UploadCollection, UploadDeploymentInfo, UploadEvent } from '../types'

vi.mock('../api', () => ({
  api: { listResearchProjects: vi.fn(), uploadCollections: vi.fn(), uploadDeployment: vi.fn(), openFolder: vi.fn(), trapperGetConfig: vi.fn(), checkUploadAccess: vi.fn(), checkUploadSelection: vi.fn(), uploadClassificationProjects: vi.fn() },
}))

const mockedApi = vi.mocked(api)

const PROJECT: LocalResearchProject = { ...EMPTY_RESEARCH_PROJECT, name: 'Doñana', acronym: 'DONA', trapper_pk: 2 }

const dep = (id: string, over: Partial<UploadDeploymentInfo> = {}): UploadDeploymentInfo => ({
  deployment_id: id, location_id: id.slice(6), start_date: '2024-09-04T13:10:00+02:00', end_date: '2024-11-04T14:28:00+01:00',
  images: 120, preprocessed: true, uploaded_at: null, ...over,
})

const COLLECTIONS: UploadCollection[] = [
  { name: 'R0001', path: '/c/DONA/R0001', deployments: [dep('R0001-DONA_01', { uploaded_at: '2024-12-01T10:00:00+00:00' })] },
  {
    name: 'R0003', path: '/c/DONA/R0003',
    deployments: [
      dep('R0003-DONA_01'), dep('R0003-DONA_02'),
      dep('R0003-DONA_03', { preprocessed: false, images: 0 }),
      dep('R0003-DONA_04', { uploaded_at: '2025-01-15T09:30:00+00:00' }),
    ],
  },
]

const STEP_EVENTS = (id: string): UploadEvent[] => [
  { type: 'step', step: 'connect', status: 'running', message: 'Connecting to Trapper…' },
  { type: 'step', step: 'connect', status: 'done', message: 'Connected — research project DONA is #2 in Trapper.' },
  { type: 'step', step: 'location', status: 'done', message: `Location ${id.slice(6)} created.` },
  { type: 'step', step: 'deployment', status: 'done', message: `Deployment ${id} was already in Trapper.` },
  { type: 'step', step: 'package', status: 'done', message: '1 package(s) of 120 image(s).' },
  { type: 'upload_progress', file: 'package_2_x_part001.zip', bytes: 5 * 1024 * 1024, total: 20 * 1024 * 1024 },
  { type: 'step', step: 'upload', status: 'done', message: 'Package 1 of 1 uploaded.' },
  { type: 'step', step: 'process', status: 'done', message: 'Trapper is processing the package.' },
  { type: 'step', step: 'wait', status: 'done', message: 'Collection R0003 is in Trapper.' },
  { type: 'done', mode: 'upload', collection: 'R0003', deployment_id: id, location_created: true, deployment_created: false, parts: 1 },
]

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.listResearchProjects.mockResolvedValue({ results: [PROJECT] })
  mockedApi.uploadCollections.mockResolvedValue({ results: COLLECTIONS })
  mockedApi.trapperGetConfig.mockResolvedValue({ base_url: 'https://trapper.example.org', user_name: 'alice@example.org', has_password: true })
  mockedApi.uploadClassificationProjects.mockResolvedValue({ results: [{ pk: 7, name: 'Doñana classification', is_active: true }] })
  mockedApi.uploadDeployment.mockImplementation(async (_rp, _col, id, _mode, onEvent) => { STEP_EVENTS(id).forEach(onEvent) })
  mockedApi.checkUploadSelection.mockResolvedValue({ checks: [
    { check: 'research_project', ok: true, message: 'You have access to the research project DONA (#2) in Trapper.' },
    { check: 'collection', ok: true, message: 'You have access to the collection R0003 (#26): it is already in Trapper, so the upload adds to it.' },
  ] })
})

async function pickCollection(name = 'R0003') {
  render(<UploadDeploymentPage />)
  await userEvent.click(await screen.findByLabelText('Research project'))
  await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
  await userEvent.click(await screen.findByLabelText('Collection'))
  await userEvent.click(await screen.findByRole('option', { name: new RegExp(`^${name}`) }))
}

describe('UploadDeploymentPage', () => {
  it('shows the Trapper account saved in the settings', async () => {
    render(<UploadDeploymentPage />)

    expect(await screen.findByText('alice@example.org')).toBeInTheDocument()
    expect(screen.getByText('https://trapper.example.org')).toBeInTheDocument()
  })

  it('says to set the account up in the settings when there is none, and does not offer to upload', async () => {
    mockedApi.trapperGetConfig.mockResolvedValue({ base_url: null, user_name: null, has_password: false })
    await pickCollection()

    expect(await screen.findByText(/no Trapper account saved yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Upload \d+ deployment/ })).toBeDisabled()
  })

  it('also needs the password saved, not just the URL and the user', async () => {
    mockedApi.trapperGetConfig.mockResolvedValue({ base_url: 'https://trapper.example.org', user_name: 'alice@example.org', has_password: false })
    await pickCollection()

    expect(screen.getByRole('button', { name: /^Upload \d+ deployment/ })).toBeDisabled()
  })

  it('says so when the collections folder has no research projects yet', async () => {
    mockedApi.listResearchProjects.mockResolvedValue({ results: [] })
    render(<UploadDeploymentPage />)

    expect(await screen.findByText(/Nothing is kept in the collections folder yet — import a deployment first/)).toBeInTheDocument()
  })

  it('asks for the collection only once a research project is picked, and for its deployments once a collection is', async () => {
    render(<UploadDeploymentPage />)
    await screen.findByLabelText('Research project')
    expect(screen.queryByLabelText('Collection')).not.toBeInTheDocument()

    await userEvent.click(screen.getByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
    expect(mockedApi.uploadCollections).toHaveBeenCalledWith('DONA')
    await userEvent.click(await screen.findByLabelText('Collection'))
    expect(await screen.findByRole('option', { name: 'R0001 — 1 deployment(s)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'R0003 — 4 deployment(s)' })).toBeInTheDocument()
    expect(screen.queryByText('Deployments')).not.toBeInTheDocument()
  })

  it('lists the deployments of the collection, with their images and dates', async () => {
    await pickCollection()

    expect(await screen.findByText('R0003-DONA_01')).toBeInTheDocument()
    expect(screen.getAllByText('2024-09-04 → 2024-11-04').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('120').length).toBeGreaterThanOrEqual(1) // its images
  })

  it('picks the deployments still to send: preprocessed and not uploaded before', async () => {
    await pickCollection()

    expect(await screen.findByRole('checkbox', { name: 'R0003-DONA_01' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_02' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_03' })).not.toBeChecked() // not preprocessed
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_04' })).not.toBeChecked() // sent already
    expect(screen.getByRole('button', { name: 'Upload 2 deployments' })).toBeEnabled()
  })

  it('a deployment that was not preprocessed cannot be chosen, and says what to do', async () => {
    await pickCollection()

    const box = await screen.findByRole('checkbox', { name: 'R0003-DONA_03' })
    expect(box).toBeDisabled()
    expect(screen.getByText(/Not preprocessed — import it again through the wizard before uploading it/)).toBeInTheDocument()
  })

  it('shows when a deployment was uploaded, which can still be chosen to send again', async () => {
    await pickCollection()

    expect(await screen.findByText('✔ 2025-01-15')).toBeInTheDocument()
    const box = screen.getByRole('checkbox', { name: 'R0003-DONA_04' })
    expect(box).toBeEnabled()
    await userEvent.click(box)
    expect(screen.getByRole('button', { name: 'Upload 3 deployments' })).toBeEnabled()
  })

  it('changes how many deployments the button says as they are ticked, and cannot upload none', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('checkbox', { name: 'R0003-DONA_01' }))
    expect(screen.getByRole('button', { name: 'Upload 1 deployment' })).toBeEnabled()

    await userEvent.click(screen.getByRole('checkbox', { name: 'R0003-DONA_02' }))
    expect(screen.getByRole('button', { name: 'Upload 0 deployments' })).toBeDisabled()
  })

  it('uploads each chosen deployment in turn', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))

    await screen.findByText(/2 deployment\(s\) uploaded\./)
    expect(mockedApi.uploadDeployment.mock.calls.map((c) => c.slice(0, 3))).toEqual([
      ['DONA', 'R0003', 'R0003-DONA_01'], ['DONA', 'R0003', 'R0003-DONA_02'],
    ])
  })

  it('shows what each step of an upload did', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))

    const first = await screen.findByRole('region', { name: 'Upload of R0003-DONA_01' })
    expect(within(first).getByText(/Connected — research project DONA is #2 in Trapper/)).toBeInTheDocument()
    expect(within(first).getByText(/Location DONA_01 created\./)).toBeInTheDocument()
    expect(within(first).getByText(/Deployment R0003-DONA_01 was already in Trapper\./)).toBeInTheDocument()
    expect(within(first).getByText(/1 package\(s\) of 120 image\(s\)\./)).toBeInTheDocument()
    expect(within(first).getByText(/Collection R0003 is in Trapper\./)).toBeInTheDocument()
    expect(within(first).getByText('✔ Uploaded to collection R0003 in 1 package(s).')).toBeInTheDocument()
  })

  it('shows how much of a file has gone up while it does', async () => {
    let finish: () => void = () => {}
    mockedApi.uploadDeployment.mockImplementation((_rp, _col, _id, _mode, onEvent) => new Promise<void>((resolve) => {
      onEvent({ type: 'upload_progress', file: 'package_2_x_part001.zip', bytes: 5 * 1024 * 1024, total: 20 * 1024 * 1024 })
      finish = resolve
    }))
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))

    expect(await screen.findByText('package_2_x_part001.zip — 5.0 of 20 MB')).toBeInTheDocument()
    const bar = screen.getByLabelText('Uploading package_2_x_part001.zip') as HTMLProgressElement
    expect(bar.value).toBe(5 * 1024 * 1024)
    expect(bar.max).toBe(20 * 1024 * 1024)
    expect(screen.getByRole('button', { name: 'Uploading…' })).toBeDisabled()

    finish()
  })

  it('a deployment that fails shows why, and the others go on', async () => {
    mockedApi.uploadDeployment.mockImplementation(async (_rp, _col, id, _mode, onEvent) => {
      if (id === 'R0003-DONA_01') throw new Error("Trapper has no research project 'DONA' — create it there first")
      STEP_EVENTS(id).forEach(onEvent)
    })
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))

    await screen.findByText(/1 deployment\(s\) uploaded, 1 failed\./)
    const failed = screen.getByRole('region', { name: 'Upload of R0003-DONA_01' })
    expect(within(failed).getByText(/Trapper has no research project 'DONA' — create it there first/)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Upload of R0003-DONA_02' })).getByText(/Uploaded to collection R0003/)).toBeInTheDocument()
    expect(mockedApi.uploadDeployment).toHaveBeenCalledTimes(2)
  })

  it('reads the collections again once done, so what was uploaded shows as uploaded', async () => {
    await pickCollection()
    mockedApi.uploadCollections.mockResolvedValue({ results: COLLECTIONS.map((c) => c.name === 'R0003'
      ? { ...c, deployments: c.deployments.map((d) => (d.deployment_id === 'R0003-DONA_01' ? { ...d, uploaded_at: '2026-10-01T08:00:00+00:00' } : d)) } : c) })
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))

    expect(await screen.findByText('✔ 2026-10-01')).toBeInTheDocument()
    expect(mockedApi.uploadCollections).toHaveBeenCalledTimes(2)
  })

  it('lets the user upload more once done', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))
    await screen.findByText(/2 deployment\(s\) uploaded\./)

    await userEvent.click(screen.getByRole('button', { name: 'Upload more' }))

    expect(screen.queryByText(/2 deployment\(s\) uploaded\./)).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Upload of R0003-DONA_01' })).not.toBeInTheDocument()
  })

  it('has no size of zips to set here: it is a setting of Trapper', async () => {
    await pickCollection()
    await screen.findByRole('button', { name: 'Upload 2 deployments' })
    expect(screen.queryByLabelText('Largest zip (MB)')).not.toBeInTheDocument()
  })

  it('changing the research project or the collection clears the previous upload', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))
    await screen.findByText(/2 deployment\(s\) uploaded\./)

    await userEvent.click(screen.getByLabelText('Collection'))
    await userEvent.click(await screen.findByRole('option', { name: /^R0001/ }))

    expect(screen.queryByRole('region', { name: 'Upload of R0003-DONA_01' })).not.toBeInTheDocument()
    expect(await screen.findByRole('checkbox', { name: 'R0001-DONA_01' })).not.toBeChecked() // sent already
  })

  it('shows why the collections could not be read', async () => {
    mockedApi.uploadCollections.mockRejectedValue(new Error('The research project id can only have letters, digits…'))
    render(<UploadDeploymentPage />)
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))

    expect(await screen.findByText(/can only have letters, digits/)).toBeInTheDocument()
  })

  it('runs a dry run, saying what would be done and changing nothing', async () => {
    mockedApi.uploadDeployment.mockImplementation(async (_rp, _col, id, _mode, onEvent) => {
      onEvent({ type: 'done', mode: 'dry_run', collection: 'R0003', deployment_id: id, parts: 3, would_create_location: true, would_create_deployment: false })
    })
    await pickCollection()
    await userEvent.click(await screen.findByRole('radio', { name: 'Dry run' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Dry run 2 deployments' }))

    await screen.findByText(/2 deployment\(s\) checked\./)
    expect(mockedApi.uploadDeployment.mock.calls.map((c) => c[3])).toEqual(['dry_run', 'dry_run'])
    expect(screen.getAllByText('The location would be created in Trapper.')).toHaveLength(2)
    expect(screen.getAllByText('The deployment is already in Trapper.')).toHaveLength(2)
    expect(screen.getAllByText('The images would go up in 3 package(s).')).toHaveLength(2)
  })

  it('only generates the files without a Trapper account, and can open their folder', async () => {
    mockedApi.trapperGetConfig.mockResolvedValue({ base_url: null, user_name: null, has_password: false })
    mockedApi.openFolder.mockResolvedValue({ opened: '/out/R0003' })
    mockedApi.uploadDeployment.mockImplementation(async (_rp, _col, id, _mode, onEvent) => {
      onEvent({ type: 'done', mode: 'generate', collection: 'R0003', deployment_id: id, parts: 1, output_dir: '/out/R0003', files: ['a_part001.zip', 'a_part001.yaml', 'R0003_deployments.csv'] })
    })
    await pickCollection()
    await userEvent.click(await screen.findByRole('radio', { name: 'Only generate the files' }))
    const button = await screen.findByRole('button', { name: 'Generate the files of 2 deployments' })
    expect(button).toBeDisabled() // the yaml needs the classification project, which can't be listed with no account
    expect(mockedApi.uploadClassificationProjects).not.toHaveBeenCalled()
    await userEvent.type(screen.getByLabelText('Classification project'), '7')
    expect(button).toBeEnabled()
    await userEvent.click(button)

    await screen.findByText(/2 deployment\(s\) generated\./)
    expect(mockedApi.uploadDeployment.mock.calls[0][3]).toBe('generate')
    expect(mockedApi.uploadDeployment.mock.calls[0][5]).toBe(7)
    expect(screen.getAllByText('R0003_deployments.csv').length).toBeGreaterThan(0)
    await userEvent.click(screen.getAllByRole('button', { name: 'Open folder in file explorer' })[0])
    expect(mockedApi.openFolder).toHaveBeenCalledWith('/out/R0003')
  })

  it('starts from the research project and collection a finished import went into', async () => {
    render(<UploadDeploymentPage initial={{ researchProjectId: 'DONA', collection: 'R0003' }} />)

    expect(await screen.findByLabelText('Collection')).toHaveValue('R0003 — 4 deployment(s)')
    expect(mockedApi.uploadCollections).toHaveBeenCalledWith('DONA')
    expect(screen.getByLabelText('Research project')).toHaveValue('DONA — Doñana')
    // what is left to send is ticked, as when the collection is picked by hand
    expect(await screen.findByRole('checkbox', { name: 'R0003-DONA_01' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_04' })).not.toBeChecked() // uploaded before
    expect(await screen.findByLabelText('Classification project')).toHaveValue('Doñana classification (#7)')
    expect(screen.getByRole('button', { name: 'Upload 2 deployments' })).toBeEnabled()
  })

  it('starts empty when it is not reached from an import', async () => {
    render(<UploadDeploymentPage />)
    expect(await screen.findByLabelText('Research project')).toHaveValue('')
    expect(mockedApi.uploadCollections).not.toHaveBeenCalled()
  })

  describe('the classification project', () => {
    it('is the only one the research project has, picked by itself and sent with the upload', async () => {
      await pickCollection()
      expect(await screen.findByLabelText('Classification project')).toHaveValue('Doñana classification (#7)')
      await userEvent.click(await screen.findByRole('button', { name: 'Upload 2 deployments' }))
      await screen.findByText(/2 deployment\(s\) uploaded\./)
      expect(mockedApi.uploadClassificationProjects).toHaveBeenCalledWith('DONA')
      expect(mockedApi.uploadDeployment.mock.calls.map((c) => c[5])).toEqual([7, 7])
    })

    it('has to be picked when there are several, and holds the upload back until it is', async () => {
      mockedApi.uploadClassificationProjects.mockResolvedValue({ results: [
        { pk: 7, name: 'A', is_active: true }, { pk: 8, name: 'B', is_active: true },
      ] })
      await pickCollection()
      const field = await screen.findByLabelText('Classification project')
      expect(field).toHaveValue('')
      expect(screen.getByRole('button', { name: 'Upload 2 deployments' })).toBeDisabled()
      expect(screen.getByText(/has several: pick the one/)).toBeInTheDocument()

      await userEvent.click(field)
      await userEvent.click(await screen.findByRole('option', { name: 'B (#8)' }))
      await userEvent.click(screen.getByRole('button', { name: 'Upload 2 deployments' }))
      await screen.findByText(/2 deployment\(s\) uploaded\./)
      expect(mockedApi.uploadDeployment.mock.calls[0][5]).toBe(8)
    })
  })

  describe('choosing the deployments', () => {
    it('selects all of them, or only the ones not uploaded yet, or none', async () => {
      await pickCollection()
      const ticked = () => ['01', '02', '03', '04'].filter((n) => (screen.getByRole('checkbox', { name: `R0003-DONA_${n}` }) as HTMLInputElement).checked)
      await screen.findByText('2 of 3 selected') // 03 can't be uploaded at all

      await userEvent.click(screen.getByRole('button', { name: 'Select all' }))
      expect(ticked()).toEqual(['01', '02', '04'])
      expect(screen.getByRole('checkbox', { name: 'Select all deployments' })).toBeChecked()

      await userEvent.click(screen.getByRole('button', { name: 'Select the not uploaded' }))
      expect(ticked()).toEqual(['01', '02'])

      await userEvent.click(screen.getByRole('button', { name: 'Select none' }))
      expect(ticked()).toEqual([])

      await userEvent.click(screen.getByRole('checkbox', { name: 'Select all deployments' })) // the header's box does it too
      expect(ticked()).toEqual(['01', '02', '04'])
      await userEvent.click(screen.getByRole('checkbox', { name: 'Select all deployments' }))
      expect(ticked()).toEqual([])
    })
  })

  describe('the access to what was chosen', () => {
    it('says whether the account has access to the research project and the collection, once both are chosen', async () => {
      await pickCollection()

      const project = await screen.findByText(/access to the research project DONA/)
      expect(mockedApi.checkUploadSelection).toHaveBeenCalledWith('DONA', 'R0003')
      expect(screen.getByText(/access to the collection R0003/)).toBeInTheDocument()
      // each message sits under its own field
      expect(project.closest('div')).toContainElement(screen.getByLabelText('Research project'))
      expect(project.closest('div')).not.toContainElement(screen.getByLabelText('Collection'))
    })

    it('says so when the account has no access, and when it cannot be checked', async () => {
      mockedApi.checkUploadSelection.mockResolvedValueOnce({ checks: [
        { check: 'research_project', ok: false, message: 'Trapper has no research project DONA.' },
        { check: 'collection', ok: false, message: 'Not checked: the research project couldn\u2019t be found.' },
      ] })
      await pickCollection()
      expect(await screen.findByText(/Trapper has no research project DONA/)).toBeInTheDocument()
    })
  })

  describe('testing the connection', () => {
    it('comes after the classification project, and checks the project, its locations and the uploader without uploading anything', async () => {
      mockedApi.checkUploadAccess.mockResolvedValue({ checks: [
        { check: 'research_project', ok: true, message: 'Research project DONA is #2 in Trapper.' },
        { check: 'location', ok: true, message: 'The 5 location(s) of the research project can be read. Would be created: DONA_02.' },
        { check: 'uploader', ok: false, message: "Trapper's uploader refused POST https://trapper.example.org/uploader/auth/login: 403 Forbidden." },
      ] })
      render(<UploadDeploymentPage />)
      await screen.findByLabelText('Research project')
      expect(screen.queryByRole('button', { name: 'Test connection' })).not.toBeInTheDocument() // only once the classification project is chosen

      await userEvent.click(await screen.findByLabelText('Research project'))
      await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
      await userEvent.click(await screen.findByLabelText('Collection'))
      await userEvent.click(await screen.findByRole('option', { name: /^R0003/ }))
      await userEvent.click(screen.getByRole('button', { name: 'Test connection' }))

      const list = await screen.findByRole('list', { name: 'Connection test' })
      expect(mockedApi.checkUploadAccess).toHaveBeenCalledWith('DONA', 'R0003', ['R0003-DONA_01', 'R0003-DONA_02'], 7)
      expect(within(list).getByText(/Research project DONA is #2/)).toBeInTheDocument()
      expect(within(list).getByText(/Would be created: DONA_02/)).toBeInTheDocument()
      expect(within(list).getByText(/uploader refused POST .*403 Forbidden/)).toBeInTheDocument()
      expect(mockedApi.uploadDeployment).not.toHaveBeenCalled()
    })

    it('says why the test could not be run', async () => {
      mockedApi.checkUploadAccess.mockRejectedValue(new Error('The Trapper account isn\u2019t set up'))
      render(<UploadDeploymentPage />)
      await userEvent.click(await screen.findByLabelText('Research project'))
      await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
      await userEvent.click(await screen.findByLabelText('Collection'))
      await userEvent.click(await screen.findByRole('option', { name: /^R0003/ }))
      await userEvent.click(await screen.findByRole('button', { name: 'Test connection' }))
      expect(await screen.findByText(/account isn.t set up/)).toBeInTheDocument()
    })
  })
})
