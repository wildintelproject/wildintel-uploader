import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MenuPage from './MenuPage'

describe('MenuPage', () => {
  it('offers Manage deployments and Import collection', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const deploymentButton = screen.getByRole('button', { name: /manage deployments/i })
    const sessionButton = screen.getByRole('button', { name: /import collection/i })

    expect(deploymentButton).toBeEnabled()
    expect(sessionButton).toBeEnabled()

    await userEvent.click(deploymentButton)
    expect(onChoose).toHaveBeenCalledWith('deployment')
    await userEvent.click(sessionButton)
    expect(onChoose).toHaveBeenCalledWith('session')
  })

  it('offers to manage the visits', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    await userEvent.click(screen.getByRole('button', { name: /manage visits/i }))
    expect(onChoose).toHaveBeenCalledWith('visits')
  })

  it('offers to upload a deployment to Trapper', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    const uploadButton = screen.getByRole('button', { name: /upload deployment to trapper/i })
    expect(uploadButton).toBeEnabled()
    expect(screen.getByText(/its location and the deployment are created there if they are missing/i)).toBeInTheDocument()

    await userEvent.click(uploadButton)
    expect(onChoose).toHaveBeenCalledWith('upload')
  })

  it('offers the tasks in the order manage visits, manage deployments, import collection, upload deployment', () => {
    render(<MenuPage onChoose={vi.fn()} />)

    const titles = screen.getAllByRole('button').map((b) => b.textContent ?? '').filter((t) => /Manage visits|Manage deployments|Import collection|Upload deployment/.test(t))
    expect(titles.map((t) => t.match(/Manage visits|Manage deployments|Import deployments|Import collection|Upload deployment/)![0])).toEqual(['Manage visits', 'Manage deployments', 'Import collection', 'Upload deployment'])
    expect(screen.queryByRole('button', { name: /upload session to trapper/i })).not.toBeInTheDocument()
  })

  it('offers the utilities, with the repair and the sync inside them rather than in the menu', async () => {
    const onChoose = vi.fn()
    render(<MenuPage onChoose={onChoose} />)

    expect(screen.queryByRole('button', { name: /^🛠️/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^🔄/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^reports/i })).not.toBeInTheDocument() // the reports are in the settings now

    await userEvent.click(screen.getByRole('button', { name: /utils/i }))
    expect(onChoose).toHaveBeenCalledWith('utils')
  })
})
