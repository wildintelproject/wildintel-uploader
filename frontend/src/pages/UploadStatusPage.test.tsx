import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UploadEntry, UploadedDeployment } from '../types'

vi.mock('../api', () => ({ api: { uploads: vi.fn(), listResearchProjects: vi.fn(), getSettings: vi.fn() } }))
import { api } from '../api'
import UploadStatusPage from './UploadStatusPage'

const sent = (extra: Partial<UploadEntry> = {}): UploadEntry => ({ destination: 'trapper', kind: 'uploaded', uploaded_at: '2026-10-20T10:00:00+00:00', parts: 2, location_created: true, deployment_created: true, url: 'https://trapper.example.org/geomap/deployment/detail/7/', ...extra })
const created = (id: string, uploads: UploadEntry[], site = 'DONA_01'): UploadedDeployment => ({ deployment_id: id, collection: id.split('-')[0], site, start: '2026-06-10T09:00:00Z', end: '2026-08-05T08:00:00Z', start_session: id.split('-')[0], uploads })
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

  it('lists the created deployments with where and when — the visit and the period — and a label for every platform each was uploaded to with the day, or that it was not uploaded', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const table = await screen.findByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Deployment', 'Where', 'When', 'Uploaded', 'What to do'])
    const rows = within(table).getAllByRole('row').slice(1)
    const cells = (row: HTMLElement) => within(row).getAllByRole('cell').map((c) => c.textContent)
    expect(rows.map(cells)).toEqual([
      ['R0002-DONA_01', 'DONA_01', 'Visit R0002 · DONA_0110 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper · 20 Oct 2026', 'View'],
      ['R0002-DONA_02', 'DONA_02', 'Visit R0002 · DONA_0210 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Not uploaded', ''],
      ['R0001-DONA_01', 'DONA_01', 'Visit R0001 · DONA_0110 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper · 1 Sep 2026', 'View'],
      ['R0001-DONA_02', 'DONA_02', 'Visit R0001 · DONA_0210 Jun 2026, 09:00 → 5 Aug 2026, 08:00', 'Trapper · synced', 'View'],
    ])
    expect(within(rows[1]).queryByRole('button', { name: /View the uploads/ })).not.toBeInTheDocument() // nothing was uploaded: nothing to see
  })

  it('opens, with View, the list of where a deployment was uploaded, when, and a link to reach the upload', async () => {
    render(<UploadStatusPage onBack={() => {}} />)
    await screen.findByRole('table', { name: 'Deployments' })

    await userEvent.click(screen.getByRole('button', { name: 'View the uploads of R0002-DONA_01' }))
    const list = screen.getByRole('list', { name: 'Uploads of R0002-DONA_01' })
    expect(list).toHaveTextContent('TrapperUploaded on 20 Oct 2026, 10:00 · 2 packages · location and deployment created there')
    expect(within(list).getByRole('link', { name: 'Open R0002-DONA_01 in Trapper' })).toHaveAttribute('href', 'https://trapper.example.org/geomap/deployment/detail/7/')
    await userEvent.click(screen.getByRole('button', { name: 'View the uploads of R0002-DONA_01' }))
    expect(screen.queryByRole('list', { name: 'Uploads of R0002-DONA_01' })).not.toBeInTheDocument()
  })

  it('goes to the visit that started a deployment', async () => {
    const onShowVisit = vi.fn()
    render(<UploadStatusPage onBack={() => {}} onShowVisit={onShowVisit} />)
    await screen.findByRole('table', { name: 'Deployments' })

    await userEvent.click(screen.getByRole('button', { name: 'Show the visit R0001 to DONA_01' }))
    expect(onShowVisit).toHaveBeenCalledWith({ session: 'R0001', site: 'DONA_01' })
  })

  it('has the revisions to pick one: its created deployments, with their uploads, and the progress follows it', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const revisions = await screen.findByRole('region', { name: 'Revision' })
    expect(within(revisions).getAllByRole('button').map((b) => b.textContent)).toEqual(['All revisions4 deployments', 'R00022 deployments', 'R00012 deployments'])
    await userEvent.click(within(revisions).getByRole('button', { name: /^R0002/ }))

    const table = screen.getByRole('table', { name: 'Deployments' })
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002-DONA_01', 'R0002-DONA_02'])
    const progress = screen.getByRole('region', { name: 'Upload progress' })
    expect(progress).toHaveTextContent('Uploads of R0002')
    expect(progress).toHaveTextContent('1 / 2')                                         // one uploaded, of the two deployments of the revision times the one uploader
    expect(progress).toHaveTextContent('2 deployments × 1 uploader: the most there can be')
    expect(within(progress).getByRole('progressbar', { name: 'Uploads done' })).toHaveAttribute('aria-valuenow', '1')
  })

  it('asks where they were uploaded: All and each uploader; the table follows it, and the Show filter', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const progress = await screen.findByRole('region', { name: 'Upload progress' })
    // to the right of the ring: All and each uploader, with what went to it
    expect(within(progress).getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(progress).getByRole('button', { name: 'Trapper' })).toHaveTextContent('3')
    expect(progress).toHaveTextContent('3 / 4')   // 4 deployments × 1 uploader
    await userEvent.click(within(progress).getByRole('button', { name: 'Trapper' }))
    expect(within(progress).getByRole('button', { name: 'Trapper' })).toHaveAttribute('aria-pressed', 'true')
    expect(progress).toHaveTextContent('All the uploads to Trapper')
    await userEvent.click(within(progress).getByRole('button', { name: 'All' }))
    expect(within(progress).getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(progress).getByRole('button', { name: 'Trapper' }))

    const table = screen.getByRole('table', { name: 'Deployments' })
    await userEvent.selectOptions(screen.getByLabelText('Show'), 'Not uploaded')
    expect(within(table).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)).toEqual(['R0002-DONA_02'])
    await userEvent.selectOptions(screen.getByLabelText('Show'), 'Uploaded')
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

  it('says so when no deployment is created', async () => {
    vi.mocked(api.uploads).mockResolvedValue({ deployments: [] })
    render(<UploadStatusPage onBack={() => {}} />)

    expect(await screen.findByText('No deployment is created yet: there is nothing to upload.')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Upload progress' })).toHaveTextContent('0 / 0')
  })

  it('comes back from the breadcrumb', async () => {
    const onBack = vi.fn()
    render(<UploadStatusPage onBack={onBack} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Manage uploads' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('has a link to the details of each deployment, and the way to upload the ones not uploaded', async () => {
    const onShowDeployment = vi.fn(), onUpload = vi.fn()
    render(<UploadStatusPage onBack={() => {}} onShowDeployment={onShowDeployment} onUpload={onUpload} />)
    await screen.findByRole('table', { name: 'Deployments' })

    await userEvent.click(screen.getByRole('button', { name: 'Show the details of the deployment R0001-DONA_01' }))
    expect(onShowDeployment).toHaveBeenCalledWith('R0001-DONA_01')
    expect(screen.queryByRole('button', { name: 'Upload the deployment R0002-DONA_01' })).not.toBeInTheDocument() // already uploaded
    await userEvent.click(screen.getByRole('button', { name: 'Upload the deployment R0002-DONA_02' }))
    expect(onUpload).toHaveBeenCalledWith({ researchProjectId: 'DONA', collection: 'R0002' })
  })
})

