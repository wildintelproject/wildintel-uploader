import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../api'
import ValidationDashboard from './ValidationDashboard'
import type { Report } from '../types'

vi.mock('../api', () => ({
  api: {
    getReport: vi.fn(), reportUrl: (id: string, format: string) => `/api/reports/${id}/download?format=${format}`,
    reportImageUrl: (id: string, path: string) => `/api/reports/${id}/image?path=${path}`,
  },
}))

const REPORT: Report = {
  id: 'r1', kind: 'validation', title: 'Validation of X', created_at: '2026-10-06T09:45:12+00:00', source_dir: '/x', deployment_id: null, checked: 241, parameters: {},
  checks: {
    corrupted: { label: 'Corrupted images', scope: 'images', ok: 238, failed: 3 },
    sequence: { label: 'Shooting order', scope: 'images', ok: 241, failed: 0 },
  },
  totals: { entries: 482, ok: 479, failed: 3, images_with_issues: 3 },
  entries: [{ identifier: 'IMG_0001.JPG', check: 'corrupted', status: 'failed', message: 'truncated', tag: 'Corrupted' }],
}

beforeEach(() => { vi.mocked(api.getReport).mockResolvedValue(REPORT) })

const renderIt = (props: Partial<Parameters<typeof ValidationDashboard>[0]> = {}) => render(
  <ValidationDashboard title="Validation" subtitle="R0003-DONA_01 · 241 image(s)" reportId="r1" running={false} canRun onRun={vi.fn()} {...props}>
    {({ report, open }) => <button type="button" onClick={() => open('corrupted')}>{report ? 'table with a report' : 'table'}</button>}
  </ValidationDashboard>,
)

describe('ValidationDashboard', () => {
  it('shows what the validation was run on, the images that are fine and the tests that failed', async () => {
    renderIt()

    expect(screen.getByText('R0003-DONA_01 · 241 image(s)')).toBeInTheDocument()
    expect(await screen.findByText('238')).toBeInTheDocument()  // valid images: 241 − 3
    expect(screen.getByText('Valid images')).toBeInTheDocument()
    expect(screen.getByText('Images with issues').previousElementSibling).toHaveTextContent('3')
    expect(screen.getByText('Tests executed').previousElementSibling).toHaveTextContent('2')
    expect(screen.getByText('Tests with errors').previousElementSibling).toHaveTextContent('1')
    expect(screen.getByText(/Last run:/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download CSV' })).toHaveAttribute('href', '/api/reports/r1/download?format=csv')
  })

  it('has nothing to summarize before the first run, and runs the validation from its button', async () => {
    const onRun = vi.fn()
    renderIt({ reportId: null, onRun })

    expect(screen.queryByText('Valid images')).not.toBeInTheDocument()
    expect(screen.getByText('table')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Run validation' }))
    expect(onRun).toHaveBeenCalled()
  })

  it('says it is validating, and cannot be run again meanwhile — or with no test to run', () => {
    const { unmount } = renderIt({ running: true })
    expect(screen.getByRole('button', { name: 'Validating…' })).toBeDisabled()
    unmount()
    renderIt({ canRun: false })
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeDisabled()
  })

  it('opens the failures of a test, and closes them with its breadcrumb', async () => {
    renderIt()
    await userEvent.click(await screen.findByRole('button', { name: 'table with a report' }))

    expect(screen.getByRole('region', { name: 'Failures of Corrupted images' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '← Validation' }))
    expect(screen.queryByRole('region', { name: /Failures of/ })).not.toBeInTheDocument()
  })
})
