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

  it('links the SD card of a deployment to its state in the settings', async () => {
    const onOpenSettings = vi.fn()
    render(<DeploymentStatusPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    await userEvent.click(within(region).getAllByRole('button', { name: 'Show the state of the SD card A13' })[0])
    expect(onOpenSettings).toHaveBeenCalledWith('sdcards', 'TATR', 'A13')
  })

  it('has the deployments as a book: a square for each revision, the status squares of the one picked, and a table', async () => {
    render(<DeploymentStatusPage onBack={vi.fn()} />)

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    const revisions = within(region).getByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 deployments', 'R00041 deployment', 'R00033 deployments'])
    const squares = within(region).getByRole('region', { name: 'Deployments by status' })
    const square = (name: RegExp) => within(squares).getByRole('button', { name })
    expect(within(squares).getByText('All the deployments').parentElement).toHaveTextContent('2 / 4')      // created, of all that was planned
    expect(square(/^Planned/)).toHaveTextContent('2')                 // a card was left: the deployment is to be created — the camera may be still out
    expect(square(/^Created/)).toHaveTextContent('2')                 // the images stored — whether they were uploaded is another thing, told by the Upload column
    expect(within(squares).queryByRole('button', { name: /^Uploaded/ })).not.toBeInTheDocument()

    await userEvent.click(within(revisions).getByRole('button', { name: /^R0003/ }))
    const table = within(region).getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Where', 'When', 'SD and photos', 'Creation', 'Upload', 'What to do'])
    const first = within(table).getAllByRole('row')[1]
    expect(within(first).getAllByRole('cell').map((c) => c.textContent)).toEqual(['R0003-TATR_0001', 'TATR_0001', 'Visit R0003 · TATR_00014 Sep 2024, 09:00 → 12 Oct 2024, 09:30', 'SD A13 · 241 photos', 'Created', '', ''])
    expect(within(first).getByRole('button', { name: 'View the deployment R0003-TATR_0001' })).toBeInTheDocument()
    expect(within(first).getByRole('img', { name: 'Uploaded' })).toBeInTheDocument() // it was uploaded: a tick

    await userEvent.click(square(/^Created/))
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0003-TATR_0001', 'R0003-TATR_0002'])   // both have their images stored — what was uploaded is another state
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

  it('lists the deployment of a stolen camera as Not created — nothing to create or upload — and counts it in what was planned', async () => {
    mockedApi.fieldDeployments.mockResolvedValue({
      results: [
        deployment({ on_trapper: true }),
        deployment({ deployment_id: 'R0003-TATR_0002', site: 'TATR_0002', images_stored: false, no_images: 'stolen', photos_counted: null, card: 'C7' }),
      ],
    } as never)
    render(<DeploymentStatusPage onBack={vi.fn()} />)

    const region = await screen.findByRole('region', { name: 'Deployments the visits say' })
    const squares = within(region).getByRole('region', { name: 'Deployments by status' })
    expect(within(squares).getByRole('button', { name: /^Not created/ })).toHaveTextContent('1')
    expect(within(squares).getByRole('button', { name: /^Planned/ })).toHaveTextContent('0')
    expect(within(squares).getByText('All the deployments').parentElement).toHaveTextContent('1 / 2')   // of all that was planned: the one that will not be made was planned too
    const table = within(region).getByRole('table', { name: 'Deployments' })
    const stolen = within(table).getByText('R0003-TATR_0002').closest('tr')!
    expect(within(stolen).getByText('Not created')).toBeInTheDocument()
    expect(within(stolen).queryByRole('button', { name: /View the deployment|Upload the deployment/ })).not.toBeInTheDocument()
  })

  it('links the location, the visit and the SD card in the same style, and goes to the deployment before and after at the same site', async () => {
    const onOpenSettings = vi.fn()
    mockedApi.fieldDeployments.mockResolvedValue({ results: [
      deployment({ deployment_id: 'R0001-TATR_0001', collection: 'R0001', start_session: 'R0001' }),
      deployment({ deployment_id: 'R0002-TATR_0001', collection: 'R0002', start_session: 'R0002' }),
      deployment({ deployment_id: 'R0003-TATR_0001', collection: 'R0003', start_session: 'R0003' }),
    ] })
    render(<DeploymentStatusPage onBack={vi.fn()} onOpenSettings={onOpenSettings} onShowVisit={vi.fn()} />)
    const table = await screen.findByRole('table', { name: 'Deployments' })
    const rowOf = (id: string) => within(table).getAllByRole('row').find((r) => within(r).queryByRole('button', { name: new RegExp(`^View the deployment ${id}`) }))!

    const first = rowOf('R0001-TATR_0001')
    await userEvent.click(within(first).getByRole('button', { name: 'TATR_0001' }))
    expect(onOpenSettings).toHaveBeenCalledWith('locations', 'TATR', 'TATR_0001')
    for (const name of ['TATR_0001', 'Show the visit R0001 to TATR_0001', 'Show the state of the SD card A13']) {
      expect(within(first).getByRole('button', { name })).toHaveClass('underline', 'decoration-dotted')
    }

    // nothing before the first revision of the site, nothing after the last
    expect(within(first).queryByRole('button', { name: /^Show the previous deployment/ })).not.toBeInTheDocument()
    expect(within(rowOf('R0003-TATR_0001')).queryByRole('button', { name: /^Show the next deployment/ })).not.toBeInTheDocument()
    await userEvent.click(within(rowOf('R0002-TATR_0001')).getByRole('button', { name: 'Show the next deployment of TATR_0001 (R0003)' }))
    expect(screen.getByRole('button', { name: /^R0003/ })).toHaveAttribute('aria-pressed', 'true')   // the revision of the deployment it went to
    expect(rowOf('R0003-TATR_0001')).toHaveAttribute('aria-current', 'true')
  })

  it('has, in the Upload column, a tick when the deployment was uploaded — it goes to its uploads — and a cross when it was not, and the button to upload its images', async () => {
    const onUpload = vi.fn()
    const onShowUploads = vi.fn()
    const states = (trapper: 'planned' | 'done' | 'failed') => [{ destination: 'trapper', state: trapper, kind: trapper === 'done' ? 'uploaded' : null, uploaded_at: trapper === 'done' ? '2024-10-20T10:00:00+00:00' : null, note: null }]
    mockedApi.fieldDeployments.mockResolvedValue({ results: [
      deployment({ on_trapper: true, uploaded_at: '2024-10-20T10:00:00+00:00', upload_states: states('done') }),
      deployment({ deployment_id: 'R0003-TATR_0002', site: 'TATR_0002', upload_states: states('planned') }),
      deployment({ deployment_id: 'R0003-TATR_0004', site: 'TATR_0004', upload_states: states('failed') }),
      deployment({ deployment_id: 'R0003-TATR_0003', site: 'TATR_0003', images_stored: false, upload_states: states('planned') }),
    ] })
    render(<DeploymentStatusPage onBack={vi.fn()} onUpload={onUpload} onShowUploads={onShowUploads} />)
    const table = await screen.findByRole('table', { name: 'Deployments' })
    const rowOf = (site: string) => within(table).getAllByRole('row').find((r) => within(r).queryAllByRole('cell')[1]?.textContent === site)!
    const uploadCell = (site: string) => within(rowOf(site)).getAllByRole('cell')[5]

    // uploaded: a tick that goes to the uploads of the deployment
    await userEvent.click(within(uploadCell('TATR_0001')).getByRole('button', { name: 'Show the uploads of the deployment R0003-TATR_0001' }))
    expect(onShowUploads).toHaveBeenCalledWith('R0003-TATR_0001')
    // planned or failed: a cross, which is not a link; a deployment that is not created yet has nothing to say
    expect(within(uploadCell('TATR_0002')).getByRole('img', { name: 'Not uploaded' })).toBeInTheDocument()
    expect(within(uploadCell('TATR_0002')).queryByRole('button')).not.toBeInTheDocument()
    expect(within(uploadCell('TATR_0004')).getByRole('img', { name: 'Not uploaded' })).toHaveAttribute('title', 'Not uploaded (Trapper: failed)')
    expect(uploadCell('TATR_0003')).toHaveTextContent('—')

    await userEvent.click(screen.getByRole('button', { name: 'Upload the deployment R0003-TATR_0002' }))
    expect(onUpload).toHaveBeenCalledWith({ researchProjectId: 'TATR', collection: 'R0003' })
    expect(screen.getByRole('button', { name: 'Upload the deployment R0003-TATR_0004' })).toHaveAttribute('title', 'Upload the images again')   // a failed one is tried again
  })
})
