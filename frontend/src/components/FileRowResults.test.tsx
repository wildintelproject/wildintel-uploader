import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import FileRowResults, { type FileRow } from './FileRowResults'

const rows: FileRow[] = [
  { row: 2, site: 'WICP_0001', session: 'R0001', actions: 'Revision + Desinstallation', date: '2026-09-14', time: '11:40', result: 'already_kept', label: 'Already kept', message: 'The R0001 visit of WICP_0001 is already kept.' },
  { row: 3, site: 'WICP_0002', result: 'problem', label: 'Actions not valid', message: "The actions 'Flying' are not valid." },
  { row: 4, site: 'WICP_0003', result: 'ok', label: '', message: '', data: { location_id: 'WICP_0003', actions: 'Installation', camera_model: 'Browning' } },
  { row: 5, site: 'WICP_0004', session: 'R0001', date: '2026-09-10', time: '09:00', result: 'already_kept', label: 'Already kept', message: 'The R0001 visit of WICP_0004 is already kept.' },
]

describe('FileRowResults', () => {
  it('counts the rows and shows them one by one, the first with an error open, and keeps the ones of the figure that is pressed', async () => {
    render(<FileRowResults rows={rows} />)
    const card = (title: string) => screen.getByRole('button', { name: title })
    expect(card('Rows read')).toHaveTextContent('Rows read4100%')
    expect(card('Ready')).toHaveTextContent('Ready1new visits')
    expect(card('Skipped / Existing')).toHaveTextContent('Skipped / Existing2unchanged')
    expect(card('With problems')).toHaveTextContent('With problems1needs attention')
    const table = screen.getByRole('table', { name: 'Rows of the file' })
    const line = (n: number) => within(table).getByRole('button', { name: `View the contents of Row ${n}` }).closest('tr')!
    expect(line(4)).toHaveTextContent('4WICP_0003———Add')
    expect(line(3)).toHaveTextContent('3WICP_0002———Error')                  // an error says only that: which one is told by its errors
    expect(line(2)).toHaveTextContent('2WICP_0001R0001Revision + Desinstallation2026-09-14 11:40Skipped / Existing')   // the row, the location, the revision and what became of it
    expect(within(table).queryByText('Diagnosis')).not.toBeInTheDocument()

    // the figures are the filters: the one pressed keeps its rows, and pressed again lets them all be seen
    await userEvent.click(card('With problems'))
    expect(card('With problems')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('button', { name: 'View the contents of Row 4' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View the contents of Row 2' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'View the errors of Row 3' }))
    expect(screen.getByRole('table', { name: 'Problems of Row 3' })).toHaveTextContent("The actions 'Flying' are not valid.")
  })

  it('has a button to view what a row says and another, only where something is wrong, to view the errors', async () => {
    render(<FileRowResults rows={rows} labels={{ camera_model: 'Camera model' }} />)
    expect(screen.queryByRole('button', { name: 'View the errors of Row 4' })).not.toBeInTheDocument()     // a row to add has no errors
    expect(screen.getByRole('button', { name: 'View the errors of Row 2' })).toHaveAttribute('aria-expanded', 'true')   // the first row with errors starts open

    await userEvent.click(screen.getByRole('button', { name: 'View the contents of Row 4' }))
    const contents = screen.getByLabelText('Contents of Row 4')
    expect(within(contents).getByText('Camera model').closest('div')).toHaveTextContent('Camera modelBrowning')   // named as the field is, or by its key
    expect(within(contents).getByText('actions').closest('div')).toHaveTextContent('actionsInstallation')
    expect(screen.queryByRole('table', { name: 'Problems of Row 2' })).not.toBeInTheDocument()       // one thing is open at a time

    await userEvent.click(screen.getByRole('button', { name: 'View the contents of Row 4' }))
    expect(screen.queryByLabelText('Contents of Row 4')).not.toBeInTheDocument()
  })

  it('searches the rows by what they say: the words typed have to be all in the row', async () => {
    render(<FileRowResults rows={rows} />)
    const seen = () => within(screen.getByRole('table', { name: 'Rows of the file' })).getAllByRole('button', { name: /^View the contents of Row/ }).map((b) => b.getAttribute('aria-label')!.replace(/^.* Row /, ''))
    expect(seen()).toEqual(['2', '3', '4', '5'])

    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'wicp_0001')
    expect(seen()).toEqual(['2'])
    await userEvent.clear(screen.getByRole('searchbox', { name: 'Search the rows' }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'r0001 existing')                // the visit and what became of it
    expect(seen()).toEqual(['2', '5'])
    await userEvent.clear(screen.getByRole('searchbox', { name: 'Search the rows' }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'flying')                       // what is wrong with it
    expect(seen()).toEqual(['3'])

    // together with the filter of the figure that is pressed
    await userEvent.clear(screen.getByRole('searchbox', { name: 'Search the rows' }))
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'wicp')
    await userEvent.click(screen.getByRole('button', { name: 'Skipped / Existing' }))
    expect(seen()).toEqual(['2', '5'])
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'zzz')
    expect(screen.getByText(/No row matches/)).toBeInTheDocument()
  })

  it('goes ten rows at a time, and starts again from the first page when the search or the filter changes', async () => {
    const many: FileRow[] = Array.from({ length: 25 }, (_, i) => ({ row: i + 2, site: `WICP_${String(i + 1).padStart(4, '0')}`, session: 'R0001', actions: 'Installation', result: 'ok' as const, label: '', message: '' }))
    render(<FileRowResults rows={many} />)
    const seen = () => within(screen.getByRole('table', { name: 'Rows of the file' })).getAllByRole('button', { name: /^View the contents of Row/ }).map((b) => b.getAttribute('aria-label')!.replace(/^.* Row /, ''))
    expect(seen()).toEqual(['2', '3', '4', '5', '6', '7', '8', '9', '10', '11'])
    expect(screen.getByRole('status', { name: '' })).toHaveTextContent('Showing 1–10 of 25 rows')
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(seen()[0]).toBe('12')
    await userEvent.click(screen.getByRole('button', { name: 'Page 3' }))
    expect(seen()).toEqual(['22', '23', '24', '25', '26'])
    expect(screen.getByText(/Showing 21–25 of 25 rows/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()

    // what is shown changes: back to the first page
    await userEvent.type(screen.getByRole('searchbox', { name: 'Search the rows' }), 'wicp_001')
    expect(screen.getByText(/Showing 1–10 of 10 rows/)).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument()      // one page: nothing to turn
  })

  it('sorts the rows by a column, and turns the order round when it is pressed again', async () => {
    render(<FileRowResults rows={rows} />)
    const order = () => within(screen.getByRole('table', { name: 'Rows of the file' })).getAllByRole('button', { name: /^View the contents of Row/ }).map((b) => b.getAttribute('aria-label')!.replace(/^.* Row /, ''))
    expect(order()).toEqual(['2', '3', '4', '5'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Row' }))
    expect(order()).toEqual(['5', '4', '3', '2'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Site ID' }))
    expect(order()).toEqual(['2', '3', '4', '5'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by When' }))
    expect(order()).toEqual(['3', '4', '5', '2'])   // the rows with no date first, then the oldest day
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Status' }))
    expect(order()).toEqual(['4', '3', '2', '5'])   // by what the pill says: Add, Error, Skipped / Existing ×2
  })

  it('groups the rows by error, and shows the rows of the one that is picked', async () => {
    render(<FileRowResults rows={rows} />)
    await userEvent.click(screen.getByRole('tab', { name: 'By reason / error' }))
    const errors = screen.getByRole('table', { name: 'Errors of the file' })
    expect(within(errors).getByText('Already kept').closest('tr')).toHaveTextContent('2 rows')
    expect(screen.queryByRole('table', { name: /^Rows with/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'View the rows with Already kept' }))
    const picked = screen.getByRole('table', { name: 'Rows with Already kept' })
    expect(within(picked).getAllByRole('row').slice(1).map((r) => r.textContent)).toEqual([
      '2R0001WICP_0001The R0001 visit of WICP_0001 is already kept.', '5R0001WICP_0004The R0001 visit of WICP_0004 is already kept.',
    ])
    // the filter applies to this view too
    await userEvent.click(screen.getByRole('button', { name: 'With problems' }))
    expect(screen.queryByRole('button', { name: 'View the rows with Already kept' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View the rows with Actions not valid' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'With problems' }))   // pressed again: all the rows
    await userEvent.click(screen.getByRole('button', { name: 'Hide the rows with Already kept' }))
    expect(screen.queryByRole('table', { name: 'Rows with Already kept' })).not.toBeInTheDocument()
  })
})
