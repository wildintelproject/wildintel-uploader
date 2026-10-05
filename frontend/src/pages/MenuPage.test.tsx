import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MenuPage from './MenuPage'

describe('MenuPage', () => {
  it('offers Import deployment and Import session', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const deploymentButton = screen.getByRole('button', { name: /import deployment/i })
    const sessionButton = screen.getByRole('button', { name: /import session/i })

    expect(deploymentButton).toBeEnabled()
    expect(sessionButton).toBeEnabled()
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument()

    await userEvent.click(deploymentButton)
    expect(onChoose).toHaveBeenCalledWith('deployment')
    await userEvent.click(sessionButton)
    expect(onChoose).toHaveBeenCalledWith('session')
  })

  it('offers to upload a deployment to Trapper', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const uploadButton = screen.getByRole('button', { name: /upload deployment to trapper/i })
    expect(uploadButton).toBeEnabled()
    expect(screen.getByText(/creating its location and the deployment there if they are missing/i)).toBeInTheDocument()

    await userEvent.click(uploadButton)
    expect(onChoose).toHaveBeenCalledWith('upload')
  })
})
