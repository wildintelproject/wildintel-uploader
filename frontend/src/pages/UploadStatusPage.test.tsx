import { render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FieldDeployment } from '../types'

vi.mock('../api', () => ({ api: { fieldDeployments: vi.fn(), listResearchProjects: vi.fn(), getSettings: vi.fn() } }))
import { api } from '../api'
import UploadStatusPage, { uploadsOf } from './UploadStatusPage'

const dep = (id: string, collection: string, extra: Partial<FieldDeployment> = {}): FieldDeployment => ({
  deployment_id: id, collection, site: 'DONA_01', status: 'closed', start: '2026-06-10T09:00:00Z', end: '2026-08-05T08:00:00Z', setup_by: null, camera_id: null, card: null,
  photos_counted: null, start_session: collection, end_session: collection, images_stored: true, on_trapper: false, ...extra,
})
const DEPLOYMENTS = [dep('R0002-DONA_01', 'R0002', { on_trapper: true }), dep('R0002-DONA_02', 'R0002'), dep('R0001-DONA_01', 'R0001', { on_trapper: true }), dep('R0001-DONA_02', 'R0001', { status: 'open', end: null, images_stored: false })]

describe('UploadStatusPage', () => {
  beforeEach(() => {
    vi.mocked(api.getSettings).mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
    vi.mocked(api.listResearchProjects).mockResolvedValue({ results: [{ acronym: 'DONA', name: 'Doñana' }] } as never)
    vi.mocked(api.fieldDeployments).mockResolvedValue({ results: DEPLOYMENTS } as never)
  })

  it('counts, for each revision, its deployments, those ready to upload and those on Trapper', () => {
    expect(uploadsOf(DEPLOYMENTS)).toEqual([
      { collection: 'R0002', total: 2, ready: 2, onTrapper: 1, toUpload: 1 },
      { collection: 'R0001', total: 2, ready: 1, onTrapper: 1, toUpload: 0 },
    ])
  })

  it('shows the revisions with their uploads and the deployments still to be uploaded', async () => {
    render(<UploadStatusPage onBack={() => {}} />)

    const table = await screen.findByRole('table', { name: 'Revisions' })
    const rows = within(table).getAllByRole('row')
    expect(within(rows[1]).getByText('R0002')).toBeInTheDocument()
    expect(within(rows[1]).getByText('1 of 2')).toBeInTheDocument()
    expect(within(rows[1]).getByRole('progressbar', { name: 'R0002 uploaded' })).toHaveAttribute('aria-valuenow', '1')
    // the deployments start with the ones not on Trapper yet
    const deployments = await screen.findByRole('table', { name: 'Deployments' })
    expect(within(deployments).getByText('R0002-DONA_02')).toBeInTheDocument()
    expect(within(deployments).queryByText('R0002-DONA_01')).not.toBeInTheDocument()
  })
})
