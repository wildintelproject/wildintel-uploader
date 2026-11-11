import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Report } from '../types'

vi.mock('../api', () => ({ api: { getReport: vi.fn(), reportUrl: (id: string, f: string) => `/report/${id}.${f}`, reportImageUrl: () => '/img' } }))
import { api } from '../api'
import SessionResults from './SessionResults'

const REPORT = {
  id: 'r1', created_at: '2026-10-29T10:00:00', checked: 12, totals: { entries: 3, ok: 0, failed: 3, images_with_issues: 2 }, parameters: {},
  entries: [
    { check: 'corrupted', identifier: 'IMG_1.JPG', status: 'failed', message: 'Cannot be opened', tag: 'corrupt' },
    { check: 'camera', identifier: 'IMG_2.JPG', status: 'failed', message: 'camera Example is not the deployment\'s' },
  ],
  checks: { corrupted: { label: 'Corrupted images', scope: 'images', failed: 1 }, camera: { label: 'Camera', scope: 'images', failed: 1 }, exif: { label: 'Required photo data', scope: 'images', failed: 0 } },
} as unknown as Report

describe('SessionResults', () => {
  beforeEach(() => vi.mocked(api.getReport).mockResolvedValue(REPORT))

  it('opens a folder to a table with a row for each failed check', async () => {
    render(<SessionResults banner={null} byCheck={null} running={false} onLeaveOut={() => {}} checks={['corrupted', 'camera', 'exif']} folders={[
      { name: 'DONA_01', images: 12, reportId: 'r1', problem: true, included: true },
      { name: 'DONA_02', images: 8, reportId: null, problem: false, included: true },
    ]} />)

    const table = await screen.findByRole('table', { name: 'Problems of DONA_01' }) // the first folder with problems comes opened
    expect(within(table).getAllByRole('row')).toHaveLength(3) // header and one row for each failed check
    expect(within(table).getByText('Corrupted images')).toBeInTheDocument()
    expect(within(table).getByText(/camera Example is not the deployment's/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download report' })).toHaveAttribute('href', '/report/r1.csv')

    await userEvent.click(within(table).getByRole('button', { name: /View the images of Camera in DONA_01/ }))
    expect(await screen.findByRole('region', { name: 'Failures of Camera' })).toBeInTheDocument()
  })
})
