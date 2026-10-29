import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import DeploymentStatusPage from './DeploymentStatusPage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), fieldDeployments: vi.fn(), getSettings: vi.fn(), collectionPath: vi.fn(), listLocalDeployments: vi.fn() } }))
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
    expect(within(squares).getByText('All the deployments').parentElement).toHaveTextContent('2 / 4')      // created (or uploaded), of all
    expect(square(/^Not created/)).toHaveTextContent('2')             // the images are not stored: the camera out, or the card not imported
    expect(square(/^Created/)).toHaveTextContent('1')                 // the images stored, not uploaded yet
    expect(square(/^Uploaded/)).toHaveTextContent('1')                // on Trapper

    await userEvent.click(within(revisions).getByRole('button', { name: /^R0003/ }))
    const table = within(region).getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Where', 'When', 'Card and photos', 'Creation', 'Upload', 'What to do'])
    const first = within(table).getAllByRole('row')[1]
    expect(within(first).getAllByRole('cell').map((c) => c.textContent)).toEqual(['R0003-TATR_0001', 'TATR_0001', 'Visit R0003 · TATR_00014 Sep 2024, 09:00 → 12 Oct 2024, 09:30', 'Card A13 · 241 photos', 'Created', 'Uploaded', 'View'])
    expect(within(first).getByText('Uploaded')).toHaveAttribute('title', 'Uploaded to Trapper on 2024-10-20')

    await userEvent.click(square(/^Created/))
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0003-TATR_0002'])
  })

  it('shows highlighted the deployment a link of the visit book goes to, on its revision', async () => {
    render(<DeploymentStatusPage onBack={vi.fn()} focus="R0003-TATR_0002" />)

    const table = await screen.findByRole('table', { name: 'Deployments' })
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Revision' })).getByRole('button', { name: /^R0003/ })).toHaveAttribute('aria-pressed', 'true'))
    expect(within(table).getByText('R0003-TATR_0002').closest('tr')).toHaveAttribute('aria-current', 'true')
  })

  it('has the visit that started each deployment, and goes to the visit dashboard on it', async () => {
    const onShowVisit = vi.fn()
    render(<DeploymentStatusPage onBack={vi.fn()} onShowVisit={onShowVisit} />)
    await screen.findByRole('table', { name: 'Deployments' })

    await userEvent.click(screen.getAllByRole('button', { name: 'Show the visit R0003 to TATR_0001' })[0])
    expect(onShowVisit).toHaveBeenCalledWith({ session: 'R0003', site: 'TATR_0001' })
  })

  it('opens what a created deployment says of itself with its View button, and has none for one that is not created', async () => {
    mockedApi.collectionPath.mockResolvedValue({ path: '/collections/TATR/R0003', collection: 'R0003' } as never)
    mockedApi.listLocalDeployments.mockResolvedValue({ results: [{ deployment_id: 'R0003-TATR_0002', start_date: '2024-09-04T09:00:00Z', camera_id: 'P800', camera_height: 1.2, bait_use: true, tags: ['forest edge'] }] } as never)
    render(<DeploymentStatusPage onBack={vi.fn()} />)
    await screen.findByRole('table', { name: 'Deployments' })

    expect(screen.queryByRole('button', { name: 'View the deployment R0003-TATR_0003' })).not.toBeInTheDocument() // not created: nothing to see
    await userEvent.click(screen.getByRole('button', { name: 'View the deployment R0003-TATR_0002' }))
    const details = await screen.findByLabelText('Details of the deployment R0003-TATR_0002', { selector: 'dl' })
    expect(mockedApi.collectionPath).toHaveBeenCalledWith('TATR', 'R0003-TATR_0002')
    expect(mockedApi.listLocalDeployments).toHaveBeenCalledWith('/collections/TATR/R0003')
    expect(details).toHaveTextContent('Camera height (m)1.2')
    expect(details).toHaveTextContent('Bait useyes')
    expect(details).toHaveTextContent('forest edge')
    await userEvent.click(screen.getByRole('button', { name: 'View the deployment R0003-TATR_0002' }))
    expect(screen.queryByLabelText('Details of the deployment R0003-TATR_0002', { selector: 'dl' })).not.toBeInTheDocument()
  })

  it('has the deployment closed by a theft apart: no images, nothing to create or upload, and left out of the progress', async () => {
    mockedApi.fieldDeployments.mockResolvedValue({ results: [
      deployment({ on_trapper: true }),
      deployment({ deployment_id: 'R0003-TATR_0002', site: 'TATR_0002', images_stored: false, no_images: 'stolen', photos_counted: null, card: 'C7' }),
    ] })
    render(<DeploymentStatusPage onBack={vi.fn()} />)

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    const squares = within(region).getByRole('region', { name: 'Deployments by status' })
    expect(within(squares).getByRole('button', { name: 'No images' })).toHaveTextContent('1')
    expect(within(squares).getByRole('button', { name: 'Not created' })).toHaveTextContent('0')
    expect(within(squares).getByText('All the deployments').parentElement).toHaveTextContent('1 / 1') // the one with no images is not counted
    const table = within(region).getByRole('table', { name: 'Deployments' })
    const stolen = within(table).getByText('R0003-TATR_0002').closest('tr')!
    expect(within(stolen).getByText('No images')).toBeInTheDocument()
    expect(within(stolen).queryByRole('button', { name: /View the deployment/ })).not.toBeInTheDocument()
  })
})

