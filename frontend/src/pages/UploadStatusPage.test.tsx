import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UploadEntry, UploadedDeployment } from '../types'

vi.mock('../api', () => ({ api: { uploads: vi.fn(), listResearchProjects: vi.fn(), getSettings: vi.fn() } }))
import { api } from '../api'
import UploadStatusPage from './UploadStatusPage'

const sent = (extra: Partial<UploadEntry> = {}): UploadEntry => ({ destination: 'trapper', kind: 'uploaded', uploaded_at: '2026-10-20T10:00:00+00:00', parts: 2, location_created: true, deployment_created: true, ...extra })
const created = (id: string, uploads: UploadEntry[], site = 'DONA_01'): UploadedDeployment => ({ deployment_id: id, collection: id.split('-')[0], site, start: '2026-06-10T09:00:00Z', end: '2026-08-05T08:00:00Z', uploads })
const DEPLOYMENTS = [
  created('R0002-DONA_01', [sent()]),
  created('R0002-DONA_02', [], 'DONA_02'),
  created('R0001-DONA_01', [sent({ uploaded_at: '2026-09-01T08:30:00+00:00', parts: 1, location_created: false })]),
  created('R0001-DONA_02', [sent({ kind: 'synced', uploaded_at: null, parts: null, location_created: null, deployment_created: null })], 'DONA_02'),
]

describe('UploadStatusPage', () => {
  beforeEach(() => {
    vi.mocked(api.getSettings).mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
    vi.mocked(api.listResearchProjects).mockResolvedValue({ results: [{ acronym: 'DONA', name: 'Doñana' }] } as never)
    vi.mocked(api.uploads).mockResolvedValue({ deployments: DEPLOYMENTS })
  })

  it('lists the created deployments and, for each, a label for every platform it was uploaded to with the day — or that it was not uploaded', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const table = await screen.findByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Revision', 'Where', 'Uploaded'])
    const rows = within(table).getAllByRole('row').slice(1)
    const cells = (row: HTMLElement) => within(row).getAllByRole('cell').map((c) => c.textContent)
    expect(rows.map(cells)).toEqual([
      ['R0002-DONA_01', 'R0002', 'DONA_01', 'Trapper · 20 Oct 2026'],
      ['R0002-DONA_02', 'R0002', 'DONA_02', 'Not uploaded'],
      ['R0001-DONA_01', 'R0001', 'DONA_01', 'Trapper · 1 Sep 2026'],
      ['R0001-DONA_02', 'R0001', 'DONA_02', 'Trapper · synced'],
    ])
    expect(within(rows[0]).getByText('Trapper · 20 Oct 2026')).toHaveAttribute('title', '2 packages · location and deployment created there')
    expect(within(rows[2]).getByText('Trapper · 1 Sep 2026')).toHaveAttribute('title', '1 package · deployment created there')
    expect(within(rows[3]).getByText('Trapper · synced')).toHaveAttribute('title', 'It came from Trapper: it was not sent from here')
  })

  it('has the revisions to pick one: its created deployments, with their uploads, and the cards follow it', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 deployments', 'R00022 deployments', 'R00012 deployments'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0002/ }))

    const table = screen.getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002-DONA_01', 'R0002-DONA_02'])
    const cards = screen.getByRole('region', { name: 'Uploads by platform' })
    expect(within(cards).getByText('Created in R0002').parentElement).toHaveTextContent('2')
    expect(within(cards).getByText('Created in R0002').parentElement).toHaveTextContent('1 uploaded · 1 not yet')
    expect(within(cards).getByRole('button', { name: 'Not uploaded' })).toHaveTextContent('1')
    expect(within(cards).getByRole('button', { name: 'Trapper' })).toHaveTextContent('1')
  })

  it('has a card for not uploaded and one for each platform, that filter the table', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const cards = await screen.findByRole('region', { name: 'Uploads by platform' })
    await userEvent.click(within(cards).getByRole('button', { name: 'Not uploaded' }))
    const table = screen.getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002-DONA_02'])
    await userEvent.click(within(cards).getByRole('button', { name: 'Trapper' }))
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(3)
    await userEvent.type(screen.getByLabelText('Filter the deployments'), 'R0001-DONA_02')
    expect(within(table).getAllByRole('row').slice(1)).toHaveLength(1)
  })

  it('has every revision of the project to pick from, also the ones with nothing created yet', async () => {
    vi.mocked(api.uploads).mockResolvedValue({ deployments: DEPLOYMENTS, revisions: ['R0004', 'R0002', 'R0001'] })
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 deployments', 'R00040 deployments', 'R00022 deployments', 'R00012 deployments'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0004/ }))
    expect(screen.getByText('No deployment matches.')).toBeInTheDocument()
  })

  it('says so when no deployment is created, and still has the card of the platform', async () => {
    vi.mocked(api.uploads).mockResolvedValue({ deployments: [] })
    render(<UploadStatusPage onBack={() => {}} />)

    expect(await screen.findByText('No deployment is created yet: there is nothing to upload.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trapper' })).toHaveTextContent('0')
  })

  it('comes back from the breadcrumb', async () => {
    const onBack = vi.fn()
    render(<UploadStatusPage onBack={onBack} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Manage uploads' }))
    expect(onBack).toHaveBeenCalled()
  })
})
