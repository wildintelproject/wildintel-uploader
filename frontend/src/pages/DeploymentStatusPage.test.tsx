import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import DeploymentStatusPage from './DeploymentStatusPage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), fieldDeployments: vi.fn(), getSettings: vi.fn() } }))
const mockedApi = vi.mocked(api)

const deployment = (over: object) => ({
  deployment_id: 'R0003-TATR_0001', collection: 'R0003', site: 'TATR_0001', status: 'closed', start: '2024-09-04T09:00:00Z', end: '2024-10-12T09:30:00Z', setup_by: 'Ana', camera_id: 'P800',
  card: 'A13', photos_counted: 241, start_session: 'R0003', end_session: 'R0004', images_stored: true, on_trapper: false, ...over,
}) as never

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ name: 'Tatra', acronym: 'TATR' }] } as never)
  mockedApi.getSettings.mockResolvedValue({ GENERAL: { default_research_project: 'TATR' } } as never)
  mockedApi.fieldDeployments.mockResolvedValue({ results: [
    deployment({ on_trapper: true, uploaded_at: '2024-10-20T10:00:00+00:00' }),
    deployment({ deployment_id: 'R0003-TATR_0002', site: 'TATR_0002', card: 'C7', photos_counted: 10 }),
    deployment({ deployment_id: 'R0003-TATR_0003', site: 'TATR_0003', card: 'C8', photos_counted: 12, images_stored: false }),
    deployment({ deployment_id: 'R0004-TATR_0001', collection: 'R0004', status: 'open', start: '2024-10-12T09:30:00Z', end: null, card: 'B2', photos_counted: null, images_stored: false }),
  ] })
})

describe('DeploymentStatusPage', () => {
  it('is of the default research project, with the link to the settings where it is changed', async () => {
    const onOpenSettings = vi.fn()
    render(<DeploymentStatusPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)

    expect(await screen.findByText(/Tatra/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Change it in the settings' }))
    expect(onOpenSettings).toHaveBeenCalledWith('general')
    expect(mockedApi.fieldDeployments).toHaveBeenCalledWith('TATR')
  })

  it('has the deployments as a book: a square for each revision, the status squares of the one picked, and a table', async () => {
    render(<DeploymentStatusPage onBack={vi.fn()} />)

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    const revisions = within(region).getByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 deployments', 'R00041 deployment', 'R00033 deployments'])
    const squares = within(region).getByRole('region', { name: 'Deployments by status' })
    const square = (name: RegExp) => within(squares).getByRole('button', { name })
    expect(square(/^All the deployments/)).toHaveTextContent('4')
    expect(square(/^Deployed/)).toHaveTextContent('1')                // camera still out
    expect(square(/^Collected/)).toHaveTextContent('1')               // camera back, images not imported
    expect(square(/^Imported/)).toHaveTextContent('2')                // collected, and the images stored
    expect(square(/^Not on Trapper yet/)).toHaveTextContent('1')      // closed, stored, not uploaded

    await userEvent.click(within(revisions).getByRole('button', { name: /^R0003/ }))
    expect(within(region).getByRole('heading', { name: 'Revision R0003: deployments by status' })).toBeInTheDocument()
    const table = within(region).getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Where', 'Status', 'Period', 'Card and photos', 'On Trapper'])
    const first = within(table).getAllByRole('row')[1]
    expect(within(first).getAllByRole('cell').map((c) => c.textContent).slice(0, 5)).toEqual(['R0003-TATR_0001', 'TATR_0001', 'Imported', '4 Sep 2024, 09:00 → 12 Oct 2024, 09:30', 'Card A13 · 241 photos'])
    expect(within(first).getByRole('img', { name: 'On Trapper' })).toHaveAttribute('title', 'Uploaded to Trapper on 2024-10-20')

    await userEvent.click(square(/^Not on Trapper yet/))
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0003-TATR_0002'])
  })

  it('shows highlighted the deployment a link of the visit book goes to, on its revision', async () => {
    render(<DeploymentStatusPage onBack={vi.fn()} focus="R0003-TATR_0002" />)

    const table = await screen.findByRole('table', { name: 'Deployments' })
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Revision' })).getByRole('button', { name: /^R0003/ })).toHaveAttribute('aria-pressed', 'true'))
    expect(within(table).getByText('R0003-TATR_0002').closest('tr')).toHaveAttribute('aria-current', 'true')
  })
})
