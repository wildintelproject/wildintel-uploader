import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import SelectionBar from './SelectionBar'

const choices = (pick: (n: string) => void) => [
  { label: 'All results', count: 3, onPick: () => pick('all') }, { label: 'Not uploaded', count: 2, onPick: () => pick('new') }, { label: 'None', onPick: () => pick('none') },
]

describe('SelectionBar', () => {
  it('says what is picked, with a dash when only some are, a tick when all are and nothing when none', () => {
    const { rerender } = render(<SelectionBar total={3} selected={1} detail="24 images" choices={[]} onToggleAll={vi.fn()} onClear={vi.fn()} />)
    expect(document.querySelector('[data-selection-count]')).toHaveTextContent('1 of 3 selected · 24 images')
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'mixed')
    rerender(<SelectionBar total={3} selected={3} choices={[]} onToggleAll={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'true')
    rerender(<SelectionBar total={3} selected={0} choices={[]} onToggleAll={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByRole('checkbox')).toHaveAttribute('aria-checked', 'false')
    expect(screen.queryByRole('button', { name: 'Clear selection' })).not.toBeInTheDocument()
  })

  it('the box picks all or none, the chevron opens the choices and closes with Escape, and Clear selection clears', async () => {
    const toggle = vi.fn(), clear = vi.fn(), pick = vi.fn()
    render(<SelectionBar total={3} selected={2} choices={choices(pick)} onToggleAll={toggle} onClear={clear} />)

    await userEvent.click(screen.getByRole('checkbox'))
    expect(toggle).toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: 'Choose what to select' }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Not uploaded/ }))
    expect(pick).toHaveBeenCalledWith('new')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Choose what to select' }))
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(clear).toHaveBeenCalled()
  })
})
