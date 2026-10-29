import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import BackButton from '../components/BackButton'
import Combobox from '../components/Combobox'
import LocationPicker from '../components/LocationPicker'
import type { ReactNode } from 'react'
import TaskCard from '../components/TaskCard'
import ResearchProjectPicker from '../components/ResearchProjectPicker'
import Notice from '../components/Notice'
import WizardStep from '../components/WizardStep'
import { CamtrapDpTag, DateTimeField, FormCard, MoreDetailsForm, SectionCard, SwitchRow, btnOutline, btnPrimary, hintClass, inputClass, labelClass } from './ImportDeploymentPage'
import { shownErrors, validateDeployment } from '../deploymentValidation'
import { availabilityErrors, cameraAtSite } from '../visitAvailability'
import { EMPTY_DEPLOYMENT_FIELDS } from '../types'
import type { Camera, DeploymentFields, NewSite, LocalLocation, LocalResearchProject, SdCard, StoredVisit, ClosedVisit, ClosedVisitTarget, VisitsCsvColumns, VisitsCsvFormat, VisitsCsvResult } from '../types'

export type VisitSource = 'manual' | 'epicollect' | 'csv'

const SOURCE_OPTIONS: { value: VisitSource; icon: ReactNode; title: string; description: string }[] = [
  { value: 'manual', icon: <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />, title: 'By hand', description: 'Enter each visit yourself: the site, when, who went and what was done.' },
  { value: 'epicollect', icon: <><rect x="7" y="2" width="10" height="20" rx="2" /><path d="M12 18h.01" /></>, title: 'From Wildintel Epicollect', description: 'Read the visits of a field trip from the Epicollect download.' },
  { value: 'csv', icon: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></>, title: 'From a spreadsheet file', description: 'Any spreadsheet: say which column gives each field of a visit.' },
]

/** The icon of the SD card section, drawn as those of the sections of the details are. */
const SD_ICON = <><path d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" /><path d="M8 6v3M11 6v3M14 7v2" /></>

/** What was done at the visit — the values the field records read. */
const ACTIONS = ['Installation', 'Revision', 'Desinstallation', 'Stolen']
/** How a field is asked at a visit: it must be filled, it may be, or it does not apply (and is turned off). */
export type Ask = 'required' | 'optional' | 'off'

/** What is asked of a visit depends on what was done at it: an Installation puts up a new camera with a card and collects nothing, a
 * Revision looks at a camera and collects its photos, a Desinstallation takes the camera away with its card, and a Stolen camera is gone —
 * nothing is collected, nothing is left. A visit may do several things, and then each field is asked as strongly as any of them asks it. */
export interface ActionFields {
  /** Which camera it is. */
  camera: Ask
  /** The SD card left in the camera. */
  sdLeft: Ask
  /** The photos on the card collected, and how the card was. */
  photos: Ask
  card: Ask
  batteries: Ask
  /** Whether the clock of the camera was right. */
  dateTime: Ask
  /** How the camera was found. */
  status: Ask
}

const OFF: ActionFields = { camera: 'off', sdLeft: 'off', photos: 'off', card: 'off', batteries: 'off', dateTime: 'off', status: 'off' }

function fieldsOf(action: string): ActionFields {
  switch (action) {
    case 'Installation': return { camera: 'required', sdLeft: 'required', photos: 'off', card: 'off', batteries: 'optional', dateTime: 'optional', status: 'off' }
    case 'Revision': return { camera: 'required', sdLeft: 'optional', photos: 'required', card: 'optional', batteries: 'optional', dateTime: 'optional', status: 'optional' }
    case 'Desinstallation': return { camera: 'required', sdLeft: 'off', photos: 'required', card: 'optional', batteries: 'optional', dateTime: 'optional', status: 'optional' }
    case 'Stolen': return { ...OFF, camera: 'required' }
    default: return OFF
  }
}

const STRENGTH: Record<Ask, number> = { off: 0, optional: 1, required: 2 }

export function fieldsFor(actions: string[]): ActionFields {
  const all = { ...OFF }
  for (const action of actions) {
    const f = fieldsOf(action)
    for (const key of Object.keys(all) as (keyof ActionFields)[]) if (STRENGTH[f[key]] > STRENGTH[all[key]]) all[key] = f[key]
  }
  return all
}

/** The tag beside a field's label: what is asked of it. */
function AskTag({ ask }: { ask: Ask }) {
  const text = ask === 'required' ? 'required' : ask === 'optional' ? 'optional' : 'not for this visit'
  const colour = ask === 'required' ? 'text-red-600 dark:text-red-400' : 'text-zinc-500 dark:text-zinc-400'
  return <span className={`ml-2 text-xs font-normal ${colour}`}>{text}</span>
}

/** What each action is, in a few words. */
const ACTION_HINTS: Record<string, string> = {
  Installation: 'A camera is put up: nothing is collected, a card is left.',
  Revision: 'The card is collected and another is left; the camera stays.',
  Desinstallation: 'The camera is taken away, with its card.',
  Stolen: 'The camera is gone: nothing is collected and nothing is left.',
}

/** The states a camera is found in. */
const CAMERA_STATUSES = ['OK', 'Knocked down', 'Altered']

export type CardState = '' | 'OK' | 'Full'
export type BatteriesState = '' | 'OK' | 'Missing'

/** How the card and the batteries were, in the one code the datasheet has for both: OK, CarFull, SinPilas or CarFullSinPilas — nothing when neither is said. */
export function cardBatteriesCode(card: CardState, batteries: BatteriesState): StoredVisit['card_batteries_ok'] {
  if (card === 'Full' && batteries === 'Missing') return 'CarFullSinPilas'
  if (card === 'Full') return 'CarFull'
  if (batteries === 'Missing') return 'SinPilas'
  return card || batteries ? 'OK' : null
}

/** A visit as the fieldwork datasheet keeps it (DateTime is worked out from Date and Time). What of it Camtrap DP has — who set the
 * camera up, its id, the notes and the optional details — is `details`, the form of More details in Import deployment; here is the rest. */
export interface Visit {
  /** Who went on the visit. */
  trappers: string
  session: string
  /** When the visit was, as an ISO local timestamp: 2026-10-02T08:14:05. */
  when: string
  site: string
  /** What was done at the visit: one or more of ACTIONS. */
  actions: string[]
  status: string
  card: CardState
  batteries: BatteriesState
  numPhotos: string
  sd: string
  dateTimeOK: string
  longitude: string
  latitude: string
  details: DeploymentFields
}

const EMPTY_VISIT: Visit = {
  // What is found most is that all is well: the switches start on, and what is wrong is turned off.
  trappers: '', session: '', when: '', site: '', actions: [], status: '', card: 'OK', batteries: 'OK',
  numPhotos: '', sd: '', dateTimeOK: 'Yes', longitude: '', latitude: '', details: EMPTY_DEPLOYMENT_FIELDS,
}

/** The fields of the Camera, the Site and the Grouping sections of the form, taken from a visit kept — not the notes. The day and the time, what was
 * done, who went and the card and its photos are of the visit being entered. */
