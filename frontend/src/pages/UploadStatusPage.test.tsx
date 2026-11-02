import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeploymentUploadState, FieldDeployment, UploadEntry } from '../types'

vi.mock('../api', () => ({ api: { fieldDeployments: vi.fn(), listResearchProjects: vi.fn(), getSettings: vi.fn() } }))
import { api } from '../api'
import UploadStatusPage from './UploadStatusPage'

const sent = (extra: Partial<UploadEntry> = {}): UploadEntry => ({ destination: 'trapper', kind: 'uploaded', uploaded_at: '2026-10-20T10:00:00+00:00', parts: 2, location_created: true, deployment_created: true, url: 'https://trapper.example.org/geomap/deployment/detail/7/', ...extra })
const upload = (state: DeploymentUploadState['state'], destination = 'trapper', extra: Partial<DeploymentUploadState> = {}): DeploymentUploadState => ({
  destination, state, kind: state === 'done' ? 'uploaded' : null, uploaded_at: state === 'done' ? '2026-10-20T10:00:00+00:00' : null, note: null, ...extra })
const deployment = (id: string, states: DeploymentUploadState[], extra: Partial<FieldDeployment> = {}): FieldDeployment => ({
  deployment_id: id, collection: id.split('-')[0], site: id.split('-')[1], status: 'closed', start: '2026-06-10T09:00:00Z', end: '2026-08-05T08:00:00Z', setup_by: null, camera_id: null, card: null,
  photos_counted: null, start_session: id.split('-')[0], end_session: null, images_stored: true, uploads: states.some((s) => s.state === 'done') ? [sent()] : [], upload_states: states, ...extra })
const DEPLOYMENTS = [
  deployment('R0002-DONA_01', [upload('done')]),
  deployment('R0002-DONA_02', [upload('planned')], { images_stored: false }),                          // not created yet: its upload waits
  deployment('R0001-DONA_01', [upload('done', 'trapper', { uploaded_at: '2026-09-01T08:30:00+00:00' })]),
  deployment('R0001-DONA_02', [upload('failed', 'trapper', { note: 'Trapper refused the package' })]),
  deployment('R0001-DONA_03', [], { images_stored: false, no_images: 'stolen' }),                       // a stolen camera: the card is gone, nothing to upload
]

