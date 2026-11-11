import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import RevisionSquares from './RevisionSquares'

const revisions = (n: number) => Array.from({ length: n }, (_, i) => ({ id: `R000${n - i}`, label: `R000${n - i}`, note: `${i} of 4 done` }))

describe('RevisionSquares', () => {
  it('shows the five most recent revisions as squares and the older ones in a list on the right', async () => {
    const onPick = vi.fn()
    render(<RevisionSquares all={{ label: 'All revisions', note: 'x' }} revisions={revisions(7)} value="" onPick={onPick} />)

    expect(screen.getAllByRole('button').map((b) => b.textContent?.slice(0, 5))).toEqual(['All r', 'R0007', 'R0006', 'R0005', 'R0004', 'R0003'])
    await userEvent.selectOptions(screen.getByLabelText('Older revisions'), 'R0001')
    expect(onPick).toHaveBeenCalledWith('R0001')
    expect(screen.getByLabelText('Older revisions').querySelectorAll('option')).toHaveLength(3) // Pick one…, R0002, R0001
  })

  it('puts the list of the older ones at the height of the description, at its right, when there is one — and not beside the squares', async () => {
    const onPick = vi.fn()
    render(<RevisionSquares description="A revision is one visit to every site." all={{ label: 'All revisions', note: 'x' }} revisions={revisions(7)} value="" onPick={onPick} />)

    const row = screen.getByText('A revision is one visit to every site.').parentElement as HTMLElement
    expect(row).toContainElement(screen.getByLabelText('Older revisions'))                               // the same row as the description
    expect(screen.getByRole('group', { name: 'Revision' })).not.toContainElement(screen.getByLabelText('Older revisions'))   // not among the squares
    await userEvent.selectOptions(screen.getByLabelText('Older revisions'), 'R0001')
    expect(onPick).toHaveBeenCalledWith('R0001')
  })

  it('has no list when all the revisions fit, and shows an older one as picked in the list', () => {
    const { rerender } = render(<RevisionSquares all={{ label: 'All revisions', note: 'x' }} revisions={revisions(5)} value="" onPick={() => {}} />)
    expect(screen.queryByLabelText('Older revisions')).not.toBeInTheDocument()
    rerender(<RevisionSquares all={{ label: 'All revisions', note: 'x' }} revisions={revisions(7)} value="R0001" onPick={() => {}} />)
    expect(screen.getByLabelText('Older revisions')).toHaveValue('R0001')
  })

  it('puts the name of the revision and the number of its note in bold, and not the words around them, when asked', () => {
    const squares = [{ id: 'R0002', label: 'R0002', note: '3 visits without deployment', strong: '3' }]
    const { rerender } = render(<RevisionSquares variablesInBold all={{ label: 'All revisions', note: '6 visits without deployment', strong: '6' }} revisions={squares} value="" onPick={() => {}} />)
    expect(screen.getByText('R0002')).toHaveClass('font-bold')
    expect(screen.getByText('3').tagName).toBe('STRONG')
    expect(screen.getByText('3').parentElement).not.toHaveClass('font-bold')           // the words around it are plain
    expect(screen.getByText('6').tagName).toBe('STRONG')
    // as it was, without asking: the whole note in bold
    rerender(<RevisionSquares all={{ label: 'All revisions', note: '6 visits without deployment', strong: '6' }} revisions={squares} value="" onPick={() => {}} />)
    expect(screen.getByText('3 visits without deployment')).toHaveClass('font-bold')
  })
})