export function visitFrom(previous: StoredVisit, now: Visit): Visit {
  const card = previous.card_batteries_ok
  const details = { ...EMPTY_DEPLOYMENT_FIELDS }
  for (const key of Object.keys(details) as (keyof DeploymentFields)[]) {
    const value = (previous as unknown as Record<string, unknown>)[key]
    if (value !== undefined && value !== null && !['deployment_id', 'location_id', 'location_name', 'coordinate_uncertainty', 'start_date', 'end_date', 'latitude', 'longitude', 'comments'].includes(key)) {
      (details as Record<string, unknown>)[key] = value
    }
  }
  return {
    ...now,
    status: previous.status ?? '', batteries: card === 'SinPilas' || card === 'CarFullSinPilas' ? 'Missing' : 'OK', dateTimeOK: previous.date_time_ok ?? 'Yes', details,
  }
}

/** What the form holds of what the actions do not ask — it is not kept, so it is put back to how it starts. */
export function withoutWhatIsNotAsked(v: Visit): Visit {
  const asked = fieldsFor(v.actions)
  if (v.actions.length === 0) return v
  return {
    ...v,
    sd: asked.sdLeft === 'off' ? '' : v.sd, numPhotos: asked.photos === 'off' ? '' : v.numPhotos, status: asked.status === 'off' ? '' : v.status,
    card: asked.card === 'off' ? 'OK' : v.card, batteries: asked.batteries === 'off' ? 'OK' : v.batteries, dateTimeOK: asked.dateTime === 'off' ? 'Yes' : v.dateTimeOK,
    details: asked.camera === 'off' ? { ...v.details, camera_id: null, camera_model: null } : v.details,
  }
}

/** The session of the next visit to a location that has had `kept` — calculated, not asked: the first visit is R0001, the second R0002… */
export function sessionOf(kept: number): string {
  return `R${String(kept + 1).padStart(4, '0')}`
}

/** The session as the datasheet writes it: R0013 for 13, R13 or r0013. */
export function sessionName(text: string): string | null {
  const m = /^\s*r?\s*0*(\d+)\s*$/i.exec(text)
  return m ? `R${m[1].padStart(4, '0')}` : null
}

type ErrorKey = Exclude<keyof Visit, 'details'> | 'camera'

/** What is wrong with a visit, by field — nothing when it can be added. */
export function visitErrors(v: Visit): Partial<Record<ErrorKey, string>> {
  const errors: Partial<Record<ErrorKey, string>> = {}
  if (!v.when) errors.when = 'Required.'
  if (!v.site.trim()) errors.site = 'Required.'
  if (v.actions.length === 0) errors.actions = 'Choose at least one.'
  const asked = fieldsFor(v.actions)
  if (asked.photos !== 'off') {
    if (!v.numPhotos.trim()) { if (asked.photos === 'required') errors.numPhotos = 'Required.' }
    else if (!/^\d+$/.test(v.numPhotos.trim())) errors.numPhotos = 'A whole number.'
  }
  if (asked.sdLeft === 'required' && !v.sd.trim()) errors.sd = 'Required.'
  if (asked.camera === 'required' && !v.details.camera_id) errors.camera = 'Required.'
  if (asked.status === 'required' && !v.status.trim()) errors.status = 'Required.'
  return errors
}

/** What is wrong with the optional details — the ranges and height-or-depth, as Import deployment says them. */
export function detailsErrors(details: DeploymentFields) {
  // The rest of a deployment's fields are not the visit's: given something valid so that only the details' own are left.
  const whole = { ...details, deployment_id: 'visit', latitude: 0, longitude: 0, start_date: '2000-01-01T00:00:00Z', end_date: '2000-01-02T00:00:00Z' }
  return shownErrors(validateDeployment(whole, 'UTC'))
}

/** A visit as the visits file keeps it: the numbers as numbers, what is left blank as none. */
export function toStored(v: Visit): StoredVisit {
  const text = (t: string) => t.trim() || null
  const number = (t: string) => (t.trim() ? Number(t) : null)
  const { deployment_id, location_id, location_name, coordinate_uncertainty, start_date, end_date, latitude, longitude, ...details } = v.details
  void deployment_id; void location_id; void location_name; void coordinate_uncertainty; void start_date; void end_date; void latitude; void longitude
  const asked = fieldsFor(v.actions)
  return {
    ...details,
    location_id: v.site.trim(), session: sessionName(v.session)!, date: v.when.slice(0, 10), time: v.when.slice(11, 19), actions: v.actions as StoredVisit['actions'],
    trappers: text(v.trappers), status: asked.status !== 'off' ? text(v.status) : null,
    // only what the action asks is kept, whatever was typed before it was changed
    card_batteries_ok: cardBatteriesCode(asked.card !== 'off' ? v.card : '', asked.batteries !== 'off' ? v.batteries : ''),
    num_photos: asked.photos !== 'off' ? number(v.numPhotos) : null, sd: asked.sdLeft !== 'off' ? text(v.sd) : null, date_time_ok: asked.dateTime !== 'off' ? text(v.dateTimeOK) : null,
    latitude: number(v.latitude), longitude: number(v.longitude),
  }
}

/** The names of a list of trappers typed as text — separated by commas. */
export function namesOf(text: string): string[] {
  return text.split(',').map((n) => n.trim()).filter(Boolean)
}

/** The text with a name added (once, whatever its case). */
export function addName(text: string, name: string): string {
  const names = namesOf(text)
  return (names.some((n) => n.toLowerCase() === name.toLowerCase()) ? names : [...names, name]).join(', ')
}

/** The text without a name. */
export function removeName(text: string, name: string): string {
  return namesOf(text).filter((n) => n.toLowerCase() !== name.toLowerCase()).join(', ')
}

/** The actions of a visit, as text. */
function actionsText(actions: string[]): string {
  return actions.join(' + ')
}

/** The latest of the visits kept, by the day and time of the visit. */
function latest(visits: StoredVisit[]): StoredVisit | undefined {
  return [...visits].sort((a, b) => `${a.date} ${a.time}`.localeCompare(`${b.date} ${b.time}`)).at(-1)
}

function Field({ id, label, ask, error, children }: { id: string; label: string; ask?: Ask; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-baseline"><label htmlFor={id} className={labelClass}>{label}</label>{ask && <AskTag ask={ask} />}</div>
      {children}
      {error && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>}
    </div>
  )
}

interface Props {
  onBack: () => void
  /** Opens the settings, on the section given — the page is left as it is under them. */
  onOpenSettings?: (section: 'trappers' | 'sdcards' | 'cameras' | 'locations', researchProjectId?: string) => void
  /** Whether the settings are open: the trappers are read again when they are closed, as they may have been changed. */
  settingsOpen?: boolean
  /** Goes to Import deployment for a visit that was just closed: its research project and the visit whose card was collected. */
  onImportImages?: (target: ClosedVisitTarget) => void
}

/** Register the visits to the camera traps, in steps — the first asks where they come from. */
/** What a visit keeps of its camera: its serial number, or its label when it has none. */
const cameraKey = (c: Camera) => c.camera_id || c.label