describe('UploadStatusPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getSettings).mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
    vi.mocked(api.listResearchProjects).mockResolvedValue({ results: [{ acronym: 'DONA', name: 'Doñana' }] } as never)
    vi.mocked(api.fieldDeployments).mockResolvedValue({ results: DEPLOYMENTS })
  })

  it('lists the uploads — one for each deployment that will be made and each uploader in use — with where, when, the uploader and its status', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const table = await screen.findByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Where', 'When', 'Uploader', 'Status', 'What to do'])
    const cells = (row: HTMLElement) => within(row).getAllByRole('cell').map((c) => c.textContent)
    expect(within(table).getAllByRole('row').slice(1).map(cells)).toEqual([
      ['R0002-DONA_01', 'DONA_01', 'Visit R0002 · DONA_0110 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper', 'Done20 Oct 2026', ''],
      ['R0002-DONA_02', 'DONA_02', 'Visit R0002 · DONA_0210 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper', 'Planned', ''],
      ['R0001-DONA_01', 'DONA_01', 'Visit R0001 · DONA_0110 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper', 'Done1 Sep 2026', ''],
      ['R0001-DONA_02', 'DONA_02', 'Visit R0001 · DONA_0210 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper', 'Failed', ''],
    ])
    expect(within(table).queryByText('R0001-DONA_03')).not.toBeInTheDocument()   // the camera was stolen: there is no deployment to upload
  })

  it('starts on the uploads of one deployment when it is reached from its tick in the deployments dashboard', async () => {
    render(<UploadStatusPage onBack={() => {}} search="R0001-DONA_01" />)

    const table = await screen.findByRole('table', { name: 'Uploads' })
    expect(screen.getByLabelText('Filter the uploads')).toHaveValue('R0001-DONA_01')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent('R0001-DONA_01')
  })

  it('counts the planned, the done and the failed, over every upload there is — the deployments times the uploaders —, and a card shows only its uploads', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const region = await screen.findByRole('region', { name: 'Uploads by status' })
    expect(within(region).getByText('All the uploads').parentElement).toHaveTextContent('2 / 4')
    expect(within(region).getByRole('button', { name: 'Planned' })).toHaveTextContent('1')
    expect(within(region).getByRole('button', { name: 'Done' })).toHaveTextContent('2')
    expect(within(region).getByRole('button', { name: 'Failed' })).toHaveTextContent('1')
    expect(within(region).getByRole('progressbar', { name: 'Uploads done' })).toHaveAttribute('aria-valuenow', '2')

    await userEvent.click(within(region).getByRole('button', { name: 'Failed' }))
    const table = screen.getByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0001-DONA_02'])
    await userEvent.click(within(region).getByRole('button', { name: 'Failed' }))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(4)
  })

  it('plans an upload for each uploader in use, so the deployments are told once for each', async () => {
    vi.mocked(api.fieldDeployments).mockResolvedValue({ results: [
      deployment('R0001-DONA_01', [upload('done'), upload('planned', 'agouti')]),
      deployment('R0001-DONA_02', [upload('planned'), upload('planned', 'agouti')], { images_stored: false }),
    ] })
    render(<UploadStatusPage onBack={() => {}} />)

    const region = await screen.findByRole('region', { name: 'Uploads by status' })
    expect(within(region).getByText('All the uploads').parentElement).toHaveTextContent('1 / 4')          // 2 deployments × 2 uploaders: the number planned from the start
    await userEvent.selectOptions(screen.getByLabelText('Uploader'), 'Agouti')
    expect(within(region).getByText(/All the uploads to Agouti/).parentElement).toHaveTextContent('0 / 2')
    const table = screen.getByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[3].textContent)).toEqual(['Agouti', 'Agouti'])
  })

  it('lets a planned upload be made once its deployment is created, and a failed one be tried again — a done one has its details instead', async () => {
    const onUpload = vi.fn()
    render(<UploadStatusPage onBack={() => {}} onUpload={onUpload} />)
    await screen.findByRole('table', { name: 'Uploads' })

    expect(screen.getByRole('button', { name: 'Upload the deployment R0002-DONA_02' })).toBeDisabled()    // its images are not stored yet
    await userEvent.click(screen.getByRole('button', { name: 'Try again the upload of the deployment R0001-DONA_02' }))
    expect(onUpload).toHaveBeenCalledWith({ researchProjectId: 'DONA', collection: 'R0001' })
    expect(screen.queryByRole('button', { name: /R0002-DONA_01$/ })).not.toBeInTheDocument() // done: nothing to upload

    await userEvent.click(screen.getByRole('button', { name: 'View the upload of R0002-DONA_01 to Trapper' }))
    const list = screen.getByRole('list', { name: 'Uploads of R0002-DONA_01' })
    expect(list).toHaveTextContent('TrapperUploaded on 20 Oct 2026, 10:00 · 2 packages · location and deployment created there')
    expect(within(list).getByRole('link', { name: 'Open R0002-DONA_01 in Trapper' })).toHaveAttribute('href', 'https://trapper.example.org/geomap/deployment/detail/7/')
    await userEvent.click(screen.getByRole('button', { name: 'View the upload of R0002-DONA_01 to Trapper' }))
    expect(screen.queryByRole('list', { name: 'Uploads of R0002-DONA_01' })).not.toBeInTheDocument()
  })

  it('has the revisions to pick one, and the progress follows it', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 uploads', 'R00022 uploads', 'R00012 uploads'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0002/ }))

    const table = screen.getByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002-DONA_01', 'R0002-DONA_02'])
    const progress = screen.getByRole('region', { name: 'Uploads by status' })
    expect(progress).toHaveTextContent('Uploads of R0002')
    expect(progress).toHaveTextContent('1 / 2')
  })

  it('goes to the visit that started a deployment and to the details of a deployment', async () => {
    const onShowVisit = vi.fn(), onShowDeployment = vi.fn()
    render(<UploadStatusPage onBack={() => {}} onShowVisit={onShowVisit} onShowDeployment={onShowDeployment} />)
    await screen.findByRole('table', { name: 'Uploads' })

    await userEvent.click(screen.getByRole('button', { name: 'Show the visit R0001 to DONA_01' }))
    expect(onShowVisit).toHaveBeenCalledWith({ session: 'R0001', site: 'DONA_01' })
    await userEvent.click(screen.getByRole('button', { name: 'Show the details of the deployment R0001-DONA_01' }))
    expect(onShowDeployment).toHaveBeenCalledWith('R0001-DONA_01')
  })

  it('says so when there is no upload', async () => {
    vi.mocked(api.fieldDeployments).mockResolvedValue({ results: [] })
    render(<UploadStatusPage onBack={() => {}} />)

    expect(await screen.findByText('There is no upload yet: no deployment is planned, or no uploader is in use.')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Uploads by status' })).toHaveTextContent('0 / 0')
  })

  it('comes back from the breadcrumb', async () => {
    const onBack = vi.fn()
    render(<UploadStatusPage onBack={onBack} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Manage uploads' }))
    expect(onBack).toHaveBeenCalled()
  })
})
