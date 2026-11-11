import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Report } from '../types'

vi.mock('../api', () => ({ api: { getReport: vi.fn(), reportUrl: (id: string, f: string) => `/report/${id}.${f}`, reportImageUrl: () => '/img' } }))
import { api } from '../api'
import DeploymentResults from './DeploymentResults'

const REPORT = {
  id: 'r1', parameters: {}, entries: [
    { check: 'sd_card', identifier: 'R0002-A', status: 'failed', message: 'You said the card 1, but the visit left 2B.' },
    { check: 'photo_count', identifier: 'R0002-A', status: 'failed', message: 'The folder has 12 photos — 33 photos missing.' },
    { check: 'corrupted', identifier: 'IMG_1.JPG', status: 'failed', message: 'Cannot be opened', tag: 'corrupt' },
  ],
  checks: {
    sd_card: { label: 'The SD card is the visit\'s', scope: 'deployment', failed: 1 },
    photo_count: { label: 'Number of photos is the visit\'s', scope: 'deployment', failed: 1 },
    corrupted: { label: 'Corrupted images', scope: 'images', failed: 1 },
    camera: { label: 'Camera', scope: 'deployment', failed: 0 },
  },
} as unknown as Report

describe('DeploymentResults', () => {
  beforeEach(() => vi.mocked(api.getReport).mockResolvedValue(REPORT))

  it('gives a row to each deployment, which opens to a table with a row for each of its errors', async () => {
    render(<DeploymentResults banner={null} byCheck={null} deployments={[
      { name: 'R0002-A', images: 12, failed: ['x', 'y', 'z'], reportId: 'r1' },
      { name: 'R0002-B', images: 8, failed: [] },
    ]} />)

    // the first deployment with problems comes opened
    const table = await screen.findByRole('table', { name: 'Problems of R0002-A' })
    await within(table).findByText(/the visit left 2B/)
    const rows = within(table).getAllByRole('row')
    expect(rows).toHaveLength(4) // header and one row for each failed check
    expect(within(rows[1]).getByText(/The SD card is the visit's/)).toBeInTheDocument()
    expect(within(rows[2]).getByText(/33 photos missing/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download report' })).toHaveAttribute('href', '/report/r1.csv')
    expect(screen.queryByRole('table', { name: 'Problems of R0002-B' })).not.toBeInTheDocument()
    expect(screen.getByText('3 checks failed')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Open R0002-B' }))
    expect(screen.getByText('Every check passed.')).toBeInTheDocument()
  })

  it('offers the images only of the checks that fail on images, and can show only the deployments with problems', async () => {
    render(<DeploymentResults banner={null} byCheck={null} deployments={[
      { name: 'R0002-A', images: 12, failed: ['x'], reportId: 'r1' },
      { name: 'R0002-B', images: 8, failed: [] },
    ]} />)
    await screen.findByRole('button', { name: /View the images of Corrupted images in R0002-A/ })
    expect(screen.queryByRole('button', { name: /View the images of The SD card/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox', { name: /Only deployments with problems/ }))
    expect(screen.queryByText('R0002-B')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /View the images of Corrupted images in R0002-A/ }))
    expect(await screen.findByRole('region', { name: 'Failures of Corrupted images' })).toBeInTheDocument()
  })

  it('says why a deployment could not be checked', () => {
    render(<DeploymentResults banner={null} byCheck={null} deployments={[{ name: 'R0002-C', images: 3, failed: [], error: 'The folder is gone' }]} />)
    expect(screen.getAllByText('Not checked').length).toBeGreaterThan(0)
    expect(screen.getByText('The folder is gone')).toBeInTheDocument()
  })
})
