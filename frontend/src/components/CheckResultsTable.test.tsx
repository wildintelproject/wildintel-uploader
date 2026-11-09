import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import CheckResultsTable from './CheckResultsTable'
import type { Report } from '../types'

const report = {
  id: 'r1', created_at: '2026-11-09T10:00:00', checked: 3, totals: { images_with_issues: 2 }, parameters: {},
  checks: {
    corrupted: { label: 'Corrupted images', scope: 'images', ok: 3, failed: 0 },
    exif: { label: 'Required EXIF fields', scope: 'images', ok: 1, failed: 2 },
  },
  entries: [
    { identifier: 'IMG_0001.JPG', check: 'corrupted', status: 'ok', message: '' },
    { identifier: 'IMG_0002.JPG', check: 'corrupted', status: 'ok', message: '' },
    { identifier: 'IMG_0003.JPG', check: 'corrupted', status: 'ok', message: '' },
    { identifier: 'IMG_0001.JPG', check: 'exif', status: 'failed', message: 'No camera id', tag: 'No camera id', taken: '2026-10-25T00:03:07' },
    { identifier: 'IMG_0002.JPG', check: 'exif', status: 'failed', message: 'No camera id', tag: 'No camera id', taken: '2026-10-25T00:06:14' },
    { identifier: 'IMG_0003.JPG', check: 'exif', status: 'ok', message: '' },
  ],
} as unknown as Report
const options = [{ value: 'corrupted', label: 'Corrupted images' }, { value: 'exif', label: 'Required EXIF fields' }]
const mount = () => render(<CheckResultsTable report={report} options={options} enabled={new Set(['corrupted', 'exif'])} required={new Set<string>()} />)

describe('CheckResultsTable', () => {
  it('lists the tests, and the chevron of one that failed opens its images — View details opens the panel of the image', async () => {
    mount()
    const table = screen.getByRole('table', { name: 'Tests' })
    expect(within(table).getByText('Corrupted images')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Show the failures of Corrupted images/ })).not.toBeInTheDocument()   // a test that passed has nothing to open
    await userEvent.click(screen.getByRole('button', { name: 'Show the failures of Required EXIF fields' }))
    expect(screen.getByText(/failing .Required EXIF fields. \(2 files\)/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'View details of IMG_0001.JPG' }))
    const panel = screen.getByRole('dialog', { name: 'Details of IMG_0001.JPG' })
    expect(within(panel).getByText('Corrupted images')).toBeInTheDocument()
    expect(within(panel).getByText('Passed')).toBeInTheDocument()
    expect(within(panel).getAllByText('No camera id').length).toBeGreaterThan(0)
  })

  it('filters the tests by what they found and by what is typed', async () => {
    mount()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Results' }), 'issues')
    const table = screen.getByRole('table', { name: 'Tests' })
    expect(within(table).queryByText('Corrupted images')).not.toBeInTheDocument()
    expect(within(table).getByText('Required EXIF fields')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Results' }), 'passed')
    expect(within(table).getByText('Corrupted images')).toBeInTheDocument()
    expect(within(table).queryByText('Required EXIF fields')).not.toBeInTheDocument()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Results' }), 'all')
    await userEvent.type(screen.getByRole('textbox', { name: 'Search the results' }), 'exif')
    expect(within(table).queryByText('Corrupted images')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Active filters')).toHaveTextContent('Search: exif')
  })

  it('groups by image: each one with what the tests found in it, and the chevron lists every test', async () => {
    mount()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Group by' }), 'image')
    const table = screen.getByRole('table', { name: 'By image' })
    expect(within(table).getByText('IMG_0001.JPG').closest('tr')).toHaveTextContent('1 failure of 2')
    expect(within(table).getByText('IMG_0003.JPG').closest('tr')).toHaveTextContent('2 passed')
    await userEvent.click(screen.getByRole('button', { name: 'Show the tests of IMG_0001.JPG' }))
    const list = screen.getByRole('list', { name: 'Tests of IMG_0001.JPG' })
    expect(within(list).getByText('Corrupted images')).toBeInTheDocument()
    expect(within(list).getByText('No camera id')).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Results' }), 'issues')
    expect(within(table).queryByText('IMG_0003.JPG')).not.toBeInTheDocument()
  })

  it('searches the images that failed a test, and shows them as a list', async () => {
    mount()
    await userEvent.click(screen.getByRole('button', { name: 'Show the failures of Required EXIF fields' }))
    const failures = screen.getByRole('region', { name: 'Failures of Required EXIF fields' })
    expect(within(failures).getAllByRole('button', { name: /^View details of/ })).toHaveLength(2)
    await userEvent.type(within(failures).getByRole('searchbox', { name: 'Search by filename' }), '0002')
    expect(within(failures).getAllByRole('button', { name: /^View details of/ })).toHaveLength(1)
    await userEvent.click(within(failures).getByRole('button', { name: 'List view' }))
    const list = within(failures).getByRole('table', { name: 'Failures of Required EXIF fields, as a list' })
    expect(list).toHaveTextContent('IMG_0002.JPG')
    expect(list).not.toHaveTextContent('IMG_0001.JPG')
    expect(failures).toHaveTextContent('Showing 1–1 of 1 images')
  })

  it('by image, the buttons of the toolbar show the images as pictures or as a list', async () => {
    mount()
    expect(screen.queryByRole('button', { name: 'Grid view' })).not.toBeInTheDocument()      // by test there is nothing to see as pictures
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Group by' }), 'image')
    expect(screen.getByRole('button', { name: 'List view' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Grid view' }))
    const pictures = screen.getByRole('list', { name: 'The images, as pictures' })
    expect(within(pictures).getAllByRole('listitem')).toHaveLength(3)
    expect(within(pictures).getByText('IMG_0001.JPG').closest('li')).toHaveTextContent('1 failure of 2')
    await userEvent.click(within(pictures).getByRole('button', { name: 'View details of IMG_0003.JPG' }))
    expect(screen.getByRole('dialog', { name: 'Details of IMG_0003.JPG' })).toBeInTheDocument()
  })
})
