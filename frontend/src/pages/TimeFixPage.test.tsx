import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TimeFixPage, { offsetText, secondsBetween } from './TimeFixPage'
import { api } from '../api'
import { EMPTY_RESEARCH_PROJECT } from '../types'
import type { ClosedVisit, Timeline } from '../types'

vi.mock('../api', () => ({
  api: { listResearchProjects: vi.fn(), closedVisits: vi.fn(), browseFolder: vi.fn(), timefixTimeline: vi.fn(), timefixShift: vi.fn(), timefixRemove: vi.fn(), getSettings: vi.fn() },
}))
const mockedApi = vi.mocked(api, true)

const FOLDER = '/home/me/Pictures/card'
const visit = (over: object) => ({ location_id: 'DONA_0011', session: 'R0001', date: '2026-06-01', time: '09:00:00', actions: ['Installation'], ...over }) as unknown as ClosedVisit['visit']
const CLOSED: ClosedVisit = { visit: visit({}), end: visit({ session: 'R0002', date: '2026-09-30', time: '15:37:00', actions: ['Revision'] }) }
const TARGET = { folder: FOLDER, research_project_id: 'DONA', location_id: 'DONA_0011', date: '2026-06-01', time: '09:00:00' }
const OFFSET = 2 * 86400 + 3600 + 1
const BROKEN: Timeline = {
  folder: '/home/me/Pictures/card',
  period: { start: '2026-06-01T09:00:00', end: '2026-09-30T15:37:00' }, tolerance_hours: 1,
  images: [
    { name: 'IMG_0001.JPG', time: '2026-06-02T10:00:00' }, { name: 'IMG_0002.JPG', time: '2020-01-01T00:00:00' }, { name: 'IMG_0003.JPG', time: null },
  ],
  segments: [
    { first_index: 0, last_index: 0, first: 'IMG_0001.JPG', last: 'IMG_0001.JPG', first_time: '2026-06-02T10:00:00', last_time: '2026-06-02T10:00:00', count: 1, inside: 1, state: 'ok', suggestion: null },
    { first_index: 1, last_index: 1, first: 'IMG_0002.JPG', last: 'IMG_0002.JPG', first_time: '2020-01-01T00:00:00', last_time: '2020-01-01T00:00:00', count: 1, inside: 0, state: 'outside', suggestion: { offset_seconds: OFFSET, why: 'so that it goes on' } },
  ],
  undated: ['IMG_0003.JPG'], outside: 1, problems: ['1 image(s) have no date.'], ok: false, corrections: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.getSettings.mockResolvedValue({ GENERAL: { default_research_project: 'DONA' } } as never)
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ ...EMPTY_RESEARCH_PROJECT, name: 'Doñana', acronym: 'DONA', trapper_pk: 2 }] })
  mockedApi.closedVisits.mockResolvedValue({ results: [CLOSED] })
  mockedApi.browseFolder.mockResolvedValue({ path: FOLDER })
  mockedApi.timefixTimeline.mockResolvedValue(BROKEN)
  mockedApi.timefixShift.mockResolvedValue({ ...BROKEN, ok: true, problems: [], corrections: [{ at: '2026-10-20T18:00:00Z', by: 'me', action: 'shift', first: 'IMG_0002.JPG', last: 'IMG_0002.JPG', count: 1, offset_seconds: OFFSET }] })
  mockedApi.timefixRemove.mockResolvedValue({ ...BROKEN })
})

