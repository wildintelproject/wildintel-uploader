import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import VisitBookPage from './VisitBookPage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), trapperGetConfig: vi.fn(), visitBook: vi.fn(), fieldDeployments: vi.fn(), writeFieldLogs: vi.fn() } }))
const mockedApi = vi.mocked(api)

const visit = (over: object) => ({
  location_id: 'TATR_0001', session: 'R0003', date: '2024-09-04', time: '09:00:00', actions: ['Installation'], trappers: 'Ana', status: null, card_batteries_ok: null, num_photos: null,
  sd: 'A13', date_time_ok: null, latitude: null, longitude: null, camera_id: 'P800', camera_model: null, deployment: null, deployment_status: null, ...over,
}) as never

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.trapperGetConfig.mockRejectedValue(new Error('no account in this test'))
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ name: 'Tatra', acronym: 'TATR' }] } as never)
  mockedApi.visitBook.mockResolvedValue({ results: [
    visit({ deployment: 'R0003-TATR_0001', deployment_status: 'closed' }),
    visit({ date: '2024-10-12', session: 'R0004', actions: ['Revision'], num_photos: 241, sd: 'B2', deployment: 'R0004-TATR_0001', deployment_status: 'open', comments: 'pilas cambiadas' }),
    visit({ location_id: 'TATR_0002', trappers: 'Luis', camera_id: 'P900', deployment: 'R0003-TATR_0002', deployment_status: 'closed', deployment_id: 'R0003-TATR_0002' }),
  ] })
  mockedApi.fieldDeployments.mockResolvedValue({ results: [
    { deployment_id: 'R0003-TATR_0001', collection: 'R0003', site: 'TATR_0001', status: 'closed', start: '2024-09-04T09:00:00Z', end: '2024-10-12T09:00:00Z', setup_by: 'Ana', camera_id: 'P800', card: 'A13', photos_counted: 241, start_session: 'R0003', end_session: 'R0004' },
    { deployment_id: 'R0003-TATR_0002', collection: 'R0003', site: 'TATR_0002', status: 'open', start: '2024-09-05T09:00:00Z', end: null, setup_by: null, camera_id: 'P900', card: 'C7', photos_counted: null, start_session: 'R0003', end_session: null },
  ] })
})

async function pickProject() {
  render(<VisitBookPage onBack={vi.fn()} />)
  await userEvent.click(await screen.findByLabelText('Research project'))
  await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
}

describe('VisitBookPage', () => {
  it('lists the visits of a research project, the newest first, and filters them', async () => {
    await pickProject()

    const table = await screen.findByRole('table', { name: 'Visits' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent('2024-10-12 09:00') // the Revision, the newest
    await userEvent.type(screen.getByLabelText('Filter the visits'), 'luis')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
    expect(mockedApi.visitBook).toHaveBeenCalledWith('TATR')
  })

  it('has the session first, then where and when, the status of the visit (closed or open), the actions and the deployment — only once it is created, with its images imported', async () => {
    await pickProject()

    const table = await screen.findByRole('table', { name: 'Visits' })
    expect(within(table).getAllByRole('columnheader').slice(0, 6).map((h) => h.textContent)).toEqual(['Session', 'Where', 'When', 'Status', 'Actions', 'Deployment'])
    const [first, second] = within(table).getAllByRole('row').slice(1)
    expect(within(first).getAllByRole('cell').slice(0, 6).map((c) => c.textContent)).toEqual(['R0004', 'TATR_0001', '2024-10-12 09:00', 'Open', 'Revision', ''])
    // the id a deployment would have is not shown: it appears when the deployment is created and its images imported
    expect(within(screen.getByRole('table', { name: 'Visits' })).getByText('R0003-TATR_0002')).toBeInTheDocument()
    expect(within(second).getAllByRole('cell').slice(0, 6).map((c) => c.textContent)).toEqual(['R0003', 'TATR_0001', '2024-09-04 09:00', 'Closed', 'Installation', 'Not created yet'])
  })

  it('shows the details of a visit, and creates the deployment of a closed visit that has none yet', async () => {
    const onImportImages = vi.fn()
    render(<VisitBookPage onBack={vi.fn()} onImportImages={onImportImages} />)
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
    await screen.findByRole('table', { name: 'Visits' })

    await userEvent.click(screen.getByRole('button', { name: 'Details of the visit R0004 to TATR_0001' }))
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('pilas cambiadas')
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('P800') // the camera, the card and the photos are in the details
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('241')
    expect(within(screen.getByRole('table', { name: 'Visits' })).queryByRole('columnheader', { name: 'Camera' })).not.toBeInTheDocument()

    // only a closed visit offers it — not the open one, nor the closed one already imported
    expect(screen.getAllByRole('button', { name: /Create the deployment of the visit/ })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Create the deployment of the visit R0003 to TATR_0001' }))
    expect(onImportImages).toHaveBeenCalledWith({ researchProjectId: 'TATR', visit: expect.objectContaining({ session: 'R0003', location_id: 'TATR_0001' }) })
  })

  it('lists the deployments the visits say, the ones still out apart, and writes the logs again', async () => {
    mockedApi.writeFieldLogs.mockResolvedValue({ collections: [{ collection: 'R0003', closed: 1, open: 1, files: ['/c/TATR/R0003/R0003_FileTimestampLog.csv'] }], warnings: [] })
    await pickProject()
    await userEvent.click(await screen.findByRole('tab', { name: /Deployments/ }))

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    expect(region).toHaveTextContent('R0003 · 1 closed · 1 still out')
    expect(region).toHaveTextContent('Camera still out')
    await userEvent.click(screen.getByRole('button', { name: 'Write the logs of all the collections again' }))
    expect(await screen.findByRole('list', { name: 'Logs written' })).toHaveTextContent('R0003: 1 closed, 1 open — R0003_FileTimestampLog.csv')
  })
})
