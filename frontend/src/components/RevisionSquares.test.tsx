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

  it('has no list when all the revisions fit, and shows an older one as picked in the list', () => {
    const { rerender } = render(<RevisionSquares all={{ label: 'All revisions', note: 'x' }} revisions={revisions(5)} value="" onPick={() => {}} />)
    expect(screen.queryByLabelText('Older revisions')).not.toBeInTheDocument()
    rerender(<RevisionSquares all={{ label: 'All revisions', note: 'x' }} revisions={revisions(7)} value="R0001" onPick={() => {}} />)
    expect(screen.getByLabelText('Older revisions')).toHaveValue('R0001')
  })
})
