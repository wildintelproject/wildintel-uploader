import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UploadRecord } from '../types'

vi.mock('../api', () => ({ api: { uploads: vi.fn(), listResearchProjects: vi.fn(), getSettings: vi.fn() } }))
import { api } from '../api'
import UploadStatusPage from './UploadStatusPage'

const upload = (id: string, extra: Partial<UploadRecord> = {}): UploadRecord => ({
  deployment_id: id, collection: id.split('-')[0], site: 'DONA_01', destination: 'trapper', kind: 'uploaded', uploaded_at: '2026-10-20T10:00:00+00:00', parts: 2,
  location_created: true, deployment_created: true, ...extra,
})
const UPLOADS = [upload('R0002-DONA_01'), upload('R0001-DONA_01', { uploaded_at: '2026-09-01T08:30:00+00:00', parts: 1, location_created: false, deployment_created: true }), upload('R0001-DONA_02', { kind: 'synced', uploaded_at: null, parts: null, location_created: null, deployment_created: null })]

describe('UploadStatusPage', () => {
  beforeEach(() => {
    vi.mocked(api.getSettings).mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
    vi.mocked(api.listResearchProjects).mockResolvedValue({ results: [{ acronym: 'DONA', name: 'Doñana' }] } as never)
    vi.mocked(api.uploads).mockResolvedValue({ results: UPLOADS })
  })

  it('shows the uploads — where each deployment went, when, and what it did — not the states of the deployments', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const table = await screen.findByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Revision', 'Platform', 'Uploaded', 'What it did'])
    const [first, second, synced] = within(table).getAllByRole('row').slice(1)
    expect(within(first).getAllByRole('cell').map((c) => c.textContent)).toEqual(['R0002-DONA_01', 'R0002', 'Trapper', '20 Oct 2026, 10:00', '2 packages · location and deployment created there'])
    expect(within(second).getAllByRole('cell')[4]).toHaveTextContent('1 package · deployment created there')
    expect(within(synced).getAllByRole('cell')[3]).toHaveTextContent('—')
    expect(within(synced).getAllByRole('cell')[4]).toHaveTextContent('Synced from Trapper: it was not sent from here')
    expect(screen.queryByRole('button', { name: 'Not created' })).not.toBeInTheDocument()
  })

  it('has a card for each platform, with its uploads, that filters the table', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const cards = await screen.findByRole('region', { name: 'Uploads by platform' })
    expect(within(cards).getByText('Uploaded deployments').parentElement).toHaveTextContent('3')
    expect(within(cards).getByText(/The last, R0002-DONA_01, on 20 Oct 2026/)).toBeInTheDocument()
    expect(within(cards).getByRole('button', { name: 'Trapper' })).toHaveTextContent('3')
    await userEvent.click(within(cards).getByRole('button', { name: 'Trapper' }))
    expect(within(screen.getByRole('table', { name: 'Uploads' })).getAllByRole('row').slice(1)).toHaveLength(3)
    await userEvent.type(screen.getByLabelText('Filter the uploads'), 'DONA_02')
    expect(within(screen.getByRole('table', { name: 'Uploads' })).getAllByRole('row').slice(1)).toHaveLength(1)
  })

  it('says so when nothing has been uploaded, and still has the card of the platform', async () => {
    vi.mocked(api.uploads).mockResolvedValue({ results: [] })
    render(<UploadStatusPage onBack={() => {}} />)

    expect(await screen.findByText('No deployment has been uploaded yet.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trapper' })).toHaveTextContent('0')
    expect(screen.getByText('None uploaded from here yet')).toBeInTheDocument()
  })

  it('comes back from the breadcrumb', async () => {
    const onBack = vi.fn()
    render(<UploadStatusPage onBack={onBack} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Manage uploads' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('has the revisions to pick one: the cards and the table follow it', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions3 uploads', 'R00021 upload', 'R00012 uploads'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0001/ }))

    const table = screen.getByRole('table', { name: 'Uploads' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0001-DONA_01', 'R0001-DONA_02'])
    expect(within(screen.getByRole('region', { name: 'Uploads by platform' })).getByRole('button', { name: 'Trapper' })).toHaveTextContent('2')
    await userEvent.click(within(revisions).getByRole('button', { name: /^All revisions/ }))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(3)
  })

  it('has every revision of the project to pick from, also the ones with no upload yet', async () => {
    vi.mocked(api.uploads).mockResolvedValue({ results: UPLOADS, revisions: ['R0004', 'R0002', 'R0001'] })
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions3 uploads', 'R00040 uploads', 'R00021 upload', 'R00012 uploads'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0004/ }))
    expect(screen.getByText('No upload matches.')).toBeInTheDocument()
  })
})

