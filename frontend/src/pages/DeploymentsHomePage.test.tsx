import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import DeploymentsHomePage from './DeploymentsHomePage'

describe('DeploymentsHomePage', () => {
  it('offers to import a deployment or to show the status of the deployments', async () => {
    const onChoose = vi.fn(), onBack = vi.fn()
    render(<DeploymentsHomePage onChoose={onChoose} onBack={onBack} />)

    expect(screen.getByRole('heading', { name: 'Manage deployments' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /import deployment/i }))
    expect(onChoose).toHaveBeenLastCalledWith('import')
    await userEvent.click(screen.getByRole('button', { name: /show deployments status/i }))
    expect(onChoose).toHaveBeenLastCalledWith('status')
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
