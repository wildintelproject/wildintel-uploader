import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import PickTable, { LabelFrame } from './PickTable'

interface Row { id: string; size: number; sent: boolean; locked?: boolean }
const ROWS: Row[] = [{ id: 'R1-A', size: 10, sent: true }, { id: 'R1-B', size: 20, sent: false }, { id: 'R1-C', size: 5, sent: false, locked: true }]

function Many() {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  return (
    <PickTable
      items={ROWS} keyOf={(r) => r.id}
      many={{ selected, onChange: setSelected, selectable: (r) => !r.locked, detail: (rs) => `${rs.reduce((n, r) => n + r.size, 0)} MB`,
        choices: [{ label: 'All results', pick: (x) => x }, { label: 'Not sent', pick: (x) => x.filter((r) => !r.sent) }, { label: 'None', pick: () => [], showCount: false }] }}
      columns={[{ label: 'Id', cell: (r) => r.id }, { label: 'Size', cell: (r) => `${r.size} MB` }]}
      searchText={(r) => r.id}
      renderLabel={(r, on, press) => <LabelFrame picked={on} name={r.id} onPress={press}>{r.id}</LabelFrame>}
      names={{ table: 'Rows', search: 'Search the rows', items: 'rows', pick: (r) => r.id, pickPlaceholder: 'Type to pick a row…' }}
      optionLabel={(r) => r.id} searchPlaceholder="Search…"
    />
  )
}

describe('PickTable, picking many', () => {
  it('has a box in each row, not on the ones that cannot be picked, and the bar tells what is picked', async () => {
    render(<Many />)
    expect(document.querySelector('[data-selection-count]')).toHaveTextContent('0 of 2 selected')                       // the locked one is not counted
    expect(screen.getByRole('checkbox', { name: 'R1-C' })).toBeDisabled()
    await userEvent.click(screen.getByRole('checkbox', { name: 'R1-B' }))
    expect(document.querySelector('[data-selection-count]')).toHaveTextContent('1 of 2 selected · 20 MB')
    expect(screen.getByRole('checkbox', { name: 'Select all' })).toHaveAttribute('aria-checked', 'mixed')
    await userEvent.click(screen.getByRole('row', { name: /R1-A/ }))                              // a press on the row picks it too
    expect(screen.getByRole('checkbox', { name: 'Select none' })).toHaveAttribute('aria-checked', 'true')
  })

  it('has the choices of the chevron, which count what they pick, and Clear selection', async () => {
    render(<Many />)
    await userEvent.click(screen.getByRole('button', { name: 'Choose what to select' }))
    const menu = within(screen.getByRole('menu'))
    expect(menu.getByRole('menuitem', { name: /All results/ })).toHaveTextContent('2')
    expect(menu.getByRole('menuitem', { name: /Not sent/ })).toHaveTextContent('1')
    await userEvent.click(menu.getByRole('menuitem', { name: /Not sent/ }))
    expect(screen.getByRole('checkbox', { name: 'R1-B' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R1-A' })).not.toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(document.querySelector('[data-selection-count]')).toHaveTextContent('0 of 2 selected')
  })

  it('keeps the selection in the labels and in the search field that picks from a list', async () => {
    render(<Many />)
    await userEvent.click(screen.getByRole('button', { name: 'Show the rows as labels' }))
    await userEvent.click(screen.getByRole('button', { name: 'Pick R1-A' }))
    expect(screen.getByRole('button', { name: 'Let go of R1-A' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Show only the search field' }))
    await userEvent.type(screen.getByLabelText('Search the rows'), 'R1')
    await userEvent.click(within(screen.getByRole('listbox')).getByRole('option', { name: /R1-B/ }))
    expect(screen.getByRole('listbox')).toBeInTheDocument()                                       // the list stays: many are picked
    await userEvent.click(screen.getByRole('button', { name: 'Show the rows as a table' }))
    expect(screen.getByRole('checkbox', { name: 'R1-A' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R1-B' })).toBeChecked()
  })
})
