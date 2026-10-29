import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import VisitsHomePage from './VisitsHomePage'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), trapperGetConfig: vi.fn(), listVisits: vi.fn(), fieldDeployments: vi.fn(), getSettings: vi.fn(), listLocalLocations: vi.fn(), closedVisits: vi.fn() } }))
const mockedApi = vi.mocked(api)

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.trapperGetConfig.mockRejectedValue(new Error('no account in this test'))
  mockedApi.listResearchProjects.mockResolvedValue({ results: [] } as never)
  mockedApi.getSettings.mockResolvedValue({ FIELDWORK: { trappers: [], sd_cards: [], cameras: [] } } as never)
  mockedApi.listLocalLocations.mockResolvedValue({ results: [] })
  mockedApi.closedVisits.mockResolvedValue({ results: [] })
  mockedApi.listVisits.mockResolvedValue({ results: [] })
  mockedApi.fieldDeployments.mockResolvedValue({ results: [] })
})

describe('VisitsHomePage', () => {
  it('offers to register visits or to show the visit book, and comes back from each', async () => {
    const onBack = vi.fn()
    render(<VisitsHomePage onBack={onBack} />)
    expect(screen.getByRole('heading', { name: 'Manage visits' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /register visits/i }))
    expect(await screen.findByText('Where do the visits come from?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /back/i }))

    await userEvent.click(screen.getByRole('button', { name: /show the visit book/i }))
    expect(await screen.findByRole('heading', { name: 'Visit book' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByRole('heading', { name: 'Manage visits' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
