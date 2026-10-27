import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VisitsPage, { detailsErrors, addName, namesOf, removeName, sessionName, sessionOf, toStored, visitErrors, cardBatteriesCode, fieldsFor } from './VisitsPage'
import { APP_SETTINGS } from '../test/fixtures'
import { api } from '../api'
import { EMPTY_DEPLOYMENT_FIELDS, EMPTY_RESEARCH_PROJECT } from '../types'
import type { ClosedVisit, StoredVisit } from '../types'

vi.mock('../api', () => ({ api: { listResearchProjects: vi.fn(), trapperGetConfig: vi.fn(), listLocalLocations: vi.fn(), saveLocalLocation: vi.fn(), listVisits: vi.fn(), saveVisit: vi.fn(), importVisitsCsv: vi.fn(), visitsCsvColumns: vi.fn(), closedVisits: vi.fn(), getSettings: vi.fn() } }))
const mockedApi = vi.mocked(api, true)

const location = (location_id: string, over: Record<string, unknown> = {}) => ({
  location_id, name: null, timezone: null, latitude: null, longitude: null, coordinate_uncertainty: null, trapper_pk: null, ...over,
})

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.listResearchProjects.mockResolvedValue({ results: [{ ...EMPTY_RESEARCH_PROJECT, name: 'Tatra', acronym: 'TATR', trapper_pk: 2 }] })
  mockedApi.trapperGetConfig.mockRejectedValue(new Error('no account in this test'))
  mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: {
      ...APP_SETTINGS.FIELDWORK, trappers: [{ name: 'Ana Pérez', affiliation: 'University of Huelva' }, { name: 'Luis', affiliation: null }],
      sd_cards: [{ label: 'A13', brand: 'SanDisk', capacity: '64 GB', in_service: null, research_project: null }, { label: 'B2', brand: null, capacity: null, in_service: null, research_project: null }],
      cameras: [{ label: 'P800HG08192031', camera_id: 'P800HG08192031', camera_model: 'Reconyx-PC800', in_service: null, research_project: null }, { label: 'X1', camera_id: 'X1', camera_model: null, in_service: null, research_project: null }],
    } })
  mockedApi.listVisits.mockResolvedValue({ results: [] })
  mockedApi.saveVisit.mockImplementation(async (_rp, v) => v)
  mockedApi.listLocalLocations.mockResolvedValue({ results: [location('TATR_0001', { name: 'Ridge', latitude: 49.2, longitude: 20.1 }), location('TATR_0002')] })
})

