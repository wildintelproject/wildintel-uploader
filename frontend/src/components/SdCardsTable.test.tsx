import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SdCardsTable from './SdCardsTable'
import type { SdCard } from '../types'

const card = (label: string): SdCard => ({ label, brand: 'SanDisk', capacity: '64 GB', in_service: null, research_project: 'WICP_02', status: 'ready' })
const cards = ['1', '2', '3', '4', '5', '6'].map(card)

describe('SdCardsTable', () => {
  it('opens as labels, and pages the cards four at a time, in the labels and in the table', async () => {
    render(<SdCardsTable cards={cards} selected="" onSelect={() => {}} empty="none" />)

    expect(screen.getByRole('button', { name: 'Show the SD cards as labels', pressed: true })).toBeInTheDocument()
    expect(within(screen.getByRole('group', { name: 'SD cards' })).getAllByRole('button')).toHaveLength(4)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 1–4 of 6 SD cards')

    await userEvent.click(screen.getByRole('button', { name: 'Show the SD cards as a table' }))
    expect(within(screen.getByRole('table', { name: 'SD cards' })).getAllByRole('row')).toHaveLength(1 + 4)          // the head and four cards
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(within(screen.getByRole('table', { name: 'SD cards' })).getAllByRole('row')).toHaveLength(1 + 2)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 5–6 of 6 SD cards')
  })

  it('picks a card by pressing its label, and lets it go when pressed again', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(<SdCardsTable cards={cards} selected="" onSelect={onSelect} empty="none" />)
    await userEvent.click(screen.getByRole('button', { name: 'Pick the SD card 3' }))
    expect(onSelect).toHaveBeenCalledWith('3')
    rerender(<SdCardsTable cards={cards} selected="3" onSelect={onSelect} empty="none" />)
    await userEvent.click(screen.getByRole('button', { name: 'Let go of the SD card 3' }))
    expect(onSelect).toHaveBeenLastCalledWith('')
  })

  const mixed: SdCard[] = [
    { ...card('10'), brand: 'Kingston', capacity: '128 GB', status: 'active' },
    { ...card('2'), brand: 'SanDisk', capacity: '32 GB', status: 'ready' },
    { ...card('1'), brand: 'Lexar', capacity: '1 TB', status: 'archived' },
  ]
  const labels = () => within(screen.getByRole('group', { name: 'SD cards' })).getAllByRole('button').map((b) => b.getAttribute('aria-label'))

  it('sorts the cards by their label as numbers, and by the others with Sort by', async () => {
    render(<SdCardsTable cards={mixed} selected="" onSelect={() => {}} empty="none" />)
    expect(labels()).toEqual(['Pick the SD card 1', 'Pick the SD card 2', 'Pick the SD card 10'])
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'Capacity')
    expect(labels()).toEqual(['Pick the SD card 2', 'Pick the SD card 10', 'Pick the SD card 1'])
    await userEvent.selectOptions(screen.getByLabelText('Sort by'), 'Brand')
    expect(labels()).toEqual(['Pick the SD card 10', 'Pick the SD card 1', 'Pick the SD card 2'])
  })

  it('sorts the table by a column pressing its head, the other way when pressed again', async () => {
    render(<SdCardsTable cards={mixed} selected="" onSelect={() => {}} empty="none" />)
    await userEvent.click(screen.getByRole('button', { name: 'Show the SD cards as a table' }))
    const firsts = () => within(screen.getByRole('table', { name: 'SD cards' })).getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[1].textContent)
    expect(screen.getByRole('columnheader', { name: /Card/ })).toHaveAttribute('aria-sort', 'ascending')
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Status' }))
    expect(firsts()).toEqual(['2', '10', '1'])        // ready, active, archived: the order of their life
    await userEvent.click(screen.getByRole('button', { name: 'Sort by Status' }))
    expect(firsts()).toEqual(['1', '10', '2'])
    expect(screen.getByRole('columnheader', { name: /Status/ })).toHaveAttribute('aria-sort', 'descending')
  })

  it('filters by status, with the statuses the cards have, told in the active filters and put back by Reset', async () => {
    render(<SdCardsTable cards={mixed} selected="" onSelect={() => {}} empty="none" />)
    const status = screen.getByLabelText('Status')
    expect(within(status).getAllByRole('option').map((o) => o.textContent)).toEqual(['All', 'Ready', 'Active', 'Archived'])
    await userEvent.selectOptions(status, 'Active')
    expect(labels()).toEqual(['Pick the SD card 10'])
    expect(screen.getByText('Status: Active')).toBeInTheDocument()
    expect(screen.getByText('1 of 3 SD cards match')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /Reset/ }))
    expect(labels()).toHaveLength(3)
    expect(screen.getByText('Status: All')).toBeInTheDocument()
  })

  it('says why there is nothing to pick', () => {
    render(<SdCardsTable cards={[]} selected="" onSelect={() => {}} empty="No SD cards for DONA in the settings yet." />)
    expect(screen.getByText('No SD cards for DONA in the settings yet.')).toBeInTheDocument()
  })

  it('shows only the search field when asked, and picks from the list under it', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(<SdCardsTable cards={cards} selected="" onSelect={onSelect} empty="none" />)

    await userEvent.click(screen.getByRole('button', { name: 'Show only the search field' }))
    expect(screen.queryByRole('table', { name: 'SD cards' })).not.toBeInTheDocument()
    const field = screen.getByLabelText('Filter the SD cards')
    expect(field).toHaveAttribute('placeholder', 'Select the SD card the images come from…')
    await userEvent.click(field)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()              // nothing typed, nothing offered: the list fills in as it is written

    await userEvent.type(field, '5')
    expect(within(screen.getByRole('listbox', { name: 'SD cards' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['5 — SanDisk 64 GB'])
    await userEvent.click(screen.getByRole('option', { name: /^5/ }))
    expect(onSelect).toHaveBeenCalledWith('5')
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    // the one picked is what the field says, once the list is closed
    rerender(<SdCardsTable cards={cards} selected="5" onSelect={onSelect} empty="none" />)
    expect(field).toHaveValue('5 — SanDisk 64 GB')
    // and the keys pick too
    await userEvent.click(screen.getByRole('button', { name: 'Show the SD cards as a table' }))
    expect(screen.getByRole('table', { name: 'SD cards' })).toBeInTheDocument()
  })
})
