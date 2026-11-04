import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import FileRowResults, { type FileRow } from './FileRowResults'

const rows: FileRow[] = [
  { row: 2, site: 'WICP_0001', session: 'R0001', result: 'already_kept', label: 'Already kept', message: 'The R0001 visit of WICP_0001 is already kept.' },
  { row: 3, site: 'WICP_0002', result: 'problem', label: 'Actions not valid', message: "The actions 'Flying' are not valid." },
  { row: 4, site: 'WICP_0003', result: 'ok', label: '', message: '' },
  { row: 5, site: 'WICP_0004', session: 'R0001', result: 'already_kept', label: 'Already kept', message: 'The R0001 visit of WICP_0004 is already kept.' },
]

describe('FileRowResults', () => {
  it('counts the rows and shows them one by one, the first with an error open, and only those with errors when asked', async () => {
    render(<FileRowResults rows={rows} />)
    const card = (title: string) => screen.getByRole('group', { name: title })
    expect(card('Rows read')).toHaveTextContent('Rows read4100%')
    expect(card('Ready')).toHaveTextContent('Ready1new visits')
    expect(card('Skipped / Existing')).toHaveTextContent('Skipped / Existing2unchanged')
    expect(card('With problems')).toHaveTextContent('With problems1needs attention')
    const table = screen.getByRole('table', { name: 'Rows of the file' })
    const line = (n: number) => within(table).getByRole('button', { name: new RegExp(`^(Open|Close) Row ${n}$`) }).closest('tr')!
    expect(line(4)).toHaveTextContent('4WICP_0003—Add')
    expect(line(2)).toHaveTextContent('2WICP_0001R0001Skipped / Existing')   // the row, the location, the revision and what became of it
    expect(within(table).queryByText('Diagnosis')).not.toBeInTheDocument()

    // the filters say how many rows each keeps
    for (const [name, count] of [['All', 4], ['Add', 1], ['Skipped', 2], ['Errors', 1]] as const) expect(screen.getByRole('button', { name: `${name} (${count})` })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Errors (1)' }))
    expect(screen.queryByRole('button', { name: 'Open Row 4' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Row 2$/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Open Row 3' }))
    expect(screen.getByRole('table', { name: 'Problems of Row 3' })).toHaveTextContent("The actions 'Flying' are not valid.")
  })

  it('sorts the rows by a column, and turns the order round when it is pressed again', async () => {
    render(<FileRowResults rows={rows} />)
    const order = () => within(screen.getByRole('table', { name: 'Rows of the file' })).getAllByRole('button', { name: /^(Open|Close) Row/ }).map((b) => b.getAttribute('aria-label')!.replace(/^\w+ Row /, ''))
    expect(order()).toEqual(['2', '3', '4', '5'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Row' }))
    expect(order()).toEqual(['5', '4', '3', '2'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Site ID' }))
    expect(order()).toEqual(['2', '3', '4', '5'])
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Status' }))
    expect(order()).toEqual(['3', '4', '2', '5'])   // by what the pill says: Actions not valid, Add, Skipped / Existing ×2
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
    await userEvent.click(screen.getByRole('button', { name: 'Errors (1)' }))
    expect(screen.queryByRole('button', { name: 'View the rows with Already kept' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View the rows with Actions not valid' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'All (4)' }))
    await userEvent.click(screen.getByRole('button', { name: 'Hide the rows with Already kept' }))
    expect(screen.queryByRole('table', { name: 'Rows with Already kept' })).not.toBeInTheDocument()
  })
})
