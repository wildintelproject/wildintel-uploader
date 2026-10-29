import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import VisitBookPage from './VisitBookPage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), trapperGetConfig: vi.fn(), listVisits: vi.fn(), fieldDeployments: vi.fn(), writeFieldLogs: vi.fn() } }))
const mockedApi = vi.mocked(api)

const visit = (over: object) => ({
  location_id: 'TATR_0001', session: 'R0003', date: '2024-09-04', time: '09:00:00', actions: ['Installation'], trappers: 'Ana', status: null, card_batteries_ok: null, num_photos: null,
  sd: 'A13', date_time_ok: null, latitude: null, longitude: null, camera_id: 'P800', camera_model: null, ...over,
}) as never

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.trapperGetConfig.mockRejectedValue(new Error('no account in this test'))
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ name: 'Tatra', acronym: 'TATR' }] } as never)
  mockedApi.listVisits.mockResolvedValue({ results: [
    visit({}), visit({ date: '2024-10-12', session: 'R0004', actions: ['Revision'], num_photos: 241, sd: 'B2', deployment_id: 'R0003-TATR_0001' }), visit({ location_id: 'TATR_0002', trappers: 'Luis', camera_id: 'P900' }),
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
    expect(rows[0]).toHaveTextContent('R0003-TATR_0001')   // the deployment it closed
    await userEvent.type(screen.getByLabelText('Filter the visits'), 'luis')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
    expect(mockedApi.listVisits).toHaveBeenCalledWith('TATR')
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
