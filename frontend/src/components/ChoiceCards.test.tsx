import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ChoiceCards from './ChoiceCards'

const choices = [
  { value: 'a' as const, label: 'Yes, I see it', description: 'The camera is there', icon: <path d="M12 5v14" /> },
  { value: 'b' as const, label: 'No, it was stolen', icon: <path d="M5 12h14" />, tone: 'red' as const },
]

describe('ChoiceCards', () => {
  it('is a group of radios named by what they say, one of which is the answer', async () => {
    const onChange = vi.fn()
    render(<ChoiceCards label="Do you see the camera?" value="a" choices={choices} onChange={onChange} />)

    expect(screen.getByRole('radiogroup', { name: 'Do you see the camera?' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Yes, I see it' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'No, it was stolen' })).not.toBeChecked()
    await userEvent.click(screen.getByRole('radio', { name: 'No, it was stolen' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('says a few words more under a card, without them being its name', () => {
    render(<ChoiceCards label="Q" value={null} choices={choices} onChange={vi.fn()} />)

    expect(screen.getByText('The camera is there')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Yes, I see it' })).not.toBeChecked()
  })
})
