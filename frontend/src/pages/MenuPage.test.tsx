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

  it('offers to sync the local collections with Trapper, and says the session upload is coming soon', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const syncButton = screen.getByRole('button', { name: /sync local collections/i })
    expect(syncButton).toBeEnabled()
    await userEvent.click(syncButton)
    expect(onChoose).toHaveBeenCalledWith('sync')

    const sessionUpload = screen.getByRole('button', { name: /upload session to trapper/i })
    expect(sessionUpload).toBeDisabled()
    expect(sessionUpload).toHaveTextContent(/coming soon/i)
  })

  it('offers to repair the local deployments', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const repairButton = screen.getByRole('button', { name: /repair local deployments/i })
    expect(repairButton).toBeEnabled()
    expect(screen.queryByRole('button', { name: /^reports/i })).not.toBeInTheDocument() // the reports are in the settings now

    await userEvent.click(repairButton)
    expect(onChoose).toHaveBeenCalledWith('repair')
  })
})
