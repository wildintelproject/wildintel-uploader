import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import VisitBookPage from './VisitBookPage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), trapperGetConfig: vi.fn(), visitBook: vi.fn(), getSettings: vi.fn() } }))
const mockedApi = vi.mocked(api)

const visit = (over: object) => ({
  location_id: 'TATR_0001', session: 'R0003', date: '2024-09-04', time: '09:00:00', actions: ['Installation'], trappers: 'Ana', status: null, card_batteries_ok: null, num_photos: null,
  sd: 'A13', date_time_ok: null, latitude: null, longitude: null, camera_id: 'P800', camera_model: null, deployment: null, deployment_status: null, not_done: false, ...over,
}) as never

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.trapperGetConfig.mockRejectedValue(new Error('no account in this test'))
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ name: 'Tatra', acronym: 'TATR' }] } as never)
  mockedApi.getSettings.mockResolvedValue({ GENERAL: { default_research_project: 'TATR' } } as never)
  mockedApi.visitBook.mockResolvedValue({ results: [
    visit({ deployment: 'R0003-TATR_0001', deployment_status: 'closed' }),
    visit({ date: '2024-10-12', session: 'R0004', actions: ['Revision'], num_photos: 241, sd: 'B2', deployment: 'R0004-TATR_0001', deployment_status: 'open', comments: 'pilas cambiadas' }),
    visit({ location_id: 'TATR_0002', trappers: 'Luis', camera_id: 'P900', deployment: 'R0003-TATR_0002', deployment_status: 'closed', deployment_id: 'R0003-TATR_0002', on_trapper: true, uploaded_at: '2024-10-20T10:00:00+00:00' }),
  ] })
})

