import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RepairPage from './RepairPage'
import { api } from '../api'
import { EMPTY_RESEARCH_PROJECT } from '../types'
import type { RepairState } from '../types'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), repairCollections: vi.fn(), repairInspect: vi.fn(), repairDeployment: vi.fn(), getReport: vi.fn(), reportUrl: vi.fn() } }))
const mockedApi = vi.mocked(api, true)

const FILES = { 'deployment.json': true, 'images.json': true, 'preprocessing.json': true, 'seal.json': true }
const dep = (deployment_id: string, over: Record<string, unknown> = {}) => ({ deployment_id, images: 3, files: FILES, synced: false, ...over })
const state = (deployment_id: string, over: Partial<RepairState> = {}): RepairState => ({
  deployment_id, status: 'valid', files: { 'deployment.json': 'ok', 'images.json': 'ok', 'preprocessing.json': 'ok', 'seal.json': 'ok' }, images: 3, log: 'row', problems: [], ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ ...EMPTY_RESEARCH_PROJECT, name: 'Doñana', acronym: 'DONA', trapper_pk: 2 }] })
  mockedApi.repairCollections.mockResolvedValue({ results: [{ name: 'R0003', path: '/c/DONA/R0003', deployments: [dep('R0003-DONA_01'), dep('R0003-DONA_02'), dep('R0003-DONA_03', { synced: true })] }] })
  mockedApi.repairInspect.mockImplementation(async (_rp, _c, id) => (
    id === 'R0003-DONA_02' ? state(id, { status: 'broken', problems: ['deployment.json is missing', '1 image(s) changed since they were sealed'] }) : state(id, id === 'R0003-DONA_03' ? { status: 'synced' } : {})
  ))
  mockedApi.getReport.mockRejectedValue(new Error('no report in this test'))
})

async function pickCollection() {
  render(<RepairPage />)
  await userEvent.click(await screen.findByLabelText('Research project'))
  await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))
  await userEvent.click(await screen.findByLabelText('Collection'))
  await userEvent.click(await screen.findByRole('option', { name: /^R0003/ }))
}

describe('RepairPage', () => {
  it('asks for a local research project and a collection, and lists the deployment folders of the collection', async () => {
    await pickCollection()

    expect(mockedApi.repairCollections).toHaveBeenCalledWith('DONA')
    expect(await screen.findByText('R0003-DONA_01')).toBeInTheDocument()
    expect(screen.getByText('R0003-DONA_02')).toBeInTheDocument()
    expect(screen.getAllByText('Not checked')).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Repair 2 deployments' })).toBeEnabled() // the one from Trapper can't be
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_03' })).toBeDisabled()
  })

  it('checks the deployments: valid is what the seal says, and it says what is wrong with the others and selects them', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Check the deployments' }))

    await screen.findByText('⚠ Not valid')
    expect(mockedApi.repairInspect.mock.calls.map((c) => c[2])).toEqual(['R0003-DONA_01', 'R0003-DONA_02', 'R0003-DONA_03'])
    expect(screen.getByText('✔ Valid')).toBeInTheDocument()
    expect(screen.getByText('From Trapper')).toBeInTheDocument()
    const problems = screen.getByLabelText('Problems of R0003-DONA_02')
    expect(problems).toHaveTextContent('deployment.json is missing')
    expect(problems).toHaveTextContent('1 image(s) changed since they were sealed')
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_01' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'R0003-DONA_02' })).toBeChecked() // the not valid ones are what is left to do
    expect(screen.getByRole('button', { name: 'Repair 1 deployment' })).toBeEnabled()
  })

  it('selects all, the not valid, or none', async () => {
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Check the deployments' }))
    await screen.findByText('⚠ Not valid')
    const ticked = () => ['01', '02', '03'].filter((n) => (screen.getByRole('checkbox', { name: `R0003-DONA_${n}` }) as HTMLInputElement).checked)

    await userEvent.click(screen.getByRole('button', { name: 'Select all' }))
    expect(ticked()).toEqual(['01', '02']) // not the one synced from Trapper
    await userEvent.click(screen.getByRole('button', { name: 'Select none' }))
    expect(ticked()).toEqual([])
    expect(screen.getByRole('button', { name: 'Repair 0 deployments' })).toBeDisabled()
    await userEvent.click(screen.getByRole('button', { name: 'Select the not valid' }))
    expect(ticked()).toEqual(['02'])
  })

  it('repairs the chosen deployments in turn, shows each step and what it wrote, and looks at the deployment again', async () => {
    mockedApi.repairDeployment.mockImplementation(async (_rp, _c, id, onEvent) => {
      onEvent({ type: 'step', step: 'inspect', status: 'done', message: '3 image(s), 1 of 4 metadata files.' })
      onEvent({ type: 'step', step: 'dates', status: 'done', message: '2024-07-01 09:00:00 → 2024-07-01 12:00:00 (the timestamp log says so).' })
      onEvent({ type: 'done', deployment_id: id, images: 3, written: ['deployment.json', 'seal.json'], problems: 0, status: 'valid', report_id: null })
    })
    mockedApi.repairInspect.mockResolvedValueOnce(state('R0003-DONA_01')).mockResolvedValueOnce(state('R0003-DONA_02', { status: 'broken' })).mockResolvedValueOnce(state('R0003-DONA_03', { status: 'synced' }))
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Check the deployments' }))
    await screen.findByText('⚠ Not valid')
    mockedApi.repairInspect.mockResolvedValue(state('R0003-DONA_02')) // valid once repaired
    await userEvent.click(screen.getByRole('button', { name: 'Repair 1 deployment' }))

    const card = await screen.findByRole('region', { name: 'Repair of R0003-DONA_02' })
    expect(mockedApi.repairDeployment).toHaveBeenCalledWith('DONA', 'R0003', 'R0003-DONA_02', expect.any(Function))
    expect(within(card).getByText(/the timestamp log says so/)).toBeInTheDocument()
    expect(await within(card).findByText(/Valid again — wrote deployment.json, seal.json/)).toBeInTheDocument()
    expect(await screen.findByText('1 deployment(s) repaired.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByText('✔ Valid')).toHaveLength(2)) // both are valid now
  })

  it('says when a repair fails, and goes on with the others', async () => {
    mockedApi.repairDeployment.mockImplementation(async (_rp, _c, id, onEvent) => {
      if (id === 'R0003-DONA_01') throw new Error("deployment.json can't be rebuilt: latitude: Input should be a valid number.")
      onEvent({ type: 'done', deployment_id: id, images: 3, written: ['seal.json'], problems: 0, status: 'valid', report_id: null })
    })
    await pickCollection()
    await userEvent.click(await screen.findByRole('button', { name: 'Repair 2 deployments' }))

    expect(await screen.findByText(/can't be rebuilt: latitude/)).toBeInTheDocument()
    expect(await screen.findByText('1 deployment(s) repaired, 1 failed.')).toBeInTheDocument()
    expect(mockedApi.repairDeployment).toHaveBeenCalledTimes(2)
  })

  it('says why when the collections cannot be read', async () => {
    mockedApi.repairCollections.mockRejectedValue(new Error('The research project id is no folder name.'))
    render(<RepairPage />)
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'DONA — Doñana' }))

    expect(await screen.findByText('The research project id is no folder name.')).toBeInTheDocument()
  })
})
