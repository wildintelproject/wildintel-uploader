import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../api'
import ReportPanel from './ReportPanel'
import type { Report } from '../types'

vi.mock('../api', () => ({
  api: { getReport: vi.fn(), reportUrl: (id: string, format: string) => `/api/reports/${id}/download?format=${format}` },
}))

const REPORT: Report = {
  id: '20261006-153012_validation_R0003-DONA_01', kind: 'validation', title: 'Validation of R0003-DONA_01', created_at: '2026-10-06T15:30:12+00:00',
  source_dir: '/home/me/R0003-DONA_01', deployment_id: null, checked: 4, parameters: {},
  checks: {
    corrupted: { label: 'Corrupted images', scope: 'images', ok: 3, failed: 1 },
    sequence: { label: 'Shooting order vs. filename sequence', scope: 'images', ok: 3, failed: 1 },
    structure: { label: 'Folder structure', scope: 'deployment', ok: 1, failed: 0 },
  },
  totals: { entries: 9, ok: 7, failed: 2 },
  entries: [
    { identifier: 'IMG_0001.JPG', check: 'corrupted', status: 'ok', message: 'can be read' },
    { identifier: 'IMG_0004.JPG', check: 'corrupted', status: 'failed', message: 'cannot identify image file' },
    { identifier: 'IMG_0002.JPG', check: 'sequence', status: 'failed', message: 'dated before IMG_0001.JPG, which has a lower number' },
  ],
}

beforeEach(() => { vi.mocked(api.getReport).mockResolvedValue(REPORT) })

describe('ReportPanel', () => {
  it('says what was checked and lists the images that failed, with the check and why', async () => {
    render(<ReportPanel reportId={REPORT.id} />)

    expect(await screen.findByText(/4 image\(s\) — 2 problem\(s\)/)).toBeInTheDocument()
    const summary = screen.getAllByRole('table')[0]
    expect(within(summary).getByText('Corrupted images').closest('tr')).toHaveTextContent('31')
    const failures = screen.getAllByRole('table')[1]
    expect(within(failures).getByText('IMG_0004.JPG').closest('tr')).toHaveTextContent('Corrupted images')
    expect(within(failures).getByText('IMG_0004.JPG').closest('tr')).toHaveTextContent('cannot identify image file')
    expect(within(failures).queryByText('IMG_0001.JPG')).not.toBeInTheDocument() // what passed isn't listed
  })

  it('can be narrowed to one check', async () => {
    render(<ReportPanel reportId={REPORT.id} />)
    await userEvent.selectOptions(await screen.findByLabelText('Check to show'), 'Shooting order vs. filename sequence (1)')

    const failures = screen.getAllByRole('table')[1]
    expect(within(failures).getByText('IMG_0002.JPG')).toBeInTheDocument()
    expect(within(failures).queryByText('IMG_0004.JPG')).not.toBeInTheDocument()
  })

  it('offers the report as a CSV and as a JSON file', async () => {
    render(<ReportPanel reportId={REPORT.id} />)

    expect(await screen.findByRole('link', { name: 'Download CSV' })).toHaveAttribute('href', `/api/reports/${REPORT.id}/download?format=csv`)
    expect(screen.getByRole('link', { name: 'Download JSON' })).toHaveAttribute('href', `/api/reports/${REPORT.id}/download?format=json`)
  })

  it('says so when nothing failed, and lists no failures', async () => {
    vi.mocked(api.getReport).mockResolvedValue({ ...REPORT, totals: { entries: 4, ok: 4, failed: 0 }, checks: { corrupted: { label: 'Corrupted images', scope: 'images', ok: 4, failed: 0 } }, entries: [] })
    render(<ReportPanel reportId={REPORT.id} />)

    expect(await screen.findByText(/4 image\(s\) — nothing failed/)).toBeInTheDocument()
    expect(screen.getAllByRole('table')).toHaveLength(1)
  })

  it('shows the first failures and the rest on request', async () => {
    const many = Array.from({ length: 150 }, (_, i) => ({ identifier: `IMG_${i}.JPG`, check: 'corrupted', status: 'failed' as const, message: 'bad' }))
    vi.mocked(api.getReport).mockResolvedValue({ ...REPORT, totals: { entries: 150, ok: 0, failed: 150 }, entries: many })
    render(<ReportPanel reportId={REPORT.id} />)

    await screen.findByText('IMG_0.JPG')
    expect(screen.queryByText('IMG_149.JPG')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show all 150' }))
    expect(screen.getByText('IMG_149.JPG')).toBeInTheDocument()
  })

  it('reports a report it cannot read', async () => {
    vi.mocked(api.getReport).mockRejectedValue(new Error("There is no report 'x'."))
    render(<ReportPanel reportId="x" />)
    expect(await screen.findByText("There is no report 'x'.")).toBeInTheDocument()
  })
})