async function chooseByHand() {
  render(<VisitsPage onBack={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
}

async function pickWhere(site = 'TATR_0001') {
  await userEvent.click(await screen.findByLabelText('Research project'))
  await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
  await userEvent.click(await screen.findByLabelText('Location'))
  await userEvent.click(await screen.findByRole('option', { name: new RegExp(`^${site}`) }))
}

// Typing in a date-and-time input does not work in jsdom, so the value is set.
async function pickWhen(when = '2026-10-02T08:14:05') {
  fireEvent.change(await screen.findByLabelText(/date and time of the visit/i), { target: { value: when } })
  await userEvent.click(screen.getByRole('button', { name: 'Continue to the visit' }))
}

// What was done at the visit decides what the rest of the form asks.
const pickAction = (name: string) => userEvent.click(screen.getByRole('checkbox', { name }))

// A trapper is picked from the list of the settings, as a research project is.
async function pickTrapper(name: string) {
  await userEvent.click(await screen.findByLabelText('Trappers'))
  await userEvent.click(await screen.findByRole('option', { name }))
}

// The cards of the details are closed until opened.
async function openSection(name: string) {
  const header = within(screen.getByRole('region', { name })).getAllByRole('button')[0]
  if (header.getAttribute('aria-expanded') !== 'true') await userEvent.click(header)
}

// The camera of the visit is one of the settings, and what is collected at a revision is counted.
async function pickCamera() {
  await openSection('Camera')
  await userEvent.click(screen.getByLabelText('Camera id'))
  await userEvent.click(await screen.findByRole('option', { name: 'P800HG08192031 — Reconyx-PC800' }))
}
async function typePhotos(count = '1620') {
  await openSection('SD card')
  await userEvent.type(screen.getByLabelText('Photos on the card collected'), count)
}

describe('VisitsPage', () => {
  it('first asks where the visits come from, with by hand, Wildintel Epicollect and a spreadsheet file', () => {
    render(<VisitsPage onBack={vi.fn()} />)

    expect(screen.getByText('Where do the visits come from?')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /by hand/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /from wildintel epicollect/i })).toBeEnabled()
    expect(screen.getByRole('button', { name: /from a spreadsheet file/i })).toBeEnabled()
  })

  it('marks the step done with the source chosen, and lets it be changed', async () => {
    await chooseByHand()
    expect(screen.getByText('Completed')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /edit where do the visits come from/i }))
    expect(screen.queryByText('Completed')).not.toBeInTheDocument()
    expect(screen.queryByText('Where was the visit?')).not.toBeInTheDocument()
  })

  it('asks where the visit was before anything else, the rest locked until then', async () => {
    await chooseByHand()

    expect(screen.getByText('Where was the visit?')).toBeInTheDocument()
    expect(screen.getByLabelText('Research project')).toBeInTheDocument()
    expect(screen.getAllByRole('img', { name: 'Locked' }).length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Trappers')).not.toBeInTheDocument()
  })

  it('asks for the location of the research project picked, and opens the form with it as the site and its coordinates', async () => {
    await chooseByHand()
    await pickWhere()

    expect(mockedApi.listLocalLocations).toHaveBeenCalledWith('TATR')
    expect(screen.getByText(/TATR · TATR_0001, Ridge/)).toBeInTheDocument()
    expect(screen.getByText('Who went, and when?')).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Actions' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Trappers')).toBeInTheDocument()
    await pickWhen()
    await pickAction('Revision')
    await openSection('SD card'); await openSection('Camera'); await openSection('Site'); await openSection('Grouping and notes')
    for (const label of ['Status of the camera', 'SD card left in the camera', 'Photos on the card collected', 'Camera id', 'Set up by', 'Comments']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
    expect(screen.queryByRole('textbox', { name: 'Site' })).not.toBeInTheDocument() // the site is the location
    expect(screen.queryByLabelText('Session')).not.toBeInTheDocument() // the session is worked out
    expect(screen.queryByLabelText('Date')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Latitude')).not.toBeInTheDocument() // it is the location's
  })

  it('keeps the SD card in a section of its own, shut until it is opened, with what is filled in on its header, and the card and the batteries as the one code of the datasheet', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Revision')

    expect(screen.queryByLabelText('SD card left in the camera')).not.toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'SD card' })).getByText('1 of 3 filled')).toBeInTheDocument() // the card starts OK

    await openSection('SD card')
    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    await userEvent.click(await screen.findByRole('option', { name: 'A13 — SanDisk 64 GB' }))
    await userEvent.type(screen.getByLabelText('Photos on the card collected'), '1620')
    await userEvent.click(screen.getByRole('switch', { name: 'Card OK' }))
    expect(screen.getByRole('switch', { name: 'Card OK' })).toHaveAttribute('aria-checked', 'false')
    expect(within(screen.getByRole('region', { name: 'SD card' })).getByText('3 of 3 filled')).toBeInTheDocument()
  })

  it('keeps the status of the camera, as one of the three it is found in, and whether its date and time were right in the Camera section, counted with the rest of it', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()

    await pickAction('Revision')
    const camera = () => within(screen.getByRole('region', { name: 'Camera' }))
    expect(camera().getByText('2 of 10 filled')).toBeInTheDocument() // the batteries and the date and time of the camera start OK
    await openSection('Camera')
    await userEvent.selectOptions(screen.getByLabelText('Status of the camera'), 'Knocked down')
    await userEvent.click(screen.getByRole('switch', { name: 'Date and time of the camera OK' }))
    expect(screen.getByRole('switch', { name: 'Date and time of the camera OK' })).toHaveAttribute('aria-checked', 'false')
    expect(camera().getByText('3 of 10 filled')).toBeInTheDocument()
  })

  it('tags the fields that are Camtrap DP\'s, and only those', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Revision')
    await openSection('Camera'); await openSection('Site'); await openSection('SD card')

    // the camera, height, tilt, heading, delay and detection distance
    expect(within(screen.getByRole('region', { name: 'Camera' })).getAllByText('Camtrap DP')).toHaveLength(6)
    // the aim of the camera, habitat, set up by, bait and the photo dates
    expect(within(screen.getByRole('region', { name: 'Site' })).getAllByText('Camtrap DP')).toHaveLength(5)
    // the status of the camera and the card are the visit's own
    expect(screen.getByLabelText('Status of the camera').closest('div')!.textContent).not.toMatch(/Camtrap DP/)
    expect(within(screen.getByRole('region', { name: 'SD card' })).queryByText('Camtrap DP')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Camera id').closest('div')!.parentElement!.textContent).toMatch(/Camtrap DP/)
  })

  it('picks the SD card of the visit from those of the settings, with a way to add a new one there', async () => {
    const onOpenSettings = vi.fn()
    render(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await openSection('SD card')

    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['A13 — SanDisk 64 GB', 'B2'])
    await userEvent.click(screen.getByRole('option', { name: 'B2' }))
    expect(screen.getByLabelText('SD card left in the camera')).toHaveValue('B2')

    await userEvent.click(screen.getByRole('button', { name: /add a new sd card/i }))
    expect(onOpenSettings).toHaveBeenCalledWith('sdcards')
  })

  it('does not ask for the camera model and id: one of the cameras of the settings is picked, with a way to add a new one there', async () => {
    const onOpenSettings = vi.fn()
    render(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await openSection('Camera')

    expect(screen.queryByLabelText('Camera model')).not.toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Camera id'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['P800HG08192031 — Reconyx-PC800', 'X1'])
    await userEvent.click(screen.getByRole('option', { name: 'P800HG08192031 — Reconyx-PC800' }))
    expect(screen.getByLabelText('Camera id')).toHaveValue('P800HG08192031 — Reconyx-PC800')
    expect(screen.getByText('Model: Reconyx-PC800')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /add a new camera/i }))
    expect(onOpenSettings).toHaveBeenCalledWith('cameras')
  })

  it('answers what is yes or no with a switch, on when all is well, and saves what is off as the code of the datasheet', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Revision')
    await pickCamera(); await typePhotos()
    for (const name of ['Card OK', 'Batteries OK', 'Date and time of the camera OK']) {
      expect(screen.getByRole('switch', { name })).toHaveAttribute('aria-checked', 'true')
    }

    await userEvent.click(screen.getByRole('switch', { name: 'Batteries OK' }))
    await userEvent.click(screen.getByRole('switch', { name: 'Date and time of the camera OK' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

    await waitFor(() => expect(mockedApi.saveVisit).toHaveBeenCalled())
    expect(mockedApi.saveVisit.mock.calls[0][1]).toMatchObject({ card_batteries_ok: 'SinPilas', date_time_ok: 'No' })
  })

  describe('what the action asks for', () => {
    async function start() {
      await chooseByHand()
      await pickWhere()
      await pickWhen()
      await openSection('SD card'); await openSection('Camera')
    }
    const field = (label: string) => screen.getByLabelText(label)
    const tag = (label: string) => field(label).closest('div')!.parentElement!.textContent
    // a field turned off is there, disabled; the others are asked as required or optional
    const off = (labels: string[]) => labels.forEach((l) => expect(field(l)).toBeDisabled())
    const on = (labels: string[]) => labels.forEach((l) => expect(field(l)).toBeEnabled())

    it('turns everything off until the action is chosen, and says so', async () => {
      await start()

      expect(screen.getByText('Choose what was done — more than one if the visit did several things: the rest of the form depends on it.')).toBeInTheDocument()
      off(['SD card left in the camera', 'Photos on the card collected', 'Status of the camera', 'Camera id'])
      expect(screen.getByRole('switch', { name: 'Card OK' })).toBeDisabled()
      expect(screen.getByRole('switch', { name: 'Date and time of the camera OK' })).toBeDisabled()
    })

    it('for an Installation asks for the camera and the card left, and turns off the photos, the card and how the camera was found', async () => {
      await start()
      await pickAction('Installation')

      expect(screen.getByText('A camera is put up: nothing is collected, a card is left.')).toBeInTheDocument()
      on(['SD card left in the camera', 'Camera id'])
      off(['Photos on the card collected', 'Status of the camera'])
      expect(tag('Camera id')).toMatch(/required/)
      expect(tag('SD card left in the camera')).toMatch(/required/)
      expect(screen.getByRole('switch', { name: 'Batteries OK' })).toBeEnabled()
      expect(screen.getByRole('switch', { name: 'Card OK' })).toBeDisabled()
    })

    it('for a Revision asks for the camera and the photos collected, and says which card is collected: the one the last visit left', async () => {
      const left = toStored({ ...BLANK, session: 'R0001', when: '2026-10-02T09:00:00', site: 'TATR_0001', actions: ['Installation'], sd: 'A13' })
      mockedApi.listVisits.mockResolvedValue({ results: [left] })
      await start()
      await pickAction('Revision')

      on(['SD card left in the camera', 'Photos on the card collected', 'Status of the camera', 'Camera id'])
      expect(tag('Photos on the card collected')).toMatch(/required/)
      expect(tag('SD card left in the camera')).toMatch(/optional/)
      expect(tag('Status of the camera')).toMatch(/optional/)
      expect(screen.getByRole('switch', { name: 'Card OK' })).toBeEnabled()
      expect(screen.getByText('Card collected: A13 (left on 2026-10-02).')).toBeInTheDocument()
    })

    it('for a Desinstallation collects the card and leaves none', async () => {
      await start()
      await pickAction('Desinstallation')

      off(['SD card left in the camera'])
      on(['Photos on the card collected', 'Status of the camera', 'Camera id'])
      expect(screen.getByText('No card is known to have been left in the camera.')).toBeInTheDocument()
    })

    it('for a Stolen camera asks only which camera it was', async () => {
      await start()
      await pickAction('Stolen')

      expect(screen.getByText('The camera is gone: nothing is collected and nothing is left.')).toBeInTheDocument()
      on(['Camera id'])
      off(['SD card left in the camera', 'Photos on the card collected', 'Status of the camera'])
      expect(screen.getAllByRole('switch').filter((s) => !(s as HTMLButtonElement).disabled)).toEqual([])
    })

    it('for several actions asks as strongly as any of them, and keeps them all', async () => {
      await start()
      await pickAction('Revision')
      await pickAction('Installation')

      expect(screen.getByText(/A camera is put up.*The card is collected/)).toBeInTheDocument()
      expect(tag('SD card left in the camera')).toMatch(/required/) // optional at a revision, required at an installation
      expect(tag('Photos on the card collected')).toMatch(/required/)
      await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))
      expect(screen.getByRole('alert')).toHaveTextContent('Required.')
      expect(mockedApi.saveVisit).not.toHaveBeenCalled()

      await pickCamera(); await typePhotos()
      await userEvent.click(screen.getByLabelText('SD card left in the camera'))
      await userEvent.click(await screen.findByRole('option', { name: 'B2' }))
      await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

      await waitFor(() => expect(mockedApi.saveVisit).toHaveBeenCalled())
      expect(mockedApi.saveVisit.mock.calls[0][1]).toMatchObject({ actions: ['Installation', 'Revision'], num_photos: 1620, sd: 'B2' })
    })

    it('warns that the first visit to a location is usually an Installation', async () => {
      await start()

      await pickAction('Installation')
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
      await pickAction('Installation')
      await pickAction('Revision')
      expect(screen.getByRole('status')).toHaveTextContent('first visit to TATR_0001')
    })

    it('keeps only what the action asks, whatever was typed before it was changed', async () => {
      await start()
      await pickAction('Revision')
      await typePhotos()
      await userEvent.selectOptions(screen.getByLabelText('Status of the camera'), 'Altered')
      await pickCamera()
      await pickAction('Revision')
      await pickAction('Stolen')
      await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

      await waitFor(() => expect(mockedApi.saveVisit).toHaveBeenCalled())
      expect(mockedApi.saveVisit.mock.calls[0][1]).toMatchObject({
        actions: ['Stolen'], num_photos: null, status: null, sd: null, card_batteries_ok: null, date_time_ok: null,
      })
    })
  })

  it('asks for what is missing and adds nothing', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()

    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))
    expect(screen.getByText('Choose at least one.')).toBeInTheDocument() // the actions
    expect(screen.getByRole('alert')).toHaveTextContent('The visit cannot be added yet')
    expect(screen.queryByText(/visits? added/)).not.toBeInTheDocument()
  })

  it('adds a visit with the session worked out from the visits kept, and asks for the location and the time of the next keeping the project and who went', async () => {
    const earlier = (date: string) => toStored({ ...BLANK, session: 'R0001', when: `${date}T09:00:00`, site: 'TATR_0001', actions: ['Installation'] })
    mockedApi.listVisits.mockResolvedValue({ results: [earlier('2026-06-10'), earlier('2026-08-05')] })
    await chooseByHand()
    await pickWhere()

    await pickTrapper('Ana Pérez')
    await pickWhen()
    await pickAction('Revision')
    await pickCamera()
    await typePhotos()
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

    expect(await screen.findByText('1 visit added')).toBeInTheDocument()
    expect(mockedApi.saveVisit).toHaveBeenCalledWith('TATR', expect.objectContaining({
      location_id: 'TATR_0001', session: 'R0003', date: '2026-10-02', time: '08:14:05', actions: ['Revision'], trappers: 'Ana Pérez', camera_id: 'P800HG08192031', camera_model: 'Reconyx-PC800', latitude: 49.2, longitude: 20.1,
    }))
    expect(screen.queryByText('Where was the visit?')).not.toBeInTheDocument() // the form is out of the way while the next step is asked
    await userEvent.click(screen.getByRole('button', { name: 'Add another visit' }))
    expect(screen.getAllByText('TATR_0001').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('img', { name: 'Locked' }).length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Research project')).toHaveValue('TATR — Tatra')

    await pickWhere('TATR_0002')
    expect(within(screen.getByRole('list', { name: 'Who went' })).getByText('Ana Pérez')).toBeInTheDocument()
    await pickWhen('2026-10-03T09:00:00')
    await openSection('Camera')
    expect(screen.getByLabelText('Camera id')).toHaveValue('')
  })

  it('offers only the cameras and the SD cards of the research project, and those that belong to none', async () => {
    const card = (label: string, research_project: string | null) => ({ label, brand: null, capacity: null, in_service: null, research_project })
    const camera = (camera_id: string, research_project: string | null) => ({ label: camera_id, camera_id, camera_model: null, in_service: null, research_project })
    mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: {
      ...APP_SETTINGS.FIELDWORK, sd_cards: [card('T1', 'TATR'), card('D1', 'DONA'), card('F1', null)], cameras: [camera('CT', 'tatr'), camera('CD', 'DONA'), camera('CF', null)],
    } })
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await openSection('SD card')
    await openSection('Camera')

    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['T1', 'F1'])
    await userEvent.click(screen.getByRole('option', { name: 'T1' }))
    await userEvent.click(screen.getByLabelText('Camera id'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['CT', 'CF'])
  })

  it('does not offer the cameras, the SD cards and the trappers that are no longer in use', async () => {
    const card = (label: string, status: 'active' | 'lost') => ({ label, brand: null, capacity: null, in_service: null, research_project: null, status })
    const camera = (camera_id: string, status: 'active' | 'stolen') => ({ label: camera_id, camera_id, camera_model: null, in_service: null, research_project: null, status })
    mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: {
      trappers: [{ name: 'Ana Pérez', affiliation: null, status: 'active' }, { name: 'Luis', affiliation: null, status: 'inactive' }],
      sd_cards: [card('T1', 'active'), card('T2', 'lost')], cameras: [camera('CT', 'active'), camera('CS', 'stolen')],
    } })
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await openSection('SD card')
    await openSection('Camera')

    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['T1'])
    await userEvent.click(screen.getByRole('option', { name: 'T1' }))
    await userEvent.click(screen.getByLabelText('Camera id'))
    expect(within(screen.getByRole('listbox')).getAllByRole('option').map((o) => o.textContent)).toEqual(['CT'])
  })

  it('will not keep a camera put up while it is installed elsewhere, nor a card left while it is in another camera, and says so as soon as they are picked', async () => {
    const elsewhere = toStored({ ...BLANK, session: 'R0001', when: '2026-06-10T09:00:00', site: 'TATR_0002', actions: ['Installation'], sd: 'A13', details: { ...EMPTY_DEPLOYMENT_FIELDS, camera_id: 'X1' } })
    mockedApi.listVisits.mockResolvedValue({ results: [elsewhere] })
    await chooseByHand()
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await pickCamera()
    await typePhotos('') // opens the SD card section
    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    await userEvent.click(await screen.findByRole('option', { name: 'A13 — SanDisk 64 GB' }))

    expect(screen.getByText('SD card A13 is in the camera at TATR_0002 (left on 2026-06-10): it has to be collected before it is left here.')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('Camera id'))
    await userEvent.click(await screen.findByRole('option', { name: 'X1' }))
    expect(screen.getByText('Camera X1 is installed at TATR_0002 (since 2026-06-10): it has to be uninstalled there before it is installed here.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))
    expect(mockedApi.saveVisit).not.toHaveBeenCalled()

    await userEvent.click(screen.getByLabelText('Camera id'))
    await userEvent.click(await screen.findByRole('option', { name: 'P800HG08192031 — Reconyx-PC800' }))
    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    await userEvent.click(await screen.findByRole('option', { name: 'B2' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))
    await waitFor(() => expect(mockedApi.saveVisit).toHaveBeenCalled())
  })

  describe('the visit a new one closes', () => {
    const left = toStored({ ...BLANK, session: 'R0001', when: '2026-06-10T09:00:00', site: 'TATR_0001', actions: ['Installation'], sd: 'A13' })
    const closing = (over: Partial<StoredVisit> = {}): ClosedVisit => ({ visit: left, end: { ...left, session: 'R0002', date: '2026-10-02', time: '08:14:05', actions: ['Revision'], ...over } })

    async function addRevision(onImportImages = vi.fn()) {
      mockedApi.listVisits.mockResolvedValue({ results: [left] })
      render(<VisitsPage onBack={vi.fn()} onImportImages={onImportImages} />)
      await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
      await pickWhere()
      await pickWhen()
      await pickAction('Revision')
      await pickCamera(); await typePhotos()
      await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))
      await screen.findByText('1 visit added')
      return onImportImages
    }

    it('offers a link to import the images of the visit whose card it collected', async () => {
      mockedApi.closedVisits.mockResolvedValue({ results: [closing()] })
      const onImportImages = await addRevision()

      await userEvent.click(await screen.findByRole('button', { name: 'Import the images of R0001' }))

      expect(screen.getByText(/is closed: its card was collected on 2026-10-02/)).toBeInTheDocument()
      expect(screen.getByRole('status')).not.toHaveTextContent('is closed') // a card of its own, not part of the success one
      expect(onImportImages).toHaveBeenCalledWith({ researchProjectId: 'TATR', visit: left })
    })

    it('offers nothing when the visit closed none', async () => {
      mockedApi.closedVisits.mockResolvedValue({ results: [closing({ time: '07:00:00' })] }) // the closed visit is one that came before
      await addRevision()

      await waitFor(() => expect(mockedApi.closedVisits).toHaveBeenCalled())
      expect(screen.queryByRole('button', { name: /Import the images/ })).not.toBeInTheDocument()
    })
  })

  it('asks, once a visit is added, whether to add another or go back to the start', async () => {
    const onBack = vi.fn()
    mockedApi.listVisits.mockResolvedValue({ results: [] })
    render(<VisitsPage onBack={onBack} />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()
    await pickWhen()
    await pickAction('Installation')
    await pickCamera()
    await typePhotos('')
    await userEvent.click(screen.getByLabelText('SD card left in the camera'))
    await userEvent.click(await screen.findByRole('option', { name: 'B2' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

    const next = within(await screen.findByRole('group', { name: 'What next' }))
    expect(next.getByText('Do you want to add another visit?')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add visit' })).not.toBeInTheDocument()
    await userEvent.click(next.getByRole('button', { name: 'Back to the start' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('offers to add a new location by hand, and picks it as the site of the visit', async () => {
    mockedApi.saveLocalLocation.mockImplementation(async (_rp, l) => l)
    await chooseByHand()
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))

    await userEvent.click(await screen.findByRole('button', { name: /add a new location/i }))
    // the first "By hand" is the source of the visits, kept (hidden) in the step above
    await userEvent.click(screen.getAllByRole('button', { name: /by hand/i }).at(-1)!)
    await userEvent.type(screen.getByLabelText(/location id/i), 'TATR_0007')
    await userEvent.type(screen.getByLabelText(/^latitude/i), '37.1')
    await userEvent.type(screen.getByLabelText(/^longitude/i), '-3.4')
    await userEvent.click(screen.getByRole('button', { name: 'Save location' }))

    expect(mockedApi.saveLocalLocation).toHaveBeenCalledWith('TATR', expect.objectContaining({ location_id: 'TATR_0007', latitude: 37.1, longitude: -3.4 }))
    expect(await screen.findByText(/TATR · TATR_0007/)).toBeInTheDocument()
  })

  it('says which visit this is to the location: the first when none is kept', async () => {
    await chooseByHand()
    await pickWhere()

    expect(await screen.findByText(/Visit no\. 1\b/)).toBeInTheDocument()
    expect(mockedApi.listVisits).toHaveBeenCalledWith('TATR', 'TATR_0001')
  })

  it('counts the visits kept to the location, and says when the last was', async () => {
    const kept = (date: string, action: 'Installation' | 'Revision') => ({ ...toStored({ ...BLANK, session: 'R0011', when: `${date}T09:00:00`, site: 'TATR_0001', actions: [action] }) })
    mockedApi.listVisits.mockResolvedValue({ results: [kept('2026-08-05', 'Revision'), kept('2026-06-10', 'Installation')] })
    await chooseByHand()
    await pickWhere()

    expect(await screen.findByText(/Visit no\. 3 · R0003 — the last was on 2026-08-05 \(Revision\)/)).toBeInTheDocument()
  })

  it('keeps nothing and says why when the visit cannot be saved', async () => {
    mockedApi.saveVisit.mockRejectedValue(new Error('The research project is not there.'))
    await chooseByHand()
    await pickWhere()

    await pickWhen()
    await pickAction('Revision')
    await pickCamera(); await typePhotos()
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

    expect(await screen.findByText('The research project is not there.')).toBeInTheDocument()
    expect(screen.queryByText(/visits? added/)).not.toBeInTheDocument()
  })

  it('asks who went from the trappers of the settings, picked as a research project is, and puts back whoever is taken out', async () => {
    await chooseByHand()
    await pickWhere()

    await pickTrapper('Ana Pérez')
    await pickTrapper('Luis')
    const who = within(screen.getByRole('list', { name: 'Who went' }))
    expect(who.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Ana Pérez×', 'Luis×'])

    // the ones on the visit are no longer offered
    await userEvent.click(screen.getByLabelText('Trappers'))
    expect(screen.queryByRole('option', { name: 'Luis' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remove Ana Pérez' }))
    expect(who.getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Luis×'])
    await userEvent.click(screen.getByLabelText('Trappers'))
    expect(await screen.findByRole('option', { name: 'Ana Pérez' })).toBeInTheDocument()
  })

  it('says there are no trappers yet when the settings have none, and has a button to add a new one there', async () => {
    mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: APP_SETTINGS.FIELDWORK })
    const onOpenSettings = vi.fn()
    render(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()

    expect(await screen.findByText('The settings have no trappers yet.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /add a new trapper/i }))
    expect(onOpenSettings).toHaveBeenCalledWith('trappers')
  })

  it('has the button to add a new trapper under the list also when there are some', async () => {
    const onOpenSettings = vi.fn()
    render(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()

    await userEvent.click(await screen.findByRole('button', { name: /add a new trapper/i }))
    expect(onOpenSettings).toHaveBeenCalledWith('trappers')
  })

  it('reads the trappers again when the settings are closed', async () => {
    mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: APP_SETTINGS.FIELDWORK })
    const view = render(<VisitsPage onBack={vi.fn()} onOpenSettings={vi.fn()} settingsOpen />)
    await userEvent.click(screen.getByRole('button', { name: /by hand/i }))
    await pickWhere()
    expect(await screen.findByText('The settings have no trappers yet.')).toBeInTheDocument()

    mockedApi.getSettings.mockResolvedValue({ ...APP_SETTINGS, FIELDWORK: { ...APP_SETTINGS.FIELDWORK, trappers: [{ name: 'Marta', affiliation: null }] } })
    view.rerender(<VisitsPage onBack={vi.fn()} onOpenSettings={vi.fn()} settingsOpen={false} />)

    await userEvent.click(await screen.findByLabelText('Trappers'))
    expect(await screen.findByRole('option', { name: 'Marta' })).toBeInTheDocument()
  })

  it('goes back to the menu', async () => {
    const onBack = vi.fn()
    render(<VisitsPage onBack={onBack} />)

    await userEvent.click(screen.getByRole('button', { name: /^back/i }))
    expect(onBack).toHaveBeenCalled()
  })
})

const BLANK = { trappers: '', session: '', when: '', site: '', actions: [] as string[], status: '', card: '' as const, batteries: '' as const, numPhotos: '', sd: '', dateTimeOK: '', longitude: '', latitude: '', details: EMPTY_DEPLOYMENT_FIELDS }

describe('cardBatteriesCode', () => {
  it('says how the card and the batteries were in the one code of the datasheet', () => {
    expect(cardBatteriesCode('', '')).toBeNull()
    expect(cardBatteriesCode('OK', '')).toBe('OK')
    expect(cardBatteriesCode('', 'OK')).toBe('OK')
    expect(cardBatteriesCode('OK', 'OK')).toBe('OK')
    expect(cardBatteriesCode('Full', 'OK')).toBe('CarFull')
    expect(cardBatteriesCode('Full', '')).toBe('CarFull')
    expect(cardBatteriesCode('OK', 'Missing')).toBe('SinPilas')
    expect(cardBatteriesCode('Full', 'Missing')).toBe('CarFullSinPilas')
  })
})

describe('sessionOf', () => {
  it('numbers the visits to a location from R0001', () => {
    expect(sessionOf(0)).toBe('R0001')
    expect(sessionOf(2)).toBe('R0003')
    expect(sessionOf(12)).toBe('R0013')
  })
})

describe('sessionName', () => {
  it('writes the session as the datasheet does', () => {
    expect(sessionName('13')).toBe('R0013')
    expect(sessionName('r13')).toBe('R0013')
    expect(sessionName(' R0013 ')).toBe('R0013')
    expect(sessionName('trip 3')).toBeNull()
  })
})

describe('the visit filled in from the last one', () => {
  const last = () => toStored({
    ...BLANK, trappers: 'Ana Pérez', session: 'R0001', when: '2026-06-10T09:00:00', site: 'TATR_0001', actions: ['Revision'], status: 'OK', card: 'Full', batteries: 'Missing',
    numPhotos: '1620', sd: 'A13', dateTimeOK: 'No', details: { ...EMPTY_DEPLOYMENT_FIELDS, camera_id: 'P800HG08192031', camera_model: 'Reconyx-PC800', setup_by: 'Ana', camera_height: 1.2, tags: ['ridge'], comments: 'Batteries changed' },
  })

  async function start() {
    mockedApi.listVisits.mockResolvedValue({ results: [last()] })
    await chooseByHand()
    await pickWhere()
    await pickWhen()
  }

  it('offers it when this is not the first visit to the location, and not when it is the first', async () => {
    await start()

    expect(screen.getByText(/This is not the first visit to/)).toHaveTextContent('the last was R0001, on 2026-06-10 (Revision)')
    expect(screen.getByRole('button', { name: 'Fill in from R0001' })).toBeInTheDocument()
  })

  it('does not offer it for the first visit', async () => {
    await chooseByHand()
    await pickWhere()
    await pickWhen()

    expect(screen.queryByRole('button', { name: /Fill in from/ })).not.toBeInTheDocument()
  })

  it('fills in the Camera, Site and Grouping sections, not the notes nor the card, and keeps only what the actions then ask', async () => {
    await start()
    await userEvent.click(screen.getByRole('button', { name: 'Fill in from R0001' }))

    expect(screen.getByRole('status')).toHaveTextContent('The Camera, Site and Grouping sections are filled in from the visit R0001, except the notes')
    expect(screen.queryByRole('list', { name: 'Who went' })).not.toBeInTheDocument() // who went is asked above
    expect(screen.getByRole('group', { name: 'Actions' }).querySelectorAll('input:checked')).toHaveLength(0) // what was done is of this visit

    await pickAction('Revision')
    await openSection('SD card'); await openSection('Camera'); await openSection('Site'); await openSection('Grouping and notes')
    expect(screen.getByLabelText('SD card left in the camera')).toHaveValue('') // the card collected is the last one's, so it is not left back
    expect(screen.getByLabelText('Photos on the card collected')).toHaveValue('')
    expect(screen.getByLabelText('Camera id')).toHaveValue('P800HG08192031 — Reconyx-PC800')
    expect(screen.getByLabelText('Status of the camera')).toHaveValue('OK')
    expect(screen.getByLabelText('Set up by')).toHaveValue('Ana')
    expect(screen.getByLabelText('Comments')).toHaveValue('') // the notes of the last visit are not this one's
    expect(screen.getByRole('switch', { name: 'Batteries OK' })).toHaveAttribute('aria-checked', 'false')
    expect(screen.getByRole('switch', { name: 'Card OK' })).toHaveAttribute('aria-checked', 'true')

    // a Desinstallation leaves no card: what was typed for the Revision is left out
    await userEvent.type(screen.getByLabelText('Photos on the card collected'), '10')
    await pickAction('Revision')
    await pickAction('Desinstallation')
    await userEvent.click(screen.getByRole('button', { name: 'Add visit' }))

    await waitFor(() => expect(mockedApi.saveVisit).toHaveBeenCalled())
    expect(mockedApi.saveVisit.mock.calls[0][1]).toMatchObject({
      actions: ['Desinstallation'], sd: null, num_photos: 10, camera_id: 'P800HG08192031', camera_height: 1.2, card_batteries_ok: 'SinPilas', date_time_ok: 'No', comments: null,
    })
  })

  it('starts empty again when asked', async () => {
    await start()
    await userEvent.click(screen.getByRole('button', { name: 'Fill in from R0001' }))
    await userEvent.click(screen.getByRole('button', { name: 'Start empty' }))

    expect(screen.getByRole('button', { name: 'Fill in from R0001' })).toBeInTheDocument()
    await pickAction('Revision')
    await openSection('SD card')
    expect(screen.getByLabelText('SD card left in the camera')).toHaveValue('')
  })
})

describe('VisitsPage from a CSV file', () => {
  const visit = (over: Record<string, unknown> = {}) => ({ ...toStored({ ...BLANK, session: 'R0001', when: '2026-10-02T08:14:05', site: 'TATR_0001', actions: ['Installation'], sd: 'A13' }), ...over })
  const file = new File(['Lugar,Dia,Hora,Tarea,Fotos\nTATR_0001,02/10/2026,08:14,Revision,1620\n'], 'visits.csv', { type: 'text/csv' })
  const COLUMNS = {
    columns: ['Lugar', 'Dia', 'Hora', 'Tarea', 'Fotos'], sample: [['TATR_0001', '02/10/2026', '08:14', 'Revision', '1620']],
    mapping: { location_id: 'Lugar', date: 'Dia', time: 'Hora', actions: 'Tarea' },
    fields: [
      { field: 'location_id', label: 'Site (a location of the research project)', required: true }, { field: 'actions', label: 'Actions', required: true },
      { field: 'date', label: 'Date', required: false }, { field: 'time', label: 'Time', required: false }, { field: 'num_photos', label: 'Photos on the card collected', required: false },
    ],
  }
  const MAPPING = { location_id: 'Lugar', date: 'Dia', time: 'Hora', actions: 'Tarea', num_photos: 'Fotos' }

  async function start(option = /from a spreadsheet file/i) {
    mockedApi.visitsCsvColumns.mockResolvedValue(COLUMNS)
    render(<VisitsPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: option }))
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
    await userEvent.upload(screen.getByLabelText('CSV file'), file)
  }

  it('shows the columns of the file with the ones that match already picked, and an example of each', async () => {
    await start()

    expect(await screen.findByLabelText('Site (a location of the research project)')).toHaveValue('Lugar')
    expect(screen.getByLabelText('Date')).toHaveValue('Dia')
    expect(screen.getByLabelText('Photos on the card collected')).toHaveValue('')
    expect(screen.getByLabelText('Example of Date')).toHaveTextContent('02/10/2026')
    expect(mockedApi.importVisitsCsv).not.toHaveBeenCalled()
  })

  it('reads the visits with the columns as they are mapped, says what it found, and keeps them with the same mapping', async () => {
    mockedApi.importVisitsCsv.mockResolvedValueOnce({ visits: [visit(), visit({ session: 'R0002', date: '2026-11-05', actions: ['Revision', 'Installation'] })], problems: [{ row: 4, message: "The site 'X' is not a location of the research project." }], skipped: 1, ignored: 0, saved: null })
    mockedApi.importVisitsCsv.mockResolvedValueOnce({ visits: [visit()], problems: [], skipped: 0, ignored: 0, saved: 2 })
    await start()
    await userEvent.selectOptions(await screen.findByLabelText('Photos on the card collected'), 'Fotos')
    await userEvent.click(screen.getByRole('button', { name: 'Read the visits' }))

    await waitFor(() => expect(mockedApi.importVisitsCsv).toHaveBeenCalledWith('TATR', expect.stringContaining('TATR_0001,02/10/2026'), false, 'mapped', MAPPING))
    expect(await screen.findByText(/to add/)).toHaveTextContent('2 visits to add · 1 already kept · 1 row with a problem')
    expect(screen.getByRole('list', { name: 'Rows with a problem' })).toHaveTextContent("Row 4: The site 'X' is not a location")
    expect(screen.getByText('Revision + Installation')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Add 2 visits' }))
    expect(mockedApi.importVisitsCsv).toHaveBeenLastCalledWith('TATR', expect.any(String), true, 'mapped', MAPPING)
    expect(await screen.findByRole('status')).toHaveTextContent('2 visits added to the visits file of TATR.')
  })

  it('does not read the visits until the site, the actions and when are mapped', async () => {
    await start()

    await userEvent.selectOptions(await screen.findByLabelText('Time'), '')
    expect(screen.getByRole('button', { name: 'Read the visits' })).toBeDisabled()
    await userEvent.selectOptions(screen.getByLabelText('Time'), 'Hora')
    expect(screen.getByRole('button', { name: 'Read the visits' })).toBeEnabled()
  })

  it('says why a file cannot be read, and offers nothing to map', async () => {
    mockedApi.visitsCsvColumns.mockRejectedValue(new Error('The file is empty.'))
    render(<VisitsPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /from a spreadsheet file/i }))
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
    await userEvent.upload(screen.getByLabelText('CSV file'), file)

    expect(await screen.findByRole('alert')).toHaveTextContent('The file is empty.')
    expect(screen.queryByRole('button', { name: 'Read the visits' })).not.toBeInTheDocument()
  })

  it('says the locations can be created when the sites of the file are not there, and checks the file again when the settings close', async () => {
    mockedApi.importVisitsCsv.mockResolvedValueOnce({ visits: [], problems: [{ row: 2, message: "The site 'TATR_0001' is not a location of the research project." }], skipped: 0, ignored: 0, saved: null })
    mockedApi.importVisitsCsv.mockResolvedValueOnce({ visits: [visit()], problems: [], skipped: 0, ignored: 0, saved: null })
    const onOpenSettings = vi.fn()
    const { rerender } = render(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} />)
    await userEvent.click(screen.getByRole('button', { name: /from wildintel epicollect/i }))
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
    await userEvent.upload(screen.getByLabelText('CSV file'), file)

    expect(await screen.findByText(/You can create the locations/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Go to the locations of TATR' }))
    expect(onOpenSettings).toHaveBeenCalledWith('locations', 'TATR')

    rerender(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} settingsOpen />)
    rerender(<VisitsPage onBack={vi.fn()} onOpenSettings={onOpenSettings} settingsOpen={false} />)
    await waitFor(() => expect(mockedApi.importVisitsCsv).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByText(/You can create the locations/)).not.toBeInTheDocument())
  })

  it('reads a Wildintel Epicollect download without asking for any column', async () => {
    mockedApi.importVisitsCsv.mockResolvedValue({ visits: [visit()], problems: [], skipped: 0, ignored: 3, saved: null })
    render(<VisitsPage onBack={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /from wildintel epicollect/i }))
    await userEvent.click(await screen.findByLabelText('Research project'))
    await userEvent.click(await screen.findByRole('option', { name: 'TATR — Tatra' }))
    await userEvent.upload(screen.getByLabelText('CSV file'), file)

    await waitFor(() => expect(mockedApi.importVisitsCsv).toHaveBeenCalledWith('TATR', expect.any(String), false, 'epicollect'))
    expect(await screen.findByText(/to add/)).toHaveTextContent('3 of old versions of the form, ignored')
    expect(mockedApi.visitsCsvColumns).not.toHaveBeenCalled()
    expect(screen.queryByText('Match the columns')).not.toBeInTheDocument()
  })
})

describe('visitErrors', () => {
  const ok = { ...BLANK, session: 'R0013', when: '2026-10-02T08:14:05', site: 'TATR_0001', actions: ['Revision'], numPhotos: '1620', details: { ...EMPTY_DEPLOYMENT_FIELDS, camera_id: '12' } }

  it('has nothing to say of a complete visit', () => {
    expect(visitErrors(ok)).toEqual({})
  })

  it('wants a whole number of photos', () => {
    expect(visitErrors({ ...ok, numPhotos: '1.5' })).toEqual({ numPhotos: 'A whole number.' })
  })

  it('wants the camera, and the photos collected at a revision, but not the photos of an installation', () => {
    expect(visitErrors({ ...ok, numPhotos: '', details: EMPTY_DEPLOYMENT_FIELDS })).toEqual({ numPhotos: 'Required.', camera: 'Required.' })
    expect(visitErrors({ ...ok, actions: ['Installation'], numPhotos: '', sd: 'A13' })).toEqual({})
  })

  it('wants the card left at an installation', () => {
    expect(visitErrors({ ...ok, actions: ['Installation'] })).toEqual({ sd: 'Required.' })
  })

  it('asks as strongly as any of the actions asks', () => {
    expect(fieldsFor(['Revision', 'Installation'])).toMatchObject({ sdLeft: 'required', photos: 'required', status: 'optional' })
    expect(fieldsFor(['Stolen'])).toMatchObject({ camera: 'required', photos: 'off', sdLeft: 'off' })
    expect(fieldsFor([]).camera).toBe('off')
  })
})

describe('toStored', () => {
  it('keeps the numbers as numbers, what is left blank as none, and the details as the deployment names them', () => {
    const stored = toStored({
      ...BLANK, trappers: ' Ana ', session: '13', when: '2026-10-02T08:14:00', site: ' TATR_0001 ', actions: ['Revision'], numPhotos: '1620', latitude: '37.1', longitude: '-3.4',
      details: { ...EMPTY_DEPLOYMENT_FIELDS, setup_by: 'Ana', camera_id: '12', camera_height: 1.2, tags: ['forest edge'] },
    })

    expect(stored).toMatchObject({
      location_id: 'TATR_0001', session: 'R0013', date: '2026-10-02', time: '08:14:00', num_photos: 1620, latitude: 37.1, longitude: -3.4,
      trappers: 'Ana', setup_by: 'Ana', camera_id: '12', camera_height: 1.2, tags: ['forest edge'], status: null, sd: null,
    })
    expect(stored).not.toHaveProperty('deployment_id')
    expect(stored).not.toHaveProperty('start_date')
  })
})

describe('detailsErrors', () => {
  it('has nothing to say when the details are empty', () => {
    expect(detailsErrors(EMPTY_DEPLOYMENT_FIELDS)).toEqual({})
  })

  it('says what is out of range in the camera details', () => {
    const errors = detailsErrors({ ...EMPTY_DEPLOYMENT_FIELDS, camera_tilt: 120, camera_heading: 400 })

    expect(errors.camera_tilt).toBeTruthy()
    expect(errors.camera_heading).toBeTruthy()
  })
})

describe('namesOf, addName and removeName', () => {
  it('read and write the names separated by commas', () => {
    expect(namesOf(' Ana ,, Luis ')).toEqual(['Ana', 'Luis'])
    expect(addName('Ana', 'Luis')).toBe('Ana, Luis')
    expect(addName('Ana', 'ana')).toBe('Ana')
    expect(addName('', 'Ana')).toBe('Ana')
    expect(removeName('Ana, Luis', 'ana')).toBe('Luis')
  })
})