async function openFolder() {
  render(<TimeFixPage />)
  await userEvent.click(await screen.findByLabelText('Revision'))
  await userEvent.click(await screen.findByRole('option', { name: 'R0001' }))
  await userEvent.click(await screen.findByLabelText('Visit that left the camera'))
  await userEvent.click(await screen.findByRole('option', { name: /DONA_0011/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Browse…' }))
  await waitFor(() => expect(screen.getByLabelText('Folder')).toHaveValue(FOLDER))
  await userEvent.click(screen.getByRole('button', { name: 'Check the dates' }))
  await screen.findByRole('heading', { name: 'Segments' })
}

describe('TimeFixPage', () => {
  it('shows the segments and shifts one by its suggested offset', async () => {
    await openFolder()
    expect(screen.getAllByText('Outside its period')).toHaveLength(2)      // in the list of segments, and in the step that fixes it
    await userEvent.click(screen.getByRole('button', { name: /^Move them into the period/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Move 1 image(s)' }))

    expect(mockedApi.timefixShift).toHaveBeenCalledWith(TARGET, 'IMG_0002.JPG', 'IMG_0002.JPG', OFFSET, expect.stringContaining('IMG_0002.JPG'))
    expect(await screen.findByText(/shifted \+2 d 1 h 1 s/)).toBeInTheDocument()
  })

  it('works the offset out from an image whose real time is known', async () => {
    await openFolder()
    await userEvent.click(screen.getByRole('radio', { name: 'From an image whose real time I know' }))
    await userEvent.selectOptions(screen.getByLabelText('Image'), 'IMG_0002.JPG')
    await userEvent.type(screen.getByLabelText(/Was really taken at/), '2020-01-01T01:00:00')

    expect(screen.getByText('+1 h')).toBeInTheDocument()
  })

  it('removes the images with no date after asking', async () => {
    await openFolder()
    await userEvent.click(screen.getAllByRole('button', { name: 'Remove these images' })[1])
    await userEvent.click(screen.getByRole('button', { name: 'Remove 1 image(s)' }))

    expect(mockedApi.timefixRemove).toHaveBeenCalledWith(TARGET, ['IMG_0003.JPG'], '')
  })
})

describe('offsets', () => {
  it('says an offset in days, hours, minutes and seconds', () => {
    expect(offsetText(OFFSET)).toBe('+2 d 1 h 1 s')
    expect(offsetText(-90)).toBe('−1 min 30 s')
  })
  it('counts the seconds between two times of the same clock', () => {
    expect(secondsBetween('2020-01-01T00:00:00', '2020-01-01T01:00')).toBe(3600)
  })
})

describe('without a visit', () => {
  it('reads the folder with no period to check the dates against', async () => {
    render(<TimeFixPage />)
    await userEvent.type(await screen.findByLabelText('Folder'), FOLDER)
    await userEvent.click(screen.getByRole('button', { name: 'Check the dates' }))

    await screen.findByRole('heading', { name: 'Segments' })
    expect(mockedApi.timefixTimeline).toHaveBeenCalledWith({ folder: FOLDER })
  })
})

describe('leaving', () => {
  it('has a Back that leaves the task', async () => {
    const onBack = vi.fn()
    render(<TimeFixPage onBack={onBack} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Back' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('keeps the header short, with a Help button that opens what each option does', async () => {
    render(<TimeFixPage />)
    expect(screen.queryByText(/work on the copy, never on the card/)).not.toBeInTheDocument()      // the header is short: that is in the help
    await userEvent.click(screen.getByRole('button', { name: 'Help' }))
    const help = screen.getByRole('dialog', { name: 'Dates and times: help' })
    expect(help).toHaveTextContent('never on the card')
    expect(help).toHaveTextContent('Segments')
    expect(help).toHaveTextContent('time_corrections.json')
    await userEvent.click(screen.getByRole('button', { name: 'Got it, close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('has the folder and the visit as the first step: once checked it says what was chosen, and Edit brings the form back', async () => {
    await openFolder()
    expect(screen.getByText('1. Choose the folder and the visit')).toBeInTheDocument()
    expect(screen.getByLabelText('Folder').closest('.hidden')).not.toBeNull()      // the form is folded away, and the step says what was chosen
    expect(screen.getByText(FOLDER)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Edit Choose the folder and the visit' }))
    expect(screen.getByLabelText('Folder').closest('.hidden')).toBeNull()
    expect(screen.getByLabelText('Folder')).toHaveValue(FOLDER)
    expect(screen.queryByRole('heading', { name: 'Segments' })).not.toBeInTheDocument()
  })

  it('asks for the revision first, and then for the visits to a site in that revision only', async () => {
    mockedApi.closedVisits.mockResolvedValue({ results: [
      CLOSED, { visit: visit({ location_id: 'DONA_0012' }), end: CLOSED.end },
      { visit: visit({ session: 'R0002', date: '2026-10-01', location_id: 'DONA_0013' }), end: CLOSED.end },
    ] })
    render(<TimeFixPage />)
    expect(await screen.findByLabelText('Visit that left the camera')).toBeDisabled()          // nothing to pick from until the revision is
    await userEvent.click(await screen.findByLabelText('Revision'))
    expect(await screen.findAllByRole('option')).toHaveLength(2)                               // R0002 and R0001
    await userEvent.click(screen.getByRole('option', { name: 'R0001' }))
    await userEvent.click(await screen.findByLabelText('Visit that left the camera'))
    const sites = screen.getAllByRole('option').map((o) => o.textContent ?? '')
    expect(sites).toHaveLength(2)
    expect(sites.join(' ')).toMatch(/DONA_0011/)
    expect(sites.join(' ')).toMatch(/DONA_0012/)
    expect(sites.join(' ')).not.toMatch(/DONA_0013/)
  })

  it('has the five steps from the start, the last four locked', async () => {
    render(<TimeFixPage />)
    for (const title of ['Choose the folder and the visit', 'Check the dates', 'Fix the segments', 'Fix the dates', 'Fixes made']) expect(await screen.findByRole('heading', { name: new RegExp(`^${title}`) })).toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: 'Locked' })).toHaveLength(4)
    expect(screen.queryByRole('heading', { name: 'Segments' })).not.toBeInTheDocument()
  })

  it('opens the steps that follow once the dates are checked', async () => {
    await openFolder()
    expect(screen.queryByRole('img', { name: 'Locked' })).not.toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Shift dates and times' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Fixes made' })).toBeInTheDocument()
  })

  it('asks, of each segment that is not in its period, whether to move its images into it or to remove them — and moves nothing until it is confirmed', async () => {
    await openFolder()
    expect(screen.getAllByText(/What do you want to do with/)).toHaveLength(1)          // the one in its period is not asked
    expect(screen.getAllByRole('button', { name: 'Remove these images' })).toHaveLength(2)          // that segment, and the images with no date
    await userEvent.click(screen.getByRole('button', { name: /^Move them into the period/ }))
    const ask = screen.getByRole('alertdialog', { name: 'Move the images' })
    expect(ask).toHaveTextContent('IMG_0002.JPG')
    expect(ask).toHaveTextContent('+2 d 1 h 1 s')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(mockedApi.timefixShift).not.toHaveBeenCalled()
  })
})