export default function VisitsPage({ onBack, onOpenSettings, settingsOpen = false, onImportImages }: Props) {
  const [source, setSource] = useState<VisitSource | null>(null)
  const [visit, setVisit] = useState<Visit>(EMPTY_VISIT)
  const [tried, setTried] = useState(false)
  const [visits, setVisits] = useState<Visit[]>([])
  // Where the visit was: a research project of the collections folder and one of its locations (the site of the visit).
  const [project, setProject] = useState<LocalResearchProject | undefined>(undefined)
  const [location, setLocation] = useState<LocalLocation | undefined>(undefined)
  const [editingWhere, setEditingWhere] = useState(false)
  // When the visit was is confirmed with Continue, not as soon as the picker holds a value (it does while the digits are still being typed).
  const [whenConfirmed, setWhenConfirmed] = useState(false)
  // The visits already kept to the location: the one being registered is the next.
  const [kept, setKept] = useState<StoredVisit[] | null>(null)
  // Every visit kept to the research project: where its cameras and its SD cards are is worked out from them.
  const [allVisits, setAllVisits] = useState<StoredVisit[] | null>(null)
  // The visits the ones just added closed — their card was collected — each with a way to import its images.
  const [justClosed, setJustClosed] = useState<ClosedVisit[]>([])
  // The session of the visit the form was filled in from, when it was.
  const [filledFrom, setFilledFrom] = useState<string | null>(null)
  // A visit was just added: what is shown is that, and the choice of adding another or going back — the form comes back when another is wanted.
  const [justAdded, setJustAdded] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  // The trappers kept in the settings, offered as who went.
  const [trappers, setTrappers] = useState<string[]>([])
  // The SD cards kept in the settings, to pick the one of the visit from.
  const [allSdCards, setSdCards] = useState<SdCard[]>([])
  // And the cameras, to pick the one of the visit from.
  const [allCameras, setCameras] = useState<Camera[]>([])
  // Only those of the research project — or of none, which any may use.
  const ofProject = (rp: string | null) => !rp || !project || rp.toLowerCase() === project.acronym.toLowerCase()
  // ...and only those still in use: a retired, lost, stolen or broken one is not offered, unless the visit already has it.
  const inUse = (status: string | undefined) => !status || status === 'active'
  const sdCards = allSdCards.filter((c) => ofProject(c.research_project) && (inUse(c.status) || c.label === visit.sd))
  const cameras = allCameras.filter((c) => ofProject(c.research_project) && (inUse(c.status) || cameraKey(c) === visit.details.camera_id))
  // From a CSV file: its text, what reading it gave, and what was kept of it.
  const [csvName, setCsvName] = useState<string | null>(null)
  const [csvText, setCsvText] = useState('')
  const [csvResult, setCsvResult] = useState<VisitsCsvResult | null>(null)
  const [csvError, setCsvError] = useState<string | null>(null)
  const [csvSaved, setCsvSaved] = useState<number | null>(null)
  // The history of visits (the fieldwork datasheet, an .xlsx, as base64) that completes the visits kept before the file's are applied.
  const [historyName, setHistoryName] = useState<string | null>(null)
  const [historyXlsx, setHistoryXlsx] = useState('')
  // From a CSV file: its columns, and the one that gives each field of a visit.
  const [csvColumns, setCsvColumns] = useState<VisitsCsvColumns | null>(null)
  const [csvMapping, setCsvMapping] = useState<Record<string, string>>({})
  const csvFormat: VisitsCsvFormat = source === 'epicollect' ? 'epicollect' : 'mapped'
  const chosen = SOURCE_OPTIONS.find((o) => o.value === source)
  // A camera put up while it is somewhere else, or a card left while it is in another camera, cannot be kept — said as soon as it is chosen.
  const conflicts = allVisits ? availabilityErrors(allVisits, visit) : {}
  // A Revision, a Desinstallation or a stolen camera is of the camera that is at the site: it comes chosen, and no other is offered unless the visit also installs one.
  const siteCamera = allVisits && visit.site.trim() ? cameraAtSite(allVisits, visit.site.trim(), visit.when || '9999-12-31T23:59:59') : null
  const ofTheSiteCamera = Boolean(siteCamera) && !visit.actions.includes('Installation') && visit.actions.some((x) => ['Revision', 'Desinstallation', 'Stolen'].includes(x))
  useEffect(() => {
    if (!ofTheSiteCamera || !siteCamera || visit.details.camera_id) return
    const known = allCameras.find((c) => cameraKey(c).toLowerCase() === siteCamera.camera.toLowerCase() || c.label.toLowerCase() === siteCamera.camera.toLowerCase())
    setVisit((v) => ({ ...v, details: { ...v.details, camera_id: known ? cameraKey(known) : siteCamera.camera, camera_model: known?.camera_model ?? v.details.camera_model } }))
  }, [ofTheSiteCamera, siteCamera?.camera, visit.details.camera_id]) // eslint-disable-line react-hooks/exhaustive-deps
  const errors = { ...visitErrors(visit), ...conflicts }
  const moreErrors = detailsErrors(visit.details)
  const shown = (field: ErrorKey) => (tried ? errors[field] : undefined)
  // What the visit needs and does not have yet is in red from the start, not only once adding it was tried.
  const red = 'border-red-500 dark:border-red-500'
  const err = (field: ErrorKey) => (shown(field) ? red : '')

  useEffect(() => {
    let cancelled = false
    api.getSettings()
      .then((settings) => {
        if (cancelled) return
        setTrappers((settings.FIELDWORK?.trappers ?? []).filter((t) => !t.status || t.status === 'active').map((t) => t.name))
        setSdCards(settings.FIELDWORK?.sd_cards ?? [])
        setCameras(settings.FIELDWORK?.cameras ?? [])
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [settingsOpen])

  useEffect(() => {
    setAllVisits(null)
    if (!project) return
    let cancelled = false
    Promise.resolve().then(() => api.listVisits(project.acronym))
      .then(({ results }) => { if (!cancelled) setAllVisits(results) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [project])

  useEffect(() => {
    if (!project || !location) { setKept(null); return }
    let cancelled = false
    api.listVisits(project.acronym, location.location_id)
      .then(({ results }) => { if (!cancelled) setKept(results) })
      .catch(() => { if (!cancelled) setKept(null) })
    return () => { cancelled = true }
  }, [project, location])

  function selectProject(picked: LocalResearchProject | undefined) {
    setProject(picked); setLocation(undefined)
    setVisit((v) => ({ ...v, site: '', latitude: '', longitude: '' }))
    setEditingWhere(true)
  }

  /** The location is the site of the visit; its coordinates are where the camera is, unless the visit says otherwise. */
  function selectLocation(picked: LocalLocation | undefined) {
    setLocation(picked); setFilledFrom(null)
    setVisit((v) => ({
      ...v, site: picked?.location_id ?? '',
      latitude: picked?.latitude != null ? String(picked.latitude) : '',
      longitude: picked?.longitude != null ? String(picked.longitude) : '',
    }))
    setEditingWhere(!picked)
  }

  // Another way to read the visits starts again from the file.
  useEffect(() => { forgetCsv(); setCsvName(null); setHistoryName(null); setHistoryXlsx('') }, [source]) // eslint-disable-line react-hooks/exhaustive-deps

  // What goes after the mapping of a call to read the file: the history, when there is one.
  const withHistory = historyXlsx ? ([historyXlsx] as const) : ([] as const)
  const csvReading = useRef(0)
  function forgetCsv() {
    csvReading.current++ // what an older file is still being answered is left out
    setCsvResult(null); setCsvError(null); setCsvSaved(null); setCsvColumns(null); setCsvMapping({})
  }

  async function readCsv(file: File | undefined) {
    forgetCsv()
    const reading = ++csvReading.current
    if (!file || !project) { setCsvName(null); return }
    setCsvName(file.name)
    try {
      const text = await file.text()
      if (reading !== csvReading.current) return
      setCsvText(text)
      if (source === 'csv') {
        const found = await api.visitsCsvColumns(text)
        if (reading === csvReading.current) { setCsvColumns(found); setCsvMapping(found.mapping) }
      } else {
        const result = historyXlsx ? await api.importVisitsCsv(project.acronym, text, false, csvFormat, undefined, historyXlsx) : await api.importVisitsCsv(project.acronym, text, false, csvFormat)
        if (reading === csvReading.current) setCsvResult(result)
      }
    } catch (e) {
      if (reading === csvReading.current) setCsvError(e instanceof Error ? e.message : 'Could not read the file.')
    }
  }

  /** The history of visits: kept as base64, and the file read again with it when one is already chosen — the history goes before it. */
  async function readHistory(file: File | undefined) {
    if (!file) { setHistoryName(null); setHistoryXlsx(''); return }
    const bytes = new Uint8Array(await file.arrayBuffer())
    let binary = ''
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
    const encoded = btoa(binary)
    setHistoryName(file.name); setHistoryXlsx(encoded)
    if (!project || !csvText) return
    setCsvError(null)
    try {
      setCsvResult(await api.importVisitsCsv(project.acronym, csvText, false, source === 'csv' ? 'mapped' : csvFormat, source === 'csv' ? csvMapping : undefined, encoded))
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : 'Could not read the history.')
    }
  }

  /** Reads the file again with the same options — after the settings were open, where the missing locations may have been added. */
  async function recheckCsv() {
    if (!project || !csvText) return
    try {
      setCsvResult(await api.importVisitsCsv(project.acronym, csvText, false, source === 'csv' ? 'mapped' : csvFormat, source === 'csv' ? csvMapping : undefined, ...withHistory))
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : 'Could not read the file.')
    }
  }
  const missingLocations = (csvResult?.new_sites.length ?? 0) > 0
  useEffect(() => { if (!settingsOpen && missingLocations) void recheckCsv() }, [settingsOpen]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Keeps a new site of the file as a location of the research project, with the coordinates of its first visit, and reads the file again. */
  async function addNewSite(site: NewSite) {
    if (!project || site.latitude == null || site.longitude == null) return
    setCsvError(null)
    try {
      await api.saveLocalLocation(project.acronym, { location_id: site.site, name: site.site, timezone: 'UTC', ignore_dst: false, latitude: site.latitude, longitude: site.longitude, coordinate_uncertainty: null, trapper_pk: null })
      await recheckCsv()
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : `Could not add ${site.site} as a location.`)
    }
  }

  /** The sites of the file that have the coordinates of their first visit and that do not look like a misprint of a location — a close id or a location next to them —
   * are new sites to add, as the file has enough of them to be locations. */
  const addable = (csvResult?.new_sites ?? []).filter((s) => s.latitude != null && s.longitude != null && s.similar.length === 0 && !(s.nearest && s.nearest.distance_m < 100))
  async function addNewSites(sites: NewSite[]) {
    if (!project) return
    setCsvError(null)
    try {
      for (const s of sites) await api.saveLocalLocation(project.acronym, { location_id: s.site, name: s.site, timezone: 'UTC', ignore_dst: false, latitude: s.latitude!, longitude: s.longitude!, coordinate_uncertainty: null, trapper_pk: null })
      await recheckCsv()
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : 'Could not add the locations.')
    }
  }

  /** From another CSV file: reads the visits with the columns as they are mapped. */
  async function readMapped() {
    if (!project) return
    setCsvError(null)
    try {
      setCsvResult(await api.importVisitsCsv(project.acronym, csvText, false, 'mapped', csvMapping, ...withHistory))
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : 'Could not read the file.')
    }
  }

  async function addCsvVisits() {
    if (!project) return
    setCsvError(null)
    try {
      const done = await api.importVisitsCsv(project.acronym, csvText, true, csvFormat, source === 'csv' ? csvMapping : undefined, ...withHistory)
      setCsvResult(done); setCsvSaved(done.saved)
      void findClosed(done.visits)
    } catch (e) {
      setCsvError(e instanceof Error ? e.message : 'Could not save the visits.')
    }
  }

  // A visit needs a site, what was done, and when: a date and a time, the two in one column, or the time the entry was created.
  const mappedEnough = !!csvMapping.location_id && !!csvMapping.actions && (!!csvMapping.when || !!csvMapping.created_at || (!!csvMapping.date && !!csvMapping.time))

  const whereDone = !!project && !!location && !editingWhere
  const whenDone = whereDone && whenConfirmed && !!visit.when
  const asked = fieldsFor(visit.actions)
  // What the last visit to the location left in the camera: the card the one that is collected now was.
  const lastVisit = kept ? latest(kept) : undefined
  const inCamera = lastVisit?.sd ?? null
  const on = (ask: Ask) => ask !== 'off'
  const sdValues = [...(on(asked.sdLeft) ? [visit.sd] : []), ...(on(asked.photos) ? [visit.numPhotos] : []), ...(on(asked.card) ? [visit.card] : [])]
  const cameraValues = [...(on(asked.batteries) ? [visit.batteries] : []), ...(on(asked.status) ? [visit.status] : []), ...(on(asked.dateTime) ? [visit.dateTimeOK] : [])]

  function set<K extends keyof Visit>(field: K, value: Visit[K]) {
    setVisit((v) => ({ ...v, [field]: value }))
  }

  /** The camera of the visit is one of the settings: its id and its model go with the visit. */
  function pickCamera(label: string) {
    const camera = cameras.find((c) => c.label === label)
    setVisit((v) => ({ ...v, details: { ...v.details, camera_id: camera ? cameraKey(camera) : null, camera_model: camera?.camera_model ?? null } }))
  }

  function setDetail<K extends keyof DeploymentFields>(key: K, value: DeploymentFields[K]) {
    setVisit((v) => ({ ...v, details: { ...v.details, [key]: value } }))
  }

  /** The visits the ones just kept closed — their card was collected — so that their images can be imported. */
  // Each visit the ones just added closed: its card was collected, so its images can be imported — a card of its own, with the way in on the right.

  const closedLinks = onImportImages && project && justClosed.length > 0 && (
    <div className="mt-3 space-y-2">
      {justClosed.map((c) => (
        <Notice
          key={`${c.visit.location_id}|${c.visit.date}|${c.visit.time}`} kind="info"
          action={<button type="button" className={btnPrimary} onClick={() => onImportImages({ researchProjectId: project.acronym, visit: c.visit })}>Import the images of {c.visit.session}</button>}
        >
          The visit <strong>{c.visit.session}</strong> to {c.visit.location_id} is closed: its card was collected on {c.end.date}.
        </Notice>
      ))}
    </div>
  )

  async function findClosed(by: { location_id: string; date: string; time: string }[]) {
    if (!project) return
    try {
      const { results } = await api.closedVisits(project.acronym)
      setJustClosed(results.filter((c) => by.some((v) => v.location_id.toLowerCase() === c.end.location_id.toLowerCase() && v.date === c.end.date && v.time === c.end.time)))
    } catch { setJustClosed([]) }
  }

  async function add() {
    setTried(true)
    if (Object.keys(errors).length > 0 || Object.keys(moreErrors).length > 0 || !project || !kept) return
    setSaveError(null)
    // The session is worked out from the visits kept to the location, as its coordinates come from the location.
    const complete: Visit = { ...visit, session: sessionOf(kept.length), site: visit.site.trim() }
    try {
      await api.saveVisit(project.acronym, toStored(complete))
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Could not save the visit.')
      return
    }
    setVisits((list) => [...list, complete])
    setJustAdded(true)
    setJustClosed([])
    setAllVisits((list) => (list ? [...list, toStored(complete)] : list))
    void findClosed([toStored(complete)])
    // The next visit is usually of the same trip: keep who went.
    // The research project stays too; the next visit is to another site, so the location is asked again.
    setVisit({ ...EMPTY_VISIT, trappers: visit.trappers })
    setFilledFrom(null)
    setLocation(undefined)
    setEditingWhere(true)
    setWhenConfirmed(false)
    setTried(false)
  }

  return (
    <div className="mx-auto max-w-[900px] px-4 py-8">
      <h4 className="text-lg font-semibold mb-1">Register visits</h4>
      <p className="text-zinc-500 dark:text-zinc-400 mb-6 text-sm">The visits to the camera traps, from which the deployments are worked out.</p>
      <WizardStep
        n={1} title="Where do the visits come from?" status={source ? 'done' : 'open'} canEdit onEdit={() => setSource(null)}
        description="Enter them by hand, or read them from a file."
        summary={chosen?.title}
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {SOURCE_OPTIONS.map((o) => <TaskCard key={o.value} icon={o.icon} title={o.title} description={o.description} selected={source === o.value} onClick={() => setSource(o.value)} />)}
        </div>
      </WizardStep>

      {source === 'manual' && (
        <>
          {!justAdded && (
          <>
          <WizardStep
            n={2} title="Where was the visit?" status={whereDone ? 'done' : 'open'} canEdit onEdit={() => setEditingWhere(true)}
            description="The research project and the location of the visit. They are kept in the collections folder — pick one that is already there, or add a new research project."
            summary={project && <>
              {project.acronym} · {visit.site}{location?.name ? `, ${location.name}` : ''}
              {kept && <><br />Visit no. {kept.length + 1} · {sessionOf(kept.length)}{latest(kept) && <> — the last was on {latest(kept)!.date} ({actionsText(latest(kept)!.actions)})</>}</>}
            </>}
          >
            <ResearchProjectPicker value={project?.acronym ?? ''} onSelect={selectProject} />
            {project && <LocationPicker researchProjectId={project.acronym} trapperPk={project.trapper_pk} value={visit.site} onSelect={selectLocation} />}
          </WizardStep>

          <WizardStep
            n={3} title="Who went, and when?" status={!whereDone ? 'locked' : whenDone ? 'done' : 'open'} canEdit onEdit={() => setWhenConfirmed(false)}
            description={!location?.timezone
              ? 'Who made the visit, and the day and the time of it.'
              : <>Who made the visit, and the day and the time of it. Times are in <strong>{location.timezone}</strong>, which {location.ignore_dst ? 'has no daylight saving time' : 'follows daylight saving time'}.</>}
            summary={visit.when && <>{visit.trappers.trim() ? `${visit.trappers.trim()} · ` : ''}{visit.when.replace('T', ' ')}</>}
          >
            <FormCard title="Who" description="The trappers kept in the settings.">
              {(() => {
                const chosen = namesOf(visit.trappers)
                const left = trappers.filter((t) => !chosen.some((n) => n.toLowerCase() === t.toLowerCase()))
                return (
                  <>
                    <label className="sr-only" htmlFor="visit-trappers">Trappers</label>
                    <Combobox
                      id="visit-trappers" options={left.map((t) => ({ value: t, label: t }))} value=""
                      onChange={(name) => name && set('trappers', addName(visit.trappers, name))}
                      placeholder={trappers.length === 0 ? 'No trappers yet' : left.length === 0 ? 'Every trapper is on the visit' : 'Select a trapper…'}
                      clearLabel="Clear trapper" disabled={left.length === 0}
                    />
                    {trappers.length === 0 && <p className={hintClass}>The settings have no trappers yet.</p>}
                    {onOpenSettings && (
                      <div className="mt-3">
                        <button type="button" className={btnOutline} onClick={() => onOpenSettings('trappers')}>➕ Add a new trapper</button>
                      </div>
                    )}
                    {chosen.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3" role="list" aria-label="Who went">
                        {chosen.map((name) => (
                          <span key={name} role="listitem" className="inline-flex items-center gap-1.5 rounded-full border border-zinc-300 dark:border-zinc-600 px-3 py-1 text-sm text-zinc-700 dark:text-zinc-300">
                            {name}
                            <button type="button" aria-label={`Remove ${name}`} className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100" onClick={() => set('trappers', removeName(visit.trappers, name))}>×</button>
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )
              })()}
            </FormCard>
            <FormCard title="When">
              <div className="max-w-xs">
                <DateTimeField label="Date and time of the visit" required value={visit.when} onChange={(v) => set('when', v)} error={shown('when')} />
              </div>
            </FormCard>
            <div className="flex justify-between items-center mt-4">
              <button type="button" className={btnOutline} onClick={() => setEditingWhere(true)}><span aria-hidden="true">← </span>Back</button>
              <button type="button" aria-label="Continue to the visit" className={btnPrimary} disabled={!visit.when} onClick={() => setWhenConfirmed(true)}>Continue<span aria-hidden="true"> →</span></button>
            </div>
          </WizardStep>

          <WizardStep n={4} title="Enter the visit" status={whenDone ? 'open' : 'locked'} canEdit={false} onEdit={() => {}} description={<>What was done at this visit. The fields tagged <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">Camtrap DP</span> are those of the deployments table of the Camtrap Data Package; the others are the visit&rsquo;s own.</>}>
            <form noValidate onSubmit={(e) => { e.preventDefault(); void add() }}>
              {lastVisit && (
                <div className="mb-4">
                  {filledFrom === lastVisit.session ? (
                    <Notice kind="success" role="status" action={<button type="button" className={btnOutline} onClick={() => { setVisit((v) => ({ ...EMPTY_VISIT, trappers: v.trappers, session: v.session, when: v.when, site: v.site, actions: v.actions, latitude: v.latitude, longitude: v.longitude })); setFilledFrom(null) }}>Start empty</button>}>
                      The Camera, Site and Grouping sections are filled in from the visit <strong>{lastVisit.session}</strong>, except the notes. What the actions do not ask is left out when the visit is kept.
                    </Notice>
                  ) : (
                    <Notice kind="info" action={<button type="button" className={btnOutline} onClick={() => { setVisit((v) => withoutWhatIsNotAsked(visitFrom(lastVisit, v))); setFilledFrom(lastVisit.session) }}>Fill in from {lastVisit.session}</button>}>
                      This is not the first visit to <strong>{visit.site}</strong>: the last was <strong>{lastVisit.session}</strong>, on {lastVisit.date} ({actionsText(lastVisit.actions)}). Fill in the Camera, Site and Grouping sections with what it said (not the notes).
                    </Notice>
                  )}
                </div>
              )}
              <FormCard title="The visit">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <fieldset className="sm:col-span-2" aria-describedby="visit-actions-hint">
                    <legend className={labelClass}>Actions</legend>
                    <div className="flex flex-wrap gap-x-5 gap-y-2">
                      {ACTIONS.map((a) => (
                        <label key={a} className="inline-flex items-center gap-2 text-sm">
                          <input
                            type="checkbox" checked={visit.actions.includes(a)}
                            onChange={(e) => setVisit((v) => withoutWhatIsNotAsked({ ...v, actions: ACTIONS.filter((x) => (x === a ? e.target.checked : v.actions.includes(x))) }))}
                          />
                          {a}
                        </label>
                      ))}
                    </div>
                    <p id="visit-actions-hint" className={hintClass}>
                      {visit.actions.length === 0 ? 'Choose what was done — more than one if the visit did several things: the rest of the form depends on it.' : visit.actions.map((a) => ACTION_HINTS[a]).join(' ')}
                    </p>
                    {shown('actions') && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{shown('actions')}</p>}
                  </fieldset>
                </div>
                {kept && kept.length === 0 && visit.actions.length > 0 && !visit.actions.includes('Installation') && (
                  <p role="status" className="mt-3 text-xs text-amber-600 dark:text-amber-400">
                    This is the first visit to {visit.site}, and the first one is usually an Installation: no camera is known to be there yet.
                  </p>
                )}
              </FormCard>

              <MoreDetailsForm deployment={visit.details} errors={moreErrors} onField={setDetail} camtrapTags
                afterCamera={(
              <SectionCard
                title="SD card" icon={SD_ICON} total={sdValues.length} filled={sdValues.filter((v) => v.trim()).length}
                summary={[on(asked.sdLeft) && visit.sd.trim() && `left ${visit.sd.trim()}`, on(asked.photos) && visit.numPhotos.trim() && `${visit.numPhotos.trim()} photos`, on(asked.card) && `card ${visit.card === 'Full' ? 'full' : 'OK'}`].filter(Boolean).join(' · ')}
              >
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <div className="flex items-baseline"><label htmlFor="visit-sd" className={labelClass}>SD card left in the camera</label><AskTag ask={asked.sdLeft} /></div>
                    <Combobox
                      id="visit-sd" options={sdCards.map((c) => ({ value: c.label, label: [c.label, [c.brand, c.capacity].filter(Boolean).join(' ')].filter(Boolean).join(' — ') }))}
                      value={visit.sd} onChange={(label) => set('sd', label)} disabled={asked.sdLeft === 'off'} invalid={asked.sdLeft === 'required' && !visit.sd.trim()}
                      placeholder={sdCards.length === 0 ? 'No SD cards yet' : 'Select an SD card…'} clearLabel="Clear SD card"
                    />
                    {(conflicts.sd || shown('sd')) && <p role={conflicts.sd ? 'alert' : undefined} className="text-xs text-red-600 dark:text-red-400 mt-1">{conflicts.sd ?? shown('sd')}</p>}
                    {asked.sdLeft !== 'off' && sdCards.length === 0 && <p className={hintClass}>The settings have no SD cards yet.</p>}
                    {asked.sdLeft !== 'off' && onOpenSettings && (
                      <div className="mt-3">
                        <button type="button" className={btnOutline} onClick={() => onOpenSettings('sdcards')}>➕ Add a new SD card</button>
                      </div>
                    )}
                  </div>
                  <Field id="visit-photos" label="Photos on the card collected" ask={asked.photos} error={shown('numPhotos')}>
                    <input id="visit-photos" inputMode="numeric" className={`${inputClass} ${err('numPhotos') || (asked.photos === 'required' && !visit.numPhotos.trim() ? red : '')}`} value={visit.numPhotos} disabled={asked.photos === 'off'} onChange={(e) => set('numPhotos', e.target.value)} />
                    {asked.photos !== 'off' && (
                      <p className={hintClass}>
                        {inCamera && lastVisit ? `Card collected: ${inCamera} (left on ${lastVisit.date}).` : 'No card is known to have been left in the camera.'}
                      </p>
                    )}
                  </Field>
                </div>
                <div className="mt-4 space-y-3">
                  <SwitchRow label="Card OK" hint="Off if the card was full." checked={visit.card === 'OK'} disabled={asked.card === 'off'} onChange={(on) => set('card', on ? 'OK' : 'Full')} />
                </div>
              </SectionCard>
                )}
                cameraPicker={(
                  <div>
                    <div className="flex items-baseline gap-2 mb-1.5">
                      <label htmlFor="visit-camera" className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Camera id</label>
                      <AskTag ask={asked.camera} />
                      <CamtrapDpTag />
                    </div>
                    <Combobox
                      id="visit-camera" options={cameras.filter((c) => !ofTheSiteCamera || cameraKey(c).toLowerCase() === siteCamera!.camera.toLowerCase() || c.label.toLowerCase() === siteCamera!.camera.toLowerCase()).map((c) => ({ value: c.label, label: c.camera_model ? `${c.label} — ${c.camera_model}` : c.label }))}
                      value={cameras.find((c) => cameraKey(c) === visit.details.camera_id)?.label ?? ''} onChange={pickCamera} disabled={asked.camera === 'off'} invalid={asked.camera === 'required' && !visit.details.camera_id}
                      placeholder={cameras.length === 0 ? 'No cameras yet' : 'Select a camera…'} clearLabel="Clear camera"
                    />
                    {(conflicts.camera || shown('camera')) && <p role={conflicts.camera ? 'alert' : undefined} className="text-xs text-red-600 dark:text-red-400 mt-1">{conflicts.camera ?? shown('camera')}</p>}
                    {ofTheSiteCamera && siteCamera && <p className={hintClass}>The camera at {visit.site.trim()} since {siteCamera.date}. To use another, add an Installation to the visit.</p>}
                    {visit.details.camera_model && <p className={hintClass}>Model: {visit.details.camera_model}</p>}
                    {cameras.length === 0 && <p className={hintClass}>The settings have no cameras yet.</p>}
                    {onOpenSettings && (
                      <div className="mt-3">
                        <button type="button" className={btnOutline} onClick={() => onOpenSettings('cameras')}>➕ Add a new camera</button>
                      </div>
                    )}
                  </div>
                )}
                cameraExtra={{
                total: cameraValues.length, filled: cameraValues.filter((v) => v.trim()).length,
                children: (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <Field id="visit-status" label="Status of the camera" ask={asked.status} error={shown('status')}>
                      <select id="visit-status" className={`${inputClass} ${asked.status === 'required' && !visit.status.trim() ? red : ''}`} value={visit.status} disabled={asked.status === 'off'} onChange={(e) => set('status', e.target.value)}>
                        <option value="">—</option>
                        {CAMERA_STATUSES.map((a) => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </Field>
                    <div className="sm:col-span-2 space-y-3">
                      <SwitchRow label="Batteries OK" hint="Off if the camera had no batteries." checked={visit.batteries === 'OK'} disabled={asked.batteries === 'off'} onChange={(on) => set('batteries', on ? 'OK' : 'Missing')} />
                      <SwitchRow label="Date and time of the camera OK" hint="Off if the clock of the camera was wrong." checked={visit.dateTimeOK === 'Yes'} disabled={asked.dateTime === 'off'} onChange={(on) => set('dateTimeOK', on ? 'Yes' : 'No')} />
                    </div>
                  </div>
                ),
              }} />

              {tried && (Object.keys(errors).length > 0 || Object.keys(moreErrors).length > 0) && (
                <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">
                  The visit cannot be added yet: {[...Object.values(errors), ...Object.values(moreErrors)].join(' ')} (a section that is shut may have the field).
                </p>
              )}
              {saveError && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{saveError}</p>}
              <div className="mt-4 flex justify-end gap-2">
                <button type="button" className={btnOutline} onClick={() => { setVisit({ ...EMPTY_VISIT, site: visit.site, latitude: visit.latitude, longitude: visit.longitude, when: visit.when }); setTried(false); setFilledFrom(null) }}>Clear</button>
                <button type="submit" className={btnPrimary} disabled={!kept}>Add visit</button>
              </div>
            </form>
          </WizardStep>

          </>
          )}

          {visits.length > 0 && (
            <Notice kind="success" role="status" className="mt-6">
              <h5 className="text-sm font-semibold mb-2">{visits.length} {visits.length === 1 ? 'visit' : 'visits'} added</h5>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left opacity-75">
                      <th className="pr-3 py-1 font-medium">Session</th><th className="pr-3 font-medium">When</th>
                      <th className="pr-3 font-medium">Site</th><th className="pr-3 font-medium">Camera</th><th className="font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visits.map((v, i) => (
                      <tr key={i} className="border-t border-emerald-300/60 dark:border-emerald-800">
                        <td className="pr-3 py-1">{v.session}</td><td className="pr-3">{v.when.replace('T', ' ')}</td>
                        <td className="pr-3">{v.site}</td><td className="pr-3">{v.details.camera_id}</td><td>{actionsText(v.actions)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs opacity-75 mt-2">Kept in the visits file of {project?.acronym}.</p>
            </Notice>
          )}
          {closedLinks}
          {justAdded && (
            <div className="mt-6 flex flex-wrap items-center gap-3" role="group" aria-label="What next">
              <p className="mr-auto text-sm text-zinc-600 dark:text-zinc-300">Do you want to add another visit?</p>
              <button type="button" className={btnPrimary} onClick={() => setJustAdded(false)}>Add another visit</button>
              <button type="button" className={btnOutline} onClick={onBack}>Back to the start</button>
            </div>
          )}
        </>
      )}

      {source !== null && source !== 'manual' && (
        <>
          <WizardStep
            n={2} title="Which research project?" status={project ? 'done' : 'open'} canEdit onEdit={() => { setProject(undefined); forgetCsv(); setCsvName(null) }}
            description="The visits are kept in the visits file of a research project of the collections folder; the sites of the file must be its locations."
            summary={project?.acronym}
          >
            <ResearchProjectPicker value={project?.acronym ?? ''} onSelect={(picked) => { setProject(picked); forgetCsv(); setCsvName(null) }} />
          </WizardStep>

          <WizardStep
            n={3} title="Choose the spreadsheet file" status={!project ? 'locked' : csvResult || csvColumns ? 'done' : 'open'} canEdit onEdit={() => { forgetCsv(); setCsvName(null) }}
            description={source === 'epicollect'
              ? <>The Epicollect download of the field trip. Its columns are found by their names ({['1_Responsable', '2_Collection', '4_Location', '5_Camera', '6_Action', '7_Status_of_the_camera', 'created_at'].map((c, i, all) => (
                <span key={c}><code className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-xs font-mono">{c}</code>{i < all.length - 2 ? ', ' : i === all.length - 2 ? ', and ' : ''}</span>
              ))}), whatever the case or the number in front. So are those of the Doñana form. The time of a visit is when its entry was created, put in the timezone of the location.</>
              : 'Any spreadsheet file with a row per visit. Next, you say which column gives each field of a visit.'}
            summary={csvName}
          >
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-6 py-5 space-y-3 mb-4">
              <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">History of visits <span className="text-sm font-normal text-zinc-500 dark:text-zinc-400">optional</span></h5>
              <div className="flex items-center gap-4 flex-wrap">
                <label htmlFor="visits-history" className="inline-flex items-center gap-2 px-5 h-12 rounded-xl border border-zinc-300 dark:border-zinc-600 text-sm font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer">
                  <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
                  Choose history
                </label>
                <span className="text-sm font-mono text-zinc-600 dark:text-zinc-400">{historyName ?? 'No history chosen'}</span>
                {historyName && <button type="button" className={btnOutline} onClick={() => void readHistory(undefined)}>Remove</button>}
                <input id="visits-history" aria-label="History of visits (.xlsx)" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="sr-only" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ''; void readHistory(file) }} />
              </div>
              <p className={hintClass}>The fieldwork datasheet (an .xlsx workbook): its visits complete the ones kept first, and then those of the file are applied on top of both.</p>
            </div>
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-6 py-5 space-y-3">
              <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Spreadsheet file</h5>
              <div className="flex items-center gap-4 flex-wrap">
                <label htmlFor="visits-csv" className="inline-flex items-center gap-2 px-5 h-12 rounded-xl border border-zinc-300 dark:border-zinc-600 text-sm font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer transition-colors">
                  <svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
                  Choose file
                </label>
                <span className="text-sm font-mono text-zinc-600 dark:text-zinc-400">{csvName ?? 'No file chosen'}</span>
                <input id="visits-csv" aria-label="CSV file" type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ''; void readCsv(file) }} />
              </div>
              <p className={hintClass}>Visits that do not have a number yet get the next one for their site. A visit that is already kept (same site, day and time) is left as it is.</p>
            </div>
            {csvError && <p role="alert" className="mt-3 text-sm text-red-600 dark:text-red-400">{csvError}</p>}
          </WizardStep>

          {source === 'csv' && (
            <WizardStep
              n={4} title="Match the columns" status={!csvColumns ? 'locked' : csvResult ? 'done' : 'open'} canEdit onEdit={() => { setCsvResult(null); setCsvSaved(null) }}
              description="For each field of a visit, the column of the file that gives it. What the file has by the names a visit uses is already matched; leave a field with no column if the file does not have it."
            >
              {csvColumns && (
                <>
                  <div className="space-y-2">
                    {csvColumns.fields.map(({ field, label, required }) => {
                      const at = csvColumns.columns.indexOf(csvMapping[field] ?? '')
                      return (
                        <div key={field} className="grid grid-cols-1 sm:grid-cols-[1fr_16rem_10rem] gap-2 items-center">
                          <div>
                            <label htmlFor={`map-${field}`} className="text-sm text-zinc-800 dark:text-zinc-200">{label}</label>
                            {required && <span className="ml-2 text-xs text-red-600 dark:text-red-400">required</span>}
                          </div>
                          <select
                            id={`map-${field}`} className={inputClass} value={csvMapping[field] ?? ''}
                            onChange={(e) => setCsvMapping((m) => ({ ...m, [field]: e.target.value }))}
                          >
                            <option value="">—</option>
                            {csvColumns.columns.map((c, i) => <option key={i} value={c}>{c}</option>)}
                          </select>
                          <span className="text-xs text-zinc-500 dark:text-zinc-400 truncate" aria-label={`Example of ${label}`}>{at >= 0 ? csvColumns.sample[0]?.[at] ?? '' : ''}</span>
                        </div>
                      )
                    })}
                  </div>
                  <p className={hintClass}>A visit needs the site, the actions and when: a date and a time, the two in one column, or the time the entry was created.</p>
                  <div className="mt-4 flex justify-end">
                    <button type="button" className={btnPrimary} disabled={!mappedEnough} onClick={() => void readMapped()}>Read the visits</button>
                  </div>
                </>
              )}
            </WizardStep>
          )}

          <WizardStep n={source === 'csv' ? 5 : 4} title="Check and add the visits" status={csvResult ? 'open' : 'locked'} canEdit={false} onEdit={() => {}} description="What the file says, before it is kept.">
            {csvResult && (
              <>
                <p className="text-base">
                  <strong>{csvResult.visits.length}</strong> {csvResult.visits.length === 1 ? 'visit' : 'visits'} to add
                  {(csvResult.history ?? 0) > 0 && <> ({csvResult.history} from the history)</>}
                  {csvResult.skipped > 0 && <> · {csvResult.skipped} already kept</>}
                  {csvResult.ignored > 0 && <> · {csvResult.ignored} {csvResult.ignored === 1 ? 'entry' : 'entries'} from an old version of the form, ignored</>}
                  {csvResult.problems.length > 0 && <> · <span className="text-red-600 dark:text-red-400">{csvResult.problems.length} {csvResult.problems.length === 1 ? 'row' : 'rows'} with a problem</span></>}
                </p>
                {csvResult.problems.length > 0 && (
                  <ul className="mt-4 mb-5 space-y-2 text-base text-red-600 dark:text-red-400 list-disc pl-6" aria-label="Rows with a problem">
                    {csvResult.problems.map((p) => <li key={`${p.history ? 'h' : 'f'}${p.row}`}>{p.history ? 'History row' : 'Row'} {p.row}: {p.message}</li>)}
                  </ul>
                )}
                {(csvResult.notes?.length ?? 0) > 0 && (
                  <Notice kind="info" className="mt-3 !items-start !rounded-2xl !px-6 !py-5 !text-base leading-relaxed" role="status">
                    <div>
                      <strong className="font-semibold">Worth knowing.</strong>
                      <ul aria-label="Notes on the visits" className="mt-2 list-disc pl-6 space-y-1">{csvResult.notes!.map((n) => <li key={n}>{n}</li>)}</ul>
                    </div>
                  </Notice>
                )}
                {csvResult.warnings.length > 0 && (
                  <Notice kind="warning" className="mt-3 !items-start !rounded-2xl !px-6 !py-5 !text-base leading-relaxed" role="status">
                    <div>
                      <strong className="font-semibold">{csvResult.warnings.length === 1 ? 'One thing' : `${csvResult.warnings.length} things`} to check in the field data.</strong> The visits are kept as the field wrote them.
                      <ul aria-label="What to check" className="mt-2 list-disc pl-6 space-y-1">{csvResult.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                    </div>
                  </Notice>
                )}
                {csvResult.new_sites.length > 0 && (
                  <div className="mt-4 space-y-3" role="group" aria-label="Sites that are not locations yet">
                    <p className="text-base font-semibold">{csvResult.new_sites.length === 1 ? 'A site is' : `${csvResult.new_sites.length} sites are`} not a location of {project?.acronym}</p>
                    <p className="text-sm text-zinc-500 dark:text-zinc-400">Their visits are held. Check each one is really new and not a site misnamed in the field: if it is new, add it as a location; if not, correct its id in the file and read it again.</p>
                    {addable.length > 0 && (
                      <div className="flex items-center gap-3 flex-wrap">
                        <button type="button" className={btnPrimary} onClick={() => void addNewSites(addable)}>Add the {addable.length} {addable.length === 1 ? 'site' : 'sites'} with coordinates as {addable.length === 1 ? 'a location' : 'locations'}</button>
                        <span className="text-xs text-zinc-500 dark:text-zinc-400">The file has their coordinates, taken from their first visit; the ones that look like a misprint are left for you to decide.</span>
                      </div>
                    )}
                    {csvResult.new_sites.map((s) => (
                      <div key={s.site} className="rounded-xl border border-zinc-200 dark:border-zinc-700 px-5 py-4 text-sm">
                        <div className="flex items-start justify-between gap-4 flex-wrap">
                          <div className="min-w-0">
                            <p><span className="font-mono font-semibold">{s.site}</span> · {s.visits} {s.visits === 1 ? 'visit' : 'visits'}, the first on {s.date} ({s.actions.join(' + ')})</p>
                            {s.similar.length > 0 && <p className="mt-1 text-amber-700 dark:text-amber-400">Its id is one character apart from <span className="font-mono">{s.similar.join(', ')}</span>: it may be a misprint.</p>}
                            {s.nearest
                              ? <p className="mt-1 text-zinc-600 dark:text-zinc-400">Its first visit was {s.nearest.distance_m < 1000 ? `${s.nearest.distance_m} m` : `${(s.nearest.distance_m / 1000).toFixed(1)} km`} from <span className="font-mono">{s.nearest.location_id}</span>{s.nearest.distance_m < 100 ? ' — so close that it may be the same site.' : '.'}</p>
                              : <p className="mt-1 text-zinc-600 dark:text-zinc-400">{s.latitude == null ? 'The file has no coordinates for it.' : 'There is no location to compare it with.'}</p>}
                          </div>
                          <button type="button" className={btnOutline} disabled={s.latitude == null || s.longitude == null} title={s.latitude == null ? 'The file gives no coordinates for it: add the location in the settings' : undefined}
                                  onClick={() => void addNewSite(s)}>Add {s.site} as a location</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {missingLocations && (
                  <Notice kind="info" className="mt-3 !items-start !rounded-2xl !px-6 !py-5 !text-base leading-relaxed">
                    You can also create the locations by hand, from a spreadsheet file or from Trapper. The file is checked again when you come back.
                    {onOpenSettings && project && (
                      <div className="mt-4">
                        <button type="button" className="px-6 h-12 rounded-xl border border-zinc-300 dark:border-zinc-600 bg-white/5 text-base font-medium text-zinc-900 dark:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors" onClick={() => onOpenSettings('locations', project.acronym)}>Go to the locations of {project.acronym}</button>
                      </div>
                    )}
                  </Notice>
                )}
                {csvResult.visits.length > 0 && csvSaved === null && (
                  <div className="overflow-x-auto mt-3">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-zinc-500 dark:text-zinc-400">
                          <th className="pr-3 py-1 font-medium">Session</th><th className="pr-3 font-medium">When</th><th className="pr-3 font-medium">Site</th>
                          <th className="pr-3 font-medium">Camera</th><th className="font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {csvResult.visits.map((v, i) => (
                          <tr key={i} className="border-t border-zinc-200 dark:border-zinc-700">
                            <td className="pr-3 py-1">{v.session}</td><td className="pr-3">{v.date} {v.time}</td><td className="pr-3">{v.location_id}</td>
                            <td className="pr-3">{v.camera_id}</td><td>{actionsText(v.actions)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {csvSaved === null ? (
                  <div className="mt-4 flex justify-end">
                    <button type="button" className={btnPrimary} disabled={csvResult.visits.length === 0} onClick={() => void addCsvVisits()}>
                      Add {csvResult.visits.length} {csvResult.visits.length === 1 ? 'visit' : 'visits'}
                    </button>
                  </div>
                ) : (
                  <>
                    <Notice kind="success" role="status" className="mt-4 !items-center !rounded-2xl !px-6 !py-5 !text-base">
                      <strong>{csvSaved} {csvSaved === 1 ? 'visit' : 'visits'} added</strong> to {project?.acronym}. The deployments will be worked out from {csvSaved === 1 ? 'it' : 'them'}.
                      {csvResult?.report && <> The report of the import: <span className="font-mono text-sm break-all">{csvResult.report}</span>.</>}
                    </Notice>
                    {closedLinks}
                    <div className="mt-5 flex flex-wrap items-center gap-3" role="group" aria-label="What next">
                      <button type="button" className="px-6 h-12 rounded-xl border border-zinc-300 dark:border-zinc-600 text-base font-medium text-zinc-900 dark:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                              onClick={() => { forgetCsv(); setCsvName(null); setProject(undefined); setSource(null) }}>Register more visits</button>
                      <button type="button" className="px-6 h-12 rounded-xl bg-blue-600 text-white text-base font-medium hover:bg-blue-700 transition-colors" onClick={onBack}>Back to the menu</button>
                    </div>
                  </>
                )}
              </>
            )}
          </WizardStep>
        </>
      )}

      {!justAdded && (
        <div className="mt-6">
          <BackButton onClick={onBack} />
        </div>
      )}
    </div>
  )
}
