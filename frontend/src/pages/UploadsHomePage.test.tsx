import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import UploadsHomePage from './UploadsHomePage'

describe('UploadsHomePage', () => {
  it('offers to upload a deployment or to show the status of the uploads', async () => {
    const onChoose = vi.fn(), onBack = vi.fn()
    render(<UploadsHomePage onChoose={onChoose} onBack={onBack} />)

    expect(screen.getByRole('heading', { name: 'Manage uploads to Trapper' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /upload deployment to trapper/i }))
    expect(onChoose).toHaveBeenLastCalledWith('upload')
    await userEvent.click(screen.getByRole('button', { name: /show uploads status/i }))
    expect(onChoose).toHaveBeenLastCalledWith('status')
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
