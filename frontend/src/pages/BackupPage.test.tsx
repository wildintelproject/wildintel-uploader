import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { BackupManifest, BackupProjectInfo, BackupRead } from '../types'

vi.mock('../api', () => ({
  api: {
    listResearchProjects: vi.fn(), getSettings: vi.fn(), backupProjectInfo: vi.fn(), browseFolder: vi.fn(), backupCreate: vi.fn(), backupPickFile: vi.fn(), backupRead: vi.fn(), backupRestore: vi.fn(), openFolder: vi.fn(),
  },
}))
import { api } from '../api'
import BackupPage from './BackupPage'

const mocked = vi.mocked(api)
const INFO: BackupProjectInfo = {
  research_project_id: 'DONA', locations: 3, cameras: 2, sd_cards: 4, visits: 12,
  collections: [
    { name: 'R0002', deployments: [{ id: 'R0002-DONA_01', files: 5, bytes: 3000, images: 3, image_bytes: 2500 }] },
    { name: 'R0001', deployments: [{ id: 'R0001-DONA_01', files: 5, bytes: 2000, images: 3, image_bytes: 1500 }, { id: 'R0001-DONA_02', files: 2, bytes: 100, images: 0, image_bytes: 0 }] },
  ],
}
const MANIFEST: BackupManifest = {
  format: 'wildintel-uploader-backup', version: 1, app_version: '1.2.3', created_at: '2026-10-29T10:30:00+00:00',
  scope: { settings: true, research_project: 'DONA', project_files: true, visits: true, images: true, deployments: [{ id: 'R0001-DONA_01', collection: 'R0001', files: 4, images: true }, { id: 'R0001-DONA_02', collection: 'R0001', files: 2, images: false }] },
  counts: { locations: 3, cameras: 2, sd_cards: 4, visits: 12 }, secrets_included: false,
}
const READ: BackupRead = { manifest: MANIFEST, here: { project: true, deployments: { 'R0001-DONA_01': true, 'R0001-DONA_02': false }, visits: { in_backup: 12, already: 10 } }, has_images: { 'R0001-DONA_01': true, 'R0001-DONA_02': false } }

beforeEach(() => {
  vi.clearAllMocks()
  mocked.listResearchProjects.mockResolvedValue({ results: [{ name: 'Doñana', acronym: 'DONA' }, { name: 'Tatra', acronym: 'TATR' }] } as never)
  mocked.getSettings.mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
  mocked.backupProjectInfo.mockResolvedValue(INFO)
})

