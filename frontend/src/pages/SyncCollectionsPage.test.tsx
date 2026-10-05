import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SyncCollectionsPage from './SyncCollectionsPage'
import { api } from '../api'

vi.mock('../api', () => ({ api: { trapperResearchProjects: vi.fn(), trapperClassificationProjects: vi.fn(), syncCollections: vi.fn() } }))
const mockedApi = vi.mocked(api, true)

const none = { research_project: [], locations: [], collections: [], deployments: [], timestamp_log: [], images: [] }

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.trapperResearchProjects.mockResolvedValue({ results: [{ pk: 2, name: 'Doñana', acronym: 'DONA' }] })
  mockedApi.trapperClassificationProjects.mockResolvedValue({ results: [{ pk: 10, name: 'Doñana 2024', is_active: true }] })
})

describe('SyncCollectionsPage', () => {
  it('asks for the research project and the classification project, then syncs and says what was created', async () => {
    mockedApi.syncCollections.mockResolvedValue({
      research_project_id: 'DONA', folder: '/c/DONA', collections: ['R0003'], unassigned: ['R0009-DONA_01'],
      created: { ...none, collections: ['R0003'], deployments: ['R0003-DONA_01'], images: ['R0003-DONA_01'] }, kept: { ...none, locations: ['DONA_01'] },
    })
    render(<SyncCollectionsPage />)

    const sync = screen.getByRole('button', { name: 'Sync' })
    expect(sync).toBeDisabled()
    await userEvent.selectOptions(await screen.findByLabelText('Research project'), 'DONA — Doñana')
    await userEvent.selectOptions(await screen.findByRole('combobox', { name: 'Classification project' }), 'Doñana 2024')
    await userEvent.click(sync)

    expect(mockedApi.syncCollections).toHaveBeenCalledWith({}, { pk: 2, name: 'Doñana', acronym: 'DONA' }, 10)
    const result = await screen.findByLabelText('Sync result')
    expect(result).toHaveTextContent('Deployments: 1 created, 0 already there')
    expect(result).toHaveTextContent('Locations: 0 created, 1 already there')
    expect(result).toHaveTextContent('Images files (images.json): 1 created, 0 already there')
    expect(result).toHaveTextContent('Not in any of its collections, so not created: R0009-DONA_01.')
  })

  it('says why when Trapper cannot be read', async () => {
    mockedApi.trapperResearchProjects.mockRejectedValue(new Error('Incorrect Trapper username or password.'))
    render(<SyncCollectionsPage />)

    await waitFor(() => expect(screen.getByText('Incorrect Trapper username or password.')).toBeInTheDocument())
  })
})
