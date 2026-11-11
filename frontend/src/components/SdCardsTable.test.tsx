import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SdCardsTable from './SdCardsTable'
import type { SdCard } from '../types'

const card = (label: string): SdCard => ({ label, brand: 'SanDisk', capacity: '64 GB', in_service: null, research_project: 'WICP_02', status: 'ready' })
const cards = ['1', '2', '3', '4', '5', '6'].map(card)

describe('SdCardsTable', () => {
  it('pages the cards four at a time, in the table and in the labels', async () => {
    render(<SdCardsTable cards={cards} selected="" onSelect={() => {}} empty="none" />)

    expect(within(screen.getByRole('table', { name: 'SD cards' })).getAllByRole('row')).toHaveLength(1 + 4)          // the head and four cards
    expect(screen.getByRole('status')).toHaveTextContent('Showing 1–4 of 6 SD cards')
    await userEvent.click(screen.getByRole('button', { name: 'Next page' }))
    expect(within(screen.getByRole('table', { name: 'SD cards' })).getAllByRole('row')).toHaveLength(1 + 2)
    expect(screen.getByRole('status')).toHaveTextContent('Showing 5–6 of 6 SD cards')

    await userEvent.click(screen.getByRole('button', { name: 'Show the SD cards as labels' }))      // back to the first page, four labels
    expect(within(screen.getByRole('group', { name: 'SD cards' })).getAllByRole('button')).toHaveLength(4)
  })

  it('picks a card by pressing its row, and tells which one with its label', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(<SdCardsTable cards={cards} selected="" onSelect={onSelect} empty="none" />)
    await userEvent.click(screen.getByRole("row", { name: /\b3\b/ }))
    expect(onSelect).toHaveBeenCalledWith('3')
    rerender(<SdCardsTable cards={cards} selected="3" onSelect={onSelect} empty="none" />)
    await userEvent.click(screen.getByRole("row", { name: /\b3\b/ }))
    expect(onSelect).toHaveBeenLastCalledWith('')                                                // pressed again: let go
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