describe('BackupPage', () => {
  it('has the header of the other pages and first asks whether to make a backup or to restore one', async () => {
    const onBack = vi.fn()
    render(<BackupPage onBack={onBack} />)

    expect(screen.getByRole('navigation', { name: 'You are here' })).toHaveTextContent('Utilities›Backup and restore')
    expect(screen.getByRole('radio', { name: 'Make a backup' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Restore a backup' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Utilities' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('asks for the research project and what of it to back up — the visits, the deployments, and whether the images go — and makes the backup', async () => {
    mocked.browseFolder.mockResolvedValue({ path: '/backups' })
    mocked.backupCreate.mockImplementation(async (_request, onEvent) => {
      onEvent({ type: 'file', index: 1, total: 2, name: 'manifest.json' })
      onEvent({ type: 'done', path: '/backups/wildintel-backup_DONA_20261030.zip', bytes: 4096, files: 2, manifest: MANIFEST })
    })
    render(<BackupPage onBack={vi.fn()} />)

    await userEvent.click(screen.getByRole('radio', { name: 'Make a backup' }))
    expect(await screen.findByText('3 locations · 2 cameras · 4 SD cards')).toBeInTheDocument()   // the research project of the settings comes chosen
    expect(screen.getByText('12 visits')).toBeInTheDocument()

    const revision = screen.getByRole('group', { name: 'Deployments of R0001' })
    await userEvent.click(within(revision).getByRole('checkbox', { name: /Revision R0001/ }))      // the whole revision
    expect(within(revision).getByRole('checkbox', { name: /R0001-DONA_02/ })).toBeChecked()
    const images = screen.getByRole('switch', { name: 'Include the images of the deployments' })
    expect(images).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByText(/its images \(.+\) stay out/)).toBeInTheDocument()
    await userEvent.click(images)
    await userEvent.click(screen.getByRole('button', { name: /Continue/ }))

    await userEvent.click(screen.getByRole('button', { name: 'Browse…' }))
    expect(await screen.findByLabelText('Folder of the backup')).toHaveTextContent('/backups')
    await userEvent.click(screen.getByRole('button', { name: 'Make the backup' }))

    await waitFor(() => expect(mocked.backupCreate).toHaveBeenCalled())
    expect(mocked.backupCreate.mock.calls[0][0]).toEqual({ dest_dir: '/backups', settings: true, research_project_id: 'DONA', project_files: true, visits: true, deployments: ['R0001-DONA_01', 'R0001-DONA_02'], images: true })
    const done = await screen.findByRole('status')
    expect(done).toHaveTextContent('Backup made — 4 KB')
    expect(done).toHaveTextContent('/backups/wildintel-backup_DONA_20261030.zip')
    expect(done).toHaveTextContent('2 deployments of DONA, with their images')
  })

  it('can back up the settings alone, with no research project, and has nothing to continue with when nothing is chosen', async () => {
    mocked.getSettings.mockResolvedValue({ GENERAL: { default_research_project: null } } as never)
    render(<BackupPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Make a backup' }))

    expect(screen.getByRole('button', { name: /Continue/ })).toBeEnabled()    // the settings are chosen to start with
    await userEvent.click(screen.getByRole('checkbox', { name: /The global settings/ }))
    expect(screen.getByRole('button', { name: /Continue/ })).toBeDisabled()
    expect(mocked.backupProjectInfo).not.toHaveBeenCalled()
  })

  it('reads a backup, says what it holds and what is already here, and restores what is picked — without replacing unless it is asked to', async () => {
    mocked.backupPickFile.mockResolvedValue({ path: '/backups/b.zip' })
    mocked.backupRead.mockResolvedValue(READ)
    mocked.backupRestore.mockImplementation(async (_request, onEvent) => {
      onEvent({ type: 'done', manifest: MANIFEST, summary: { settings: true, project_files: { locations: { added: 1, replaced: 0, kept: 2 } }, visits: { added: 2, replaced: 0, kept: 10 }, deployments: { restored: ['R0001-DONA_02'], skipped: ['R0001-DONA_01'] }, files: 2 } })
    })
    render(<BackupPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Restore a backup' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose the backup…' }))

    expect(await screen.findByText(/Made on 29 Oct 2026, 10:30, by version 1\.2\.3/)).toBeInTheDocument()
    expect(screen.getByText('The global settings (without passwords)')).toBeInTheDocument()
    expect(screen.getByText('10 of 12 already here')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /R0001-DONA_01/ }).closest('label')).toHaveTextContent('already here')
    expect(screen.getByText(/Off: what is already here is left as it is/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))

    await waitFor(() => expect(mocked.backupRestore).toHaveBeenCalled())
    expect(mocked.backupRestore.mock.calls[0][0]).toEqual({ path: '/backups/b.zip', settings: true, project_files: true, visits: true, deployments: ['R0001-DONA_01', 'R0001-DONA_02'], images: true, replace: false })
    const done = await screen.findByRole('status')
    expect(done).toHaveTextContent('Locations: 1 added, 0 replaced, 2 kept')
    expect(done).toHaveTextContent('Visits: 2 added, 0 replaced, 10 kept')
    expect(done).toHaveTextContent('Deployments: 1 restored, 1 left as they were (R0001-DONA_01)')
  })

  it('replaces what is there only when the switch is on', async () => {
    mocked.backupPickFile.mockResolvedValue({ path: '/backups/b.zip' })
    mocked.backupRead.mockResolvedValue(READ)
    mocked.backupRestore.mockResolvedValue(undefined)
    render(<BackupPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Restore a backup' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose the backup…' }))
    await userEvent.click(await screen.findByRole('switch', { name: 'Replace what is already here' }))
    expect(screen.getByText(/What is retired stays retired/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Restore' }))

    await waitFor(() => expect(mocked.backupRestore).toHaveBeenCalled())
    expect(mocked.backupRestore.mock.calls[0][0].replace).toBe(true)
  })

  it('says why a file is not a backup', async () => {
    mocked.backupPickFile.mockResolvedValue({ path: '/x.zip' })
    mocked.backupRead.mockRejectedValue(new Error('That .zip is not a backup of this app: it has no manifest.'))
    render(<BackupPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('radio', { name: 'Restore a backup' }))
    await userEvent.click(screen.getByRole('button', { name: 'Choose the backup…' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('has no manifest')
    expect(screen.queryByRole('button', { name: 'Restore' })).not.toBeInTheDocument()
  })
})