// The book is of the default research project: nothing to pick.
async function pickProject() {
  render(<VisitBookPage onBack={vi.fn()} onImportImages={vi.fn()} />)
  await screen.findByText('Tatra', { exact: false })
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

  it('is of the default research project, says so, and links to the settings where it is changed', async () => {
    const onOpenSettings = vi.fn()
    render(<VisitBookPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)

    expect(await screen.findByText(/Tatra/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Research project')).not.toBeInTheDocument() // no picker: the book is of the default one
    await userEvent.click(screen.getByRole('button', { name: 'Change it in the settings' }))
    expect(onOpenSettings).toHaveBeenCalledWith('general')
    expect(mockedApi.visitBook).toHaveBeenCalledWith('TATR')
  })

  it('says when there is no default research project, or it is not in the collections folder', async () => {
    mockedApi.getSettings.mockResolvedValue({ GENERAL: { default_research_project: null } } as never)
    const { unmount } = render(<VisitBookPage onBack={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(await screen.findByText('No default research project is set.')).toBeInTheDocument()
    expect(mockedApi.visitBook).not.toHaveBeenCalled()
    unmount()

    mockedApi.getSettings.mockResolvedValue({ GENERAL: { default_research_project: 'GONE' } } as never)
    render(<VisitBookPage onBack={vi.fn()} onOpenSettings={vi.fn()} />)
    expect(await screen.findByText(/is not in the collections folder/)).toBeInTheDocument()
  })

  it('has a row for each location not visited in a session, as Planned, with no buttons', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: [
      visit({ session: 'R0001', deployment: 'R0001-TATR_0001', deployment_status: 'closed' }),
      visit({ location_id: 'TATR_0002', session: 'R0001', date: '', time: '', actions: [], sd: null, camera_id: null, trappers: null, not_done: true, when: null }),
    ] })
    await pickProject()

    const table = await screen.findByRole('table', { name: 'Visits' })
    const [done, notDone] = within(table).getAllByRole('row').slice(1)
    expect(within(notDone).getAllByRole('cell').slice(0, 5).map((c) => c.textContent)).toEqual(['R0001', 'TATR_0002', '—', '', 'Planned'])
    expect(within(notDone).queryByRole('button')).not.toBeInTheDocument()
    expect(within(done).getByRole('button', { name: /View the visit/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /^Planned/ }))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
  })

  it('counts the visits by status in squares that filter them, with how many are done', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: [
      visit({ session: 'R0001', deployment: 'R0001-TATR_0001', deployment_status: 'closed' }),
      visit({ session: 'R0001', location_id: 'TATR_0002', deployment: 'R0001-TATR_0002', deployment_status: 'closed', deployment_id: 'R0001-TATR_0002' }),
      visit({ session: 'R0002', deployment: 'R0002-TATR_0001', deployment_status: 'open' }),
      visit({ session: 'R0002', location_id: 'TATR_0002', date: '', time: '', actions: [], not_done: true, sd: null, camera_id: null, trappers: null }),
    ] })
    await pickProject()
    const squares = await screen.findByRole('region', { name: 'Visits by status' })
    const square = (name: RegExp) => within(squares).getByRole('button', { name })

    expect(within(squares).getByText('Visits completed').parentElement).toHaveTextContent('3 / 4')
    expect(square(/^Planned/)).toHaveTextContent('1')
    expect(square(/^Deployed/)).toHaveTextContent('1')
    expect(square(/^Collected/)).toHaveTextContent('1')                   // the card collected, and no deployment made yet
    expect(square(/^Stored/)).toHaveTextContent('1')                      // the deployment is made: the images are stored
    expect(within(squares).getByRole('progressbar', { name: 'Visits done' })).toHaveAttribute('aria-valuenow', '3')
    expect(within(squares).getByText('3 of 4 visits done (75%) · 1 pending')).toBeInTheDocument()

    const table = screen.getByRole('table', { name: 'Visits' })
    await userEvent.click(square(/^Collected/))
    expect(square(/^Collected/)).toHaveAttribute('aria-pressed', 'true')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
    await userEvent.click(square(/^Collected/))                              // pressed again: all
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(4)
    await userEvent.click(square(/^Stored/))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
  })

  it('has a square for each revision — one visit to every site — with how many are done, and the status squares follow the one picked', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: [
      visit({ session: 'R0001', deployment: 'R0001-TATR_0001', deployment_status: 'closed' }),
      visit({ session: 'R0001', location_id: 'TATR_0002', date: '', time: '', actions: [], not_done: true, sd: null, camera_id: null, trappers: null }),
      visit({ session: 'R0002', deployment: 'R0002-TATR_0001', deployment_status: 'open' }),
      visit({ session: 'R0002', location_id: 'TATR_0002', date: '', time: '', actions: [], not_done: true, sd: null, camera_id: null, trappers: null }),
      visit({ session: 'R0003', date: '', time: '', actions: [], not_done: true, sd: null, camera_id: null, trappers: null }),
    ] })
    await pickProject()
    const revisions = await screen.findByRole('region', { name: 'Revision' })
    const pick = (name: RegExp) => within(revisions).getByRole('button', { name })

    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions2 of 5 done', 'R00030 of 1 done', 'R00021 of 2 done', 'R00011 of 2 done'])

    await userEvent.click(pick(/^R0002/))
    expect(pick(/^R0002/)).toHaveAttribute('aria-pressed', 'true')
    const squares = screen.getByRole('region', { name: 'Visits by status' })
    expect(within(squares).getByRole('button', { name: /^Deployed/ })).toHaveTextContent('1')
    expect(within(squares).getByText('1 of 2 visits done (50%) · 1 pending')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Visits' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002', 'R0002'])

    await userEvent.click(pick(/^All revisions/))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(5)
  })

  it('filters by status from the selector as from the cards', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: [
      visit({ session: 'R0001', deployment: 'R0001-TATR_0001', deployment_status: 'open' }),
      visit({ session: 'R0001', location_id: 'TATR_0002', date: '', time: '', actions: [], not_done: true, sd: null, camera_id: null, trappers: null }),
    ] })
    await pickProject()
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Status' }), 'Planned')
    expect(within(screen.getByRole('table', { name: 'Visits' })).getAllByRole('row').slice(1)).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Planned' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('pages the visits, ten at a time, and goes back to the first page when the filter changes', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: Array.from({ length: 23 }, (_, n) => visit({ session: `R${String(n + 1).padStart(4, '0')}`, date: `2024-09-${String(n + 1).padStart(2, '0')}`, location_id: n === 22 ? 'TATR_0099' : 'TATR_0001' })) })
    await pickProject()

    const table = await screen.findByRole('table', { name: 'Visits' })
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(10)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 1–10 of 23 visits')
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Page 3' }))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(3)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 21–23 of 23 visits')
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Previous page' }))
    expect(screen.getByRole('button', { name: 'Page 2' })).toHaveAttribute('aria-current', 'page')

    await userEvent.type(screen.getByLabelText('Filter the visits'), '0099')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
    expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument() // one page: nothing to page
  })

  it('sorts by a column, and turns it round when it is pressed again — the rows not made always last', async () => {
    mockedApi.visitBook.mockResolvedValue({ results: [
      visit({ location_id: 'TATR_0002', session: 'R0001', date: '2024-09-05', actions: ['Installation'] }),
      visit({ location_id: 'TATR_0001', session: 'R0001', date: '2024-09-07', actions: ['Revision'], deployment_status: 'open' }),
      visit({ location_id: 'TATR_0003', session: 'R0001', date: '', time: '', actions: [], not_done: true, camera_id: null, sd: null, trappers: null }),
      visit({ location_id: 'TATR_0004', session: 'R0001', date: '2024-09-06', actions: ['Revision'], deployment_status: 'closed', deployment: 'R0001-TATR_0004', deployment_id: 'R0001-TATR_0004' }),
    ] })
    await pickProject()
    const table = await screen.findByRole('table', { name: 'Visits' })
    const where = () => within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[1].textContent)

    await userEvent.click(within(table).getByRole('button', { name: 'Where' }))
    expect(where()).toEqual(['TATR_0001', 'TATR_0002', 'TATR_0003', 'TATR_0004'])
    expect(within(table).getByRole('columnheader', { name: /Where/ })).toHaveAttribute('aria-sort', 'ascending')
    await userEvent.click(within(table).getByRole('button', { name: 'Where' }))
    expect(where()).toEqual(['TATR_0004', 'TATR_0003', 'TATR_0002', 'TATR_0001'])
    expect(within(table).getByRole('columnheader', { name: /Where/ })).toHaveAttribute('aria-sort', 'descending')

    await userEvent.click(within(table).getByRole('button', { name: 'When' }))
    expect(where()).toEqual(['TATR_0002', 'TATR_0004', 'TATR_0001', 'TATR_0003']) // oldest first, the one not made last
    await userEvent.click(within(table).getByRole('button', { name: 'When' }))
    expect(where()).toEqual(['TATR_0001', 'TATR_0004', 'TATR_0002', 'TATR_0003']) // newest first, the one not made still last

    await userEvent.click(within(table).getByRole('button', { name: 'Status' }))
    expect(where().slice(0, 2)).toEqual(['TATR_0004', 'TATR_0001']) // closed, then open
  })

  it('has the session first, then where and when, the status of the visit (closed or open), the actions and whether its images are stored (a tick, or the button to create the deployment)', async () => {
    await pickProject()

    const table = await screen.findByRole('table', { name: 'Visits' })
    expect(within(table).getAllByRole('columnheader').slice(0, 6).map((h) => h.textContent)).toEqual(['Revision', 'Where', 'When', 'Actions', 'Status', 'Images'])
    const [first, second] = within(table).getAllByRole('row').slice(1)
    expect(within(first).getAllByRole('cell').slice(0, 6).map((c) => c.textContent)).toEqual(['R0004', 'TATR_0001', '2024-10-12 09:00', 'Revision', 'Deployed', ''])
    // a tick when the images are stored — the deployment is created and imported —, a button to create it when the visit is closed and they are not
    expect(within(table).getAllByRole('button', { name: /^Details of the deployment/ })).toHaveLength(1) // "Show image details", not the id of the deployment
    expect(within(table).getByRole('button', { name: /^Details of the deployment/ })).toHaveTextContent('Show image details')
    expect(within(table).queryByText('R0003-TATR_0002')).not.toBeInTheDocument()
    expect(within(table).getAllByLabelText('Images not stored')).toHaveLength(1) // the open visit: nothing to store yet
    expect(within(second).getAllByRole('cell').slice(0, 6).map((c) => c.textContent)).toEqual(['R0003', 'TATR_0001', '2024-09-04 09:00', 'Installation', 'Collected', 'Create deployment'])
  })

  it('links the Show image details button to the status of the deployment', async () => {
    const onShowDeployment = vi.fn()
    render(<VisitBookPage onBack={vi.fn()} onShowDeployment={onShowDeployment} />)
    await screen.findByRole('table', { name: 'Visits' })

    expect(screen.queryByRole('tab')).not.toBeInTheDocument() // the deployments are on Manage deployments, not here
    await userEvent.click(screen.getByRole('button', { name: 'Details of the deployment R0003-TATR_0002' }))
    expect(onShowDeployment).toHaveBeenCalledWith('R0003-TATR_0002')
  })

  it('shows the details of a visit, and creates the deployment of a closed visit that has none yet', async () => {
    const onImportImages = vi.fn()
    render(<VisitBookPage onBack={vi.fn()} onImportImages={onImportImages} />)
    await screen.findByRole('table', { name: 'Visits' })

    await userEvent.click(screen.getByRole('button', { name: 'View the visit R0004 to TATR_0001' }))
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('pilas cambiadas')
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('P800') // the camera, the card and the photos are in the details
    expect(screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })).toHaveTextContent('241')
    expect(within(screen.getByRole('table', { name: 'Visits' })).queryByRole('columnheader', { name: 'Camera' })).not.toBeInTheDocument()

    // only a closed visit offers it — not the open one, nor the closed one already imported
    expect(screen.getAllByRole('button', { name: /Create the deployment of the visit/ })).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Create the deployment of the visit R0003 to TATR_0001' }))
    expect(onImportImages).toHaveBeenCalledWith({ researchProjectId: 'TATR', visit: expect.objectContaining({ session: 'R0003', location_id: 'TATR_0001' }) })
  })

  it('says where it hangs from, Manage visits, and goes back there', async () => {
    const onBack = vi.fn()
    render(<VisitBookPage onBack={onBack} onOpenSettings={vi.fn()} />)

    const here = await screen.findByRole('navigation', { name: 'You are here' })
    expect(here).toHaveTextContent('Manage visits›Visit dashboard')
    await userEvent.click(within(here).getByRole('button', { name: 'Manage visits' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('opens on the visit a link of the deployments dashboard goes to: its revision picked and its details open', async () => {
    render(<VisitBookPage onBack={vi.fn()} focus={{ session: 'R0003', site: 'TATR_0002' }} />)

    expect(await screen.findByLabelText('Details of the visit R0003 to TATR_0002', { selector: 'dl' })).toHaveTextContent('P900')
    expect(within(screen.getByRole('region', { name: 'Revision' })).getByRole('button', { name: /^R0003/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('says that the photos of a visit are those of the card it collects — the one left before —, not of the card it leaves', async () => {
    await pickProject()
    const table = await screen.findByRole('table', { name: 'Visits' })
    await userEvent.click(within(table).getByRole('button', { name: /View the visit R0004 to TATR_0001/ }))

    const details = screen.getByLabelText('Details of the visit R0004 to TATR_0001', { selector: 'dl' })
    expect(details).toHaveTextContent('Photos collected from the SD card previously installed (A13)241')
    expect(details).toHaveTextContent('SD card leftB2')
  })
})
