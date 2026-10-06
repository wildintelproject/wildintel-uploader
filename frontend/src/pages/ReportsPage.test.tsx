import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../api'
import ReportsPage from './ReportsPage'
import type { ReportSummary } from '../types'

vi.mock('../api', () => ({
  api: { listReports: vi.fn(), deleteReport: vi.fn(), getReport: vi.fn(), reportUrl: (id: string, format: string) => `/api/reports/${id}/download?format=${format}` },
}))

const SUMMARIES: ReportSummary[] = [
  { id: '20261006-153012_validation_R0003-DONA_01', kind: 'validation', title: 'Validation of R0003-DONA_01', created_at: '2026-10-06T15:30:12+00:00',
    source_dir: '/home/me/R0003-DONA_01', deployment_id: null, checked: 241, totals: { entries: 1000, ok: 998, failed: 2 } },
  { id: '20261006-153500_preprocessing_R0003-DONA_01', kind: 'preprocessing', title: 'Preprocessing of R0003-DONA_01', created_at: '2026-10-06T15:35:00+00:00',
    source_dir: '/home/me/R0003-DONA_01', deployment_id: 'R0003-DONA_01', checked: 241, totals: { entries: 241, ok: 241, failed: 0 } },
]

beforeEach(() => {
  vi.mocked(api.listReports).mockResolvedValue(SUMMARIES)
  vi.mocked(api.deleteReport).mockResolvedValue({ status: 'ok' })
})

describe('ReportsPage', () => {
  it('lists the reports with what they found, and offers their downloads', async () => {
    render(<ReportsPage />)

    const validation = await screen.findByRole('listitem', { name: 'Validation of R0003-DONA_01' })
    expect(validation).toHaveTextContent('2 problem(s)')
    expect(screen.getByRole('listitem', { name: 'Preprocessing of R0003-DONA_01' })).toHaveTextContent('nothing failed')
    expect(screen.getAllByRole('link', { name: 'CSV' })[0]).toHaveAttribute('href', `/api/reports/${SUMMARIES[0].id}/download?format=csv`)
  })

  it('deletes a report only after asking again', async () => {
    render(<ReportsPage />)
    await screen.findByRole('listitem', { name: 'Validation of R0003-DONA_01' })

    await userEvent.click(screen.getAllByRole('button', { name: 'Delete' })[0])
    expect(api.deleteReport).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Delete it' }))

    expect(api.deleteReport).toHaveBeenCalledWith(SUMMARIES[0].id)
    expect(screen.queryByRole('listitem', { name: 'Validation of R0003-DONA_01' })).not.toBeInTheDocument()
  })

  it('says so when there are none', async () => {
    vi.mocked(api.listReports).mockResolvedValue([])
    render(<ReportsPage />)
    expect(await screen.findByText(/There are no reports yet/)).toBeInTheDocument()
  })
})
