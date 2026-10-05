import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { isValidTimezone, shownErrors, stampTimezone, validateDeployment } from '../deploymentValidation'
import ResearchProjectPicker from '../components/ResearchProjectPicker'
import { EMPTY_DEPLOYMENT_FIELDS } from '../types'
import type {
  DeploymentCheck, DeploymentCheckResult, DeploymentFields, ImageCheck, ImportEvent, LocalLocation, LocalResearchProject,
  PreprocessingOptions, SessionScan, StatisticsParams, UploadTarget, ValidationResult,
} from '../types'
import {
  ALL_DEPLOYMENT_CHECKS, CheckTable, DEFAULT_CHECK_SETTINGS, DEPLOYMENT_CHECK_OPTIONS, DeploymentCheckReport, Field,
  FormCard, IMAGE_CHECK_OPTIONS, PreprocessItem, SelectField, SmallSpinner, StepHeading,
  DeploymentFormBody, LocationTimeNote, ValidationReport, buildDeploymentId, fillFromPreviousRevision, btnOutline, btnPrimary, deploymentCheckPassed, describePreprocessing, imageCheckPassed,
  inputClass, labelClass, statParamsOf, statParamsValid, toggled,
} from './ImportDeploymentPage'
import type { PreprocessStep, WizardSettings } from './ImportDeploymentPage'

type StepKey = 'folder' | 'validate' | 'origin' | 'details' | 'checks' | 'preprocessing' | 'import'

const STEPS: { key: StepKey; label: string }[] = [
  { key: 'folder', label: 'Session' },
  { key: 'validate', label: 'Validate' },
  { key: 'origin', label: 'Origin' },
  { key: 'details', label: 'Details' },
  { key: 'checks', label: 'Postvalidation' },
  { key: 'preprocessing', label: 'Preprocessing' },
  { key: 'import', label: 'Import' },
]

/** What is asked of each deployment of the session: its own location, period, camera and notes — the same fields
 * as a single deployment's. Its dates carry the designator of its timezone, as there. */
interface Entry {
  fields: DeploymentFields
  timezone: string
  /** The location's summer-time setting, as its timezone is: read from it, kept in it. */
  ignoreDst: boolean | null
  /** Whether the camera, site and notes are open in the form. */
  showAll: boolean
  /** Where the location was deduced from, until it is picked by hand. */
  locationFrom?: 'folder' | 'log'
}

interface Outcome<T> { result?: T; error?: string }

interface ImportRun { events: ImportEvent[]; done: boolean; error?: string; destDir?: string }

const EMPTY_LOCATION_DRAFT = { location_id: '', name: '', timezone: '', ignore_dst: true, latitude: '', longitude: '' }

/** The location a subfolder is named after — "DONA_01" for the folder "DONA_01", "R0003-DONA_01" or "dona_01 (2)" —
 * when there is exactly one such. */
export function matchLocation(folderName: string, locations: LocalLocation[]): LocalLocation | undefined {
  const folder = folderName.toLowerCase()
  const exact = locations.find((l) => l.location_id.toLowerCase() === folder)
  if (exact) return exact
  const contained = locations.filter((l) => folder.includes(l.location_id.toLowerCase()))
  return contained.length === 1 ? contained[0] : undefined
}

/** What a location gives its deployment: its id, name and coordinates. */
function locationFields(location?: LocalLocation): Partial<DeploymentFields> {
  return {
    location_id: location?.location_id ?? null, location_name: location?.name ?? null,
    latitude: location?.latitude ?? null, longitude: location?.longitude ?? null, coordinate_uncertainty: location?.coordinate_uncertainty ?? null,
  }
}

interface Props {
  /** Offered once the session is imported: goes to the upload page, on the revision's collection. */
  onUpload?: (target: UploadTarget) => void
}

export default function ImportSessionPage({ onUpload }: Props = {}) {
  const [step, setStep] = useState(0)
  const stepKey = STEPS[step].key

  // ── Session folder ──
  const [sessionDir, setSessionDir] = useState('')
  const [scan, setScan] = useState<SessionScan | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [browsing, setBrowsing] = useState(false)
  const [included, setIncluded] = useState<Set<string>>(new Set())

  // ── Common to the whole session ──
  const [checkSettings, setCheckSettings] = useState<WizardSettings>(DEFAULT_CHECK_SETTINGS)
  const [imageChecks, setImageChecks] = useState<Set<ImageCheck>>(new Set(['corrupted', 'sequence', 'structure', 'camera', 'exif', 'duplicates']))
  const [requiredImageChecks, setRequiredImageChecks] = useState<Set<ImageCheck>>(new Set())
  const [deploymentChecks, setDeploymentChecks] = useState<Set<DeploymentCheck>>(new Set(ALL_DEPLOYMENT_CHECKS))
  const [requiredDeploymentChecks, setRequiredDeploymentChecks] = useState<Set<DeploymentCheck>>(new Set())
  const [preprocessSteps, setPreprocessSteps] = useState<Set<PreprocessStep>>(new Set(['rename', 'resize', 'metadata']))
  const [exiftool, setExiftool] = useState<boolean | null>(null)
  const [revision, setRevision] = useState('')
  // The log the revision was deduced from, until it is edited.
  const [revisionFromLog, setRevisionFromLog] = useState<string | null>(null)
  // The revision starts as the next one expected for the deployments' locations, until it is typed.
  const revisionTouched = useRef(false)
  const [revisionSuggested, setRevisionSuggested] = useState(false)
  // Set the moment a value is edited (refs, so a settings response arriving meanwhile never puts it back).
  const preprocessTouched = useRef(false)

  // ── Origin ──
  // The research project picked, as in the Origin step of Import deployment (see ResearchProjectPicker).
  const [project, setProject] = useState<LocalResearchProject | undefined>(undefined)
  const projectId = project?.acronym ?? ''
  const [localLocations, setLocalLocations] = useState<LocalLocation[]>([])
  const [originError, setOriginError] = useState<string | null>(null)

  // ── Per deployment ──
  const [drafts, setDrafts] = useState<Record<string, Entry>>({})
  const [activeName, setActiveName] = useState('')
  const [filter, setFilter] = useState('')
  const [onlyIncomplete, setOnlyIncomplete] = useState(false)
  // Where each deployment is already kept, by its id — importing it again would be refused.
  const [existing, setExisting] = useState<Record<string, string | null>>({})
  // Whether each deployment is known to have an earlier revision (true) or not (false), by research project and id — until it is looked up, unknown.
  const [previousKnown, setPreviousKnown] = useState<Record<string, boolean>>({})
  const [filling, setFilling] = useState(false)
  // What the last fill said, and whether it was for one deployment or for all of them.
  const [fillMessage, setFillMessage] = useState<{ scope: 'one' | 'all'; text: string } | null>(null)
  const [addingLocation, setAddingLocation] = useState(false)
  const [locationDraft, setLocationDraft] = useState(EMPTY_LOCATION_DRAFT)
  const [locationError, setLocationError] = useState<string | null>(null)
  const [savingDetails, setSavingDetails] = useState(false)
  const [detailsError, setDetailsError] = useState<string | null>(null)
  const [validations, setValidations] = useState<Record<string, Outcome<ValidationResult>>>({})
  const [validating, setValidating] = useState(false)
  const [checks, setChecks] = useState<Record<string, Outcome<DeploymentCheckResult>>>({})
  const [checking, setChecking] = useState(false)
  const [runs, setRuns] = useState<Record<string, ImportRun>>({})
  const [importing, setImporting] = useState(false)
  const [collectionPath, setCollectionPath] = useState<string | null>(null)
  const [openFolderError, setOpenFolderError] = useState<string | null>(null)

  const chosen = (scan?.deployments ?? []).filter((d) => included.has(d.name))

  useEffect(() => {
    if (stepKey !== 'validate' && stepKey !== 'checks' && stepKey !== 'preprocessing') return
    let cancelled = false
    api.getSettings()
      .then((s) => {
        if (cancelled) return
        setCheckSettings({ VALIDATION: s.VALIDATION, POSTVALIDATION: s.POSTVALIDATION, PREPROCESSING: s.PREPROCESSING })
        if (!preprocessTouched.current) setPreprocessSteps(new Set((['rename', 'resize', 'metadata'] as const).filter((k) => s.PREPROCESSING[k])))
      })
      .catch(() => { /* the settings can't be read: every check stays shown */ })
    return () => { cancelled = true }
  }, [stepKey])

  useEffect(() => {
    if (stepKey !== 'preprocessing') return
    let cancelled = false
    api.exiftoolStatus().then((s) => { if (!cancelled) setExiftool(s.available) }).catch(() => { if (!cancelled) setExiftool(null) })
    return () => { cancelled = true }
  }, [stepKey])

  useEffect(() => {
    if (!projectId) { setLocalLocations([]); return }
    let cancelled = false
    api.listLocalLocations(projectId)
      .then(({ results }) => { if (!cancelled) setLocalLocations(results) })
      .catch((e) => { if (!cancelled) setOriginError(e instanceof Error ? e.message : 'Could not read the locations.') })
    return () => { cancelled = true }
  }, [projectId])

  // The details of each deployment start from what the scan found and the location its folder is named after.
  useEffect(() => {
    if (stepKey !== 'details' || !scan) return
    setDrafts((current) => {
      const next = { ...current }
      for (const d of scan.deployments.filter((x) => included.has(x.name))) {
        if (next[d.name]) continue
        // The folder's name first; failing that, the id its row in the timestamp log gives it.
        const byFolder = matchLocation(d.name, localLocations)
        const byLog = byFolder || !d.log_deployment_id ? undefined : matchLocation(d.log_deployment_id, localLocations)
        const location = byFolder ?? byLog
        const timezone = location?.timezone ?? ''
        next[d.name] = {
          timezone, ignoreDst: location?.ignore_dst ?? null, showAll: false, locationFrom: byFolder ? 'folder' : byLog ? 'log' : undefined,
          fields: {
            ...EMPTY_DEPLOYMENT_FIELDS, ...locationFields(location),
            start_date: stampTimezone(d.start_date ?? '', timezone), end_date: d.end_date ? stampTimezone(d.end_date, timezone) : null,
            camera_model: d.camera_model, camera_id: d.camera_id,
          },
        }
      }
      return next
    })
    setActiveName((name) => (name && included.has(name) ? name : [...included][0] ?? ''))
  }, [stepKey, scan, included, localLocations])

  // Which of the deployments the revision and the locations name are already kept — said as soon as it can be known.
  const knownIds = chosen.map((d) => fieldsOf(d.name).deployment_id).filter(Boolean).sort().join('\n')
  useEffect(() => {
    if (stepKey !== 'details' || !projectId || !knownIds) { setExisting({}); return }
    let cancelled = false
    api.existingDeployments(projectId, knownIds.split('\n'))
      .then(({ results }) => { if (!cancelled) setExisting(results) })
      .catch(() => { if (!cancelled) setExisting({}) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepKey, projectId, knownIds])

  // The revision starts as the next one expected for the deployments' locations — the highest of them — until it is typed.
  const locationIds = [...new Set(chosen.map((d) => fieldsOf(d.name).location_id).filter((id): id is string => Boolean(id)))].sort().join('\n')
  useEffect(() => {
    if (stepKey !== 'details' || !projectId || !locationIds || revisionTouched.current || revisionFromLog) return
    let cancelled = false
    Promise.all(locationIds.split('\n').map((id) => api.nextRevision(projectId, id)))
      .then((answers) => {
        if (cancelled || revisionTouched.current) return
        setRevision(String(Math.max(...answers.map((a) => a.next)))); setRevisionSuggested(true)
      })
      .catch(() => { /* no suggestion: it is typed */ })
    return () => { cancelled = true }
  }, [stepKey, projectId, locationIds, revisionFromLog])

  // ── The session folder ──

  async function handleBrowse() {
    setBrowsing(true); setScanError(null)
    try {
      const { path } = await api.browseFolder()
      if (path) { setSessionDir(path); setScan(null) }
    } catch (e) {
      setScanError(e instanceof Error ? e.message : 'Could not open the folder browser.')
    } finally {
      setBrowsing(false)
    }
  }

  async function handleScan() {
    setScanning(true); setScanError(null); setScan(null)
    try {
      const result = await api.scanSession(sessionDir)
      setScan(result)
      const logged = result.timestamp_log?.revision
      if (logged) { setRevision(String(logged)); setRevisionFromLog(result.timestamp_log!.name) }
      else if (revisionFromLog) { setRevision(''); setRevisionFromLog(null) }
      setIncluded(new Set(result.deployments.filter((d) => d.image_count > 0).map((d) => d.name)))
      autoFilled.current.clear(); setPreviousKnown({}); setDrafts({}); setValidations({}); setChecks({}); setRuns({})
    } catch (e) {
      setScanError(e instanceof Error ? e.message : 'Could not scan the folder.')
    } finally {
      setScanning(false)
    }
  }

  // ── Validate ──

  const shownImageChecks = IMAGE_CHECK_OPTIONS.filter((o) => checkSettings.VALIDATION[o.value])
  const runnableImageChecks = shownImageChecks.map((o) => o.value).filter((c) => imageChecks.has(c))

  async function handleValidate() {
    setValidating(true); setValidations({})
    for (const d of chosen) {
      try {
        const result = await api.validateImages(d.path, runnableImageChecks)
        setValidations((v) => ({ ...v, [d.name]: { result } }))
      } catch (e) {
        setValidations((v) => ({ ...v, [d.name]: { error: e instanceof Error ? e.message : 'Could not validate the images.' } }))
      }
    }
    setValidating(false)
  }

  const requiredImageChecksOk = [...requiredImageChecks]
    .filter((c) => checkSettings.VALIDATION[c])
    .every((c) => chosen.every((d) => imageCheckPassed(c, validations[d.name]?.result ?? null) === true))

  // ── Origin ──

  // ── Details ──

  const revisionNumber = Number(revision)
  const revisionValid = revision.trim() !== '' && Number.isInteger(revisionNumber) && revisionNumber >= 1 && revisionNumber <= 9999

  function fieldsOf(name: string): DeploymentFields {
    const entry = drafts[name]
    if (!entry) return EMPTY_DEPLOYMENT_FIELDS
    return { ...entry.fields, deployment_id: buildDeploymentId(revision, entry.fields.location_id) }
  }

  const errorsOf = (name: string) => validateDeployment(fieldsOf(name), drafts[name]?.timezone ?? '')
  const idCounts = chosen.reduce<Record<string, number>>((n, d) => {
    const id = fieldsOf(d.name).deployment_id
    if (id) n[id] = (n[id] ?? 0) + 1
    return n
  }, {})
  const duplicated = (name: string) => (idCounts[fieldsOf(name).deployment_id] ?? 0) > 1
  /** How many things are wrong or missing in a deployment's details. */
  const problemsOf = (name: string) => (drafts[name] ? Object.keys(errorsOf(name)).length + (duplicated(name) ? 1 : 0) : 1)
  const completed = chosen.filter((d) => problemsOf(d.name) === 0).length
  // The deployments whose id is known — the ones a previous revision can be looked up for.
  const fillable = chosen.filter((d) => fieldsOf(d.name).deployment_id).map((d) => d.name)
  const existingFolder = (name: string) => existing[fieldsOf(name).deployment_id] ?? null
  const existingNames = chosen.filter((d) => existingFolder(d.name))
  // There can only be an earlier revision after the first, and once it is known that a deployment has none, it is not offered.
  const hasEarlierRevision = (name: string) => {
    const id = fieldsOf(name).deployment_id
    return revisionValid && revisionNumber > 1 && Boolean(id) && previousKnown[`${projectId}|${id}`] !== false
  }
  const canFillFromPrevious = chosen.some((d) => hasEarlierRevision(d.name))
  const deduced = chosen.filter((d) => drafts[d.name]?.locationFrom)
  const detailsReady = revisionValid && chosen.length > 0 && completed === chosen.length

  function updateEntry(name: string, change: (entry: Entry) => Entry) {
    setDrafts((all) => (all[name] ? { ...all, [name]: change(all[name]) } : all))
  }

  function updateField<K extends keyof DeploymentFields>(name: string, key: K, value: DeploymentFields[K]) {
    updateEntry(name, (e) => ({ ...e, fields: { ...e.fields, [key]: value } }))
  }

  /** Sets the timezone and re-stamps both dates with the designator it gives them — the wall-clock time stays. */
  function setTimezone(name: string, timezone: string) {
    updateEntry(name, (e) => ({
      ...e, timezone,
      fields: { ...e.fields, start_date: stampTimezone(e.fields.start_date, timezone), end_date: e.fields.end_date ? stampTimezone(e.fields.end_date, timezone) : e.fields.end_date },
    }))
  }

  function pickLocation(name: string, locationId: string, known?: LocalLocation) {
    const location = known ?? localLocations.find((l) => l.location_id === locationId)
    updateEntry(name, (e) => ({ ...e, locationFrom: undefined, ignoreDst: location?.ignore_dst ?? null, fields: { ...e.fields, ...locationFields(location) } }))
    if (location?.timezone) setTimezone(name, location.timezone)
  }

  /** Fills these deployments in from the previous revision of the same one — R0002-DONA_01 from R0001-DONA_01 —
   * keeping their own location, dates and id. The camera model and id are only filled in when the images gave none. */
  async function fillFromPrevious(names: string[], scope: 'one' | 'all', automatic = false) {
    const ids = names.map((n) => fieldsOf(n).deployment_id)
    setFilling(true); setFillMessage(null)
    try {
      const { results } = await api.previousDeployments(projectId, ids)
      setPreviousKnown((known) => ({ ...known, ...Object.fromEntries(ids.map((id) => [`${projectId}|${id}`, Boolean(results[id])])) }))
      setDrafts((all) => {
        const next = { ...all }
        names.forEach((name, i) => {
          const previous = results[ids[i]]?.deployment
          if (!previous || !next[name]) return
          next[name] = { ...next[name], showAll: true, fields: fillFromPreviousRevision(next[name].fields, previous) }
        })
        return next
      })
      const found = names.filter((_, i) => results[ids[i]]).length
      const say = (text: string) => setFillMessage({ scope, text })
      if (automatic && found === 0) return // nothing to say when there simply is no earlier revision
      say(names.length === 1
        ? (found ? `Filled in from ${results[ids[0]]!.deployment_id}.` : 'There is no previous revision of this deployment to fill it in from.')
        : `Filled in ${found} of ${names.length} from their previous revision${found < names.length ? ` — the other ${names.length - found} have none` : ''}.`)
    } catch (e) {
      setFillMessage({ scope, text: e instanceof Error ? e.message : 'Could not read the previous revisions.' })
    } finally {
      setFilling(false)
    }
  }

  // As soon as the revision gives a deployment its id, it is filled in from its previous revision — once, so what is typed after is kept.
  const autoFilled = useRef(new Set<string>())
  useEffect(() => {
    if (stepKey !== 'details' || !projectId || !revisionValid || revisionNumber <= 1 || !knownIds) return // revision 1 has no earlier one
    const timer = setTimeout(() => {
      const todo = chosen.filter((d) => {
        const id = fieldsOf(d.name).deployment_id
        return id && drafts[d.name] && !autoFilled.current.has(`${projectId}|${id}`)
      })
      if (todo.length === 0) return
      todo.forEach((d) => autoFilled.current.add(`${projectId}|${fieldsOf(d.name).deployment_id}`))
      void fillFromPrevious(todo.map((d) => d.name), 'all', true)
    }, 400) // the revision may still be being typed
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepKey, projectId, revisionValid, knownIds, Object.keys(drafts).length])

  const locationErrors = {
    location_id: locationDraft.location_id.trim() ? undefined : 'Required',
    timezone: locationDraft.timezone && !isValidTimezone(locationDraft.timezone) ? 'Not a known IANA timezone (e.g. Europe/Madrid).' : undefined,
    latitude: coordinateError(locationDraft.latitude, 90),
    longitude: coordinateError(locationDraft.longitude, 180),
  }
  const canSaveLocation = Object.values(locationErrors).every((e) => !e)

  async function handleSaveLocation() {
    setLocationError(null)
    try {
      const saved = await api.saveLocalLocation(projectId, {
        location_id: locationDraft.location_id.trim(), name: locationDraft.name.trim() || null, timezone: locationDraft.timezone.trim() || null, ignore_dst: locationDraft.ignore_dst,
        trapper_pk: null, latitude: Number(locationDraft.latitude), longitude: Number(locationDraft.longitude), coordinate_uncertainty: null,
      })
      setLocalLocations((list) => [...list, saved])
      pickLocation(activeName, saved.location_id, saved)
      setAddingLocation(false); setLocationDraft(EMPTY_LOCATION_DRAFT)
    } catch (e) {
      setLocationError(e instanceof Error ? e.message : 'Could not save the location.')
    }
  }

  /** Each deployment's row goes into its collection's FileTimestampLog before the postvalidation. */
  async function handleContinueFromDetails() {
    setSavingDetails(true); setDetailsError(null)
    try {
      for (const d of chosen) await api.writeTimestampLog(projectId, fieldsOf(d.name))
    } catch (e) {
      setDetailsError(e instanceof Error ? e.message : "Could not write the collection's timestamp log.")
      setSavingDetails(false)
      return
    }
    setSavingDetails(false)
    setChecks({})
    setStep((s) => s + 1)
  }

  // ── Postvalidation ──

  const shownDeploymentChecks = DEPLOYMENT_CHECK_OPTIONS.filter((o) => checkSettings.POSTVALIDATION[o.value])
  const runnableDeploymentChecks = shownDeploymentChecks.map((o) => o.value).filter((c) => deploymentChecks.has(c))
  // The tolerance and what the statistical checks mean by a sequence and by similar come from the settings.
  const toleranceHours = String(checkSettings.POSTVALIDATION.tolerance_hours)
  const statistics: StatisticsParams | null = statParamsValid(statParamsOf(checkSettings.POSTVALIDATION))

  async function handleCheck() {
    setChecking(true); setChecks({})
    for (const d of chosen) {
      try {
        const result = await api.validateDeployment(d.path, fieldsOf(d.name), runnableDeploymentChecks, {
          collectionName: null, expectedLocationId: drafts[d.name].fields.location_id || null, toleranceHours: Number(toleranceHours),
          researchProjectId: projectId || null, statistics: statistics ?? undefined,
        })
        setChecks((c) => ({ ...c, [d.name]: { result } }))
      } catch (e) {
        setChecks((c) => ({ ...c, [d.name]: { error: e instanceof Error ? e.message : 'Could not check the deployment.' } }))
      }
    }
    setChecking(false)
  }

  const requiredDeploymentChecksOk = [...requiredDeploymentChecks]
    .filter((c) => checkSettings.POSTVALIDATION[c])
    .every((c) => chosen.every((d) => deploymentCheckPassed(c, checks[d.name]?.result ?? null) === true))

  // ── Preprocessing & import ──

  const preSettings = checkSettings.PREPROCESSING
  const effectiveSteps = new Set([...preprocessSteps].filter((k) => k !== 'metadata' || exiftool !== false))
  const pending = chosen.filter((d) => !runs[d.name]?.done)

  async function handleImport() {
    setImporting(true); setOpenFolderError(null)
    for (const d of pending) {
      const name = d.name
      setRuns((r) => ({ ...r, [name]: { events: [], done: false } }))
      const onEvent = (event: ImportEvent) => setRuns((r) => ({
        ...r, [name]: { ...r[name], events: [...r[name].events, event], ...(event.type === 'done' ? { done: true, destDir: event.dest_dir } : {}) },
      }))
      try {
        const deployment = fieldsOf(name)
        // Asked again each time: the first deployment creates the revision's collection, the next ones find it.
        const planned = await api.collectionPath(projectId, deployment.deployment_id)
        setCollectionPath(planned.path)
        const options: PreprocessingOptions = {
          rename: effectiveSteps.has('rename'), resize: effectiveSteps.has('resize'), resize_width: preSettings.resize_width,
          metadata: effectiveSteps.has('metadata'), owner: preSettings.owner, publisher: preSettings.publisher,
          coverage: preSettings.coverage, license_url: preSettings.license_url, research_project: project?.name ?? '',
          convert_to_utc: preSettings.convert_to_utc,
        }
        await api.importLocal(d.path, planned.path, planned.exists ? null : planned.collection, deployment, options, onEvent)
      } catch (e) {
        setRuns((r) => ({ ...r, [name]: { ...r[name], error: e instanceof Error ? e.message : 'The import failed.' } }))
      }
    }
    setImporting(false)
  }

  async function handleOpenFolder() {
    setOpenFolderError(null)
    try { await api.openFolder(collectionPath!) } catch (e) { setOpenFolderError(e instanceof Error ? e.message : String(e)) }
  }

  const allDone = chosen.length > 0 && pending.length === 0
  const failures = chosen.filter((d) => runs[d.name]?.error && !runs[d.name]?.done).length

  const active = scan?.deployments.find((d) => d.name === activeName)
  const activeIndex = chosen.findIndex((d) => d.name === activeName)
  const visible = chosen.filter((d) => d.name.toLowerCase().includes(filter.trim().toLowerCase()) && (!onlyIncomplete || problemsOf(d.name) > 0))
  // The next deployment after this one (wrapping round) that still has something to fix.
  const nextIncomplete = [...chosen.slice(activeIndex + 1), ...chosen.slice(0, Math.max(activeIndex, 0))].find((d) => d.name !== activeName && problemsOf(d.name) > 0)
  function selectDeployment(name: string) { setActiveName(name); setAddingLocation(false); setFillMessage((m) => (m?.scope === 'one' ? null : m)) }
  const activeEntry = drafts[activeName]
  const activeErrors = activeName && activeEntry ? shownErrors(errorsOf(activeName)) : {}
  const activeFields = activeName && activeEntry ? fieldsOf(activeName) : null

  const canContinue: Record<StepKey, boolean> = {
    folder: Boolean(scan) && chosen.length > 0,
    validate: requiredImageChecksOk && !validating,
    origin: Boolean(projectId),
    details: detailsReady && !savingDetails,
    checks: requiredDeploymentChecksOk && !checking,
    preprocessing: true,
    import: false,
  }

  return (
    <div className="max-w-screen-md mx-auto px-4 py-8">
      <h2 className="text-xl font-bold mb-1 text-zinc-900 dark:text-zinc-100">Import session</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        Imports a folder of deployments — one subfolder each — into the local collections folder. The revision, the checks and the
        preprocessing are the same for all of them; the location, the dates and the camera are asked for each.
      </p>

      <div className="flex items-start mb-10">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-start flex-1">
            <div className="flex flex-col items-center" style={{ minWidth: 56 }}>
              <div className={`w-9 h-9 rounded-full flex items-center justify-center font-bold mb-1 text-sm ${
                i < step ? 'bg-emerald-600 text-white' : i === step ? 'bg-blue-600 text-white' : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400'
              }`}>
                {i < step ? '✓' : i + 1}
              </div>
              <small className={`text-xs whitespace-nowrap ${i === step ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-500 dark:text-zinc-400'}`}>{s.label}</small>
            </div>
            {i < STEPS.length - 1 && <div className={`flex-1 border-t mx-1 mt-[18px] ${i < step ? 'border-emerald-500' : 'border-zinc-300 dark:border-zinc-700'}`} />}
          </div>
        ))}
      </div>

      {/* ── Step: the session folder ── */}
      {stepKey === 'folder' && (
        <div>
          <StepHeading>Session folder</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">A folder with one subfolder per deployment, on this machine.</p>
          <div className="mb-4 rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
            Copy the images from the cameras&rsquo; memory cards to a local folder first — don&rsquo;t point this at a card itself.
          </div>
          <label className={labelClass} htmlFor="session-dir">Folder path</label>
          <div className="flex gap-2">
            <input id="session-dir" className={`${inputClass} flex-1`} placeholder="/home/me/Pictures/R0003" value={sessionDir}
                   onChange={(e) => { setSessionDir(e.target.value); setScan(null) }} />
            <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={browsing} onClick={handleBrowse}>
              {browsing && <SmallSpinner />}{browsing ? 'Browsing…' : 'Browse…'}
            </button>
            <button type="button" className={btnOutline} disabled={!sessionDir || scanning} onClick={handleScan}>
              {scanning ? <SmallSpinner /> : 'Scan'}
            </button>
          </div>
          {scanError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{scanError}</p>}
          {scan && (
            <div className="mt-4">
              {scan.warnings.map((w, i) => <p key={i} className="text-sm text-amber-600 dark:text-amber-400">⚠ {w}</p>)}
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">{scan.deployments.length} subfolder(s) — tick the ones to import.</p>
              <table className="w-full text-sm border border-zinc-200 dark:border-zinc-700 rounded">
                <thead className="bg-zinc-50 dark:bg-zinc-800/50 text-xs text-zinc-500 dark:text-zinc-400">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-center">Import</th>
                    <th scope="col" className="px-3 py-2 text-left">Subfolder</th>
                    <th scope="col" className="px-3 py-2 text-right">Images</th>
                    <th scope="col" className="px-3 py-2 text-left">Dates</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                  {scan.deployments.map((d) => (
                    <tr key={d.name}>
                      <td className="px-3 py-2 text-center">
                        <input type="checkbox" aria-label={d.name} checked={included.has(d.name)} onChange={() => setIncluded((s) => toggled(s, d.name))} />
                      </td>
                      <td className="px-3 py-2 font-mono">
                        {d.name}
                        {d.warnings.map((w, i) => <p key={i} className="text-xs font-sans text-amber-600 dark:text-amber-400">⚠ {w}</p>)}
                      </td>
                      <td className="px-3 py-2 text-right">{d.image_count}</td>
                      <td className="px-3 py-2 text-zinc-600 dark:text-zinc-400">{d.start_date?.slice(0, 10) ?? '?'} → {d.end_date?.slice(0, 10) ?? '?'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Step: validate every deployment's images ── */}
      {stepKey === 'validate' && (
        <div>
          <StepHeading>Validate the images</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            The same checks over each of the {chosen.length} deployment(s) — pick which to run, and which must pass in all of them before moving on.
          </p>
          {shownImageChecks.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">Every validation check is turned off in the settings, so there is nothing to run here — go on.</p>
          ) : (
            <>
              <CheckTable options={shownImageChecks} enabled={imageChecks} required={requiredImageChecks}
                          onToggleEnabled={(c) => setImageChecks((prev) => {
                            const next = toggled(prev, c)
                            if (!next.has(c)) setRequiredImageChecks((r) => (r.has(c) ? toggled(r, c) : r))
                            return next
                          })}
                          onToggleRequired={(c) => setRequiredImageChecks((s) => toggled(s, c))}
                          onSetEnabled={setImageChecks} onSetRequired={setRequiredImageChecks} />
              <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={validating || runnableImageChecks.length === 0} onClick={handleValidate}>
                {validating && <SmallSpinner />}{validating ? 'Validating…' : 'Run validation'}
              </button>
            </>
          )}
          <div className="mt-4 space-y-2">
            {chosen.filter((d) => validations[d.name]).map((d) => {
              const outcome = validations[d.name]
              const all = runnableImageChecks.map((c) => imageCheckPassed(c, outcome.result ?? null))
              return (
                <details key={d.name} className="rounded border border-zinc-200 dark:border-zinc-700 px-3 py-2" open={Boolean(outcome.error) || all.some((x) => x === false)}>
                  <summary className="cursor-pointer text-sm font-mono">
                    {outcome.error ? '⚠' : all.every((x) => x !== false) ? '✔' : '⚠'} {d.name}
                  </summary>
                  {outcome.error && <p className="text-sm text-red-600 dark:text-red-400">{outcome.error}</p>}
                  {outcome.result && <ValidationReport validation={outcome.result} />}
                </details>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Step: where they were taken ── */}
      {stepKey === 'origin' && (
        <div>
          <StepHeading>Where were they taken?</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            The research project is the same for the whole session. Each deployment&rsquo;s location is picked in the next step, from the project&rsquo;s locations.
          </p>
          <ResearchProjectPicker value={projectId} onSelect={(picked) => { setProject(picked); setDrafts({}) }} />
          {originError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{originError}</p>}
        </div>
      )}

      {/* ── Step: each deployment's details ── */}
      {stepKey === 'details' && (
        <div>
          <StepHeading>Deployment details</StepHeading>
          <FormCard title="Which revision is this?" description="The same revision number names all the deployments of the session — R0003-DONA_01, R0003-DONA_02…">
            <div className="max-w-sm">
              <Field label="What revision number are you importing?" required type="number" min={1} max={9999} step={1} placeholder="e.g. 3" value={revision} onChange={(v) => { revisionTouched.current = true; setRevision(v); setRevisionFromLog(null); setRevisionSuggested(false) }}
                     hint={revisionFromLog && revisionValid ? `Taken from the deployment ids in ${revisionFromLog} — change it if it is not right.` : revisionSuggested && revisionValid ? 'Filled in as the next one expected for these locations — change it if it is not right.' : '1 for the first visit to these locations, 2 for the second, and so on.'}
                     error={revision.trim() !== '' && !revisionValid ? 'A whole number from 1 to 9999.' : undefined} />
            </div>
            {revisionValid && existingNames.length > 0 && (
              <p aria-live="polite" className="mt-3 text-sm text-amber-700 dark:text-amber-400">
                ⚠ Revision {revisionNumber} already has {existingNames.length} of these {chosen.length} deployment(s) in the collections folder:{' '}
                <span className="font-mono">{existingNames.slice(0, 5).map((d) => fieldsOf(d.name).deployment_id).join(', ')}{existingNames.length > 5 ? ', …' : ''}</span>.
                Importing them again would be refused — pick another revision, or leave them out.
              </p>
            )}
            {canFillFromPrevious && (
              <div className="mt-4 flex items-center gap-3 flex-wrap">
                <button type="button" className={btnOutline} disabled={filling} onClick={() => fillFromPrevious(fillable, 'all')}>
                  {filling ? 'Reading…' : 'Fill all from the previous revision'}
                </button>
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  As soon as the revision is known, each deployment is filled in with everything possible from the same one in the closest earlier
                  revision — revision 2 from revision 1 — except the dates. This does it again, replacing what you have typed in those fields.
                </span>
              </div>
            )}
            {fillMessage?.scope === 'all' && <p aria-live="polite" className="text-sm text-zinc-600 dark:text-zinc-400 mt-2">{fillMessage.text}</p>}
          </FormCard>

          {scan?.timestamp_log && (
            <p aria-live="polite" className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
              The start and end dates of {scan.timestamp_log.matched} of these {chosen.length} deployment(s) were taken from{' '}
              <span className="font-mono">{scan.timestamp_log.name}</span>, found in the session folder, not from the images' EXIF data.
            </p>
          )}
          {deduced.length > 0 && (
            <p aria-live="polite" className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">
              The location of {deduced.length} of these {chosen.length} deployment(s) was deduced from the name of their folder
              {deduced.some((d) => drafts[d.name]?.locationFrom === 'log') ? ' or the deployment id in the timestamp log' : ''}, as it is already registered
              in this research project. Check them, and pick another where it is not right.
            </p>
          )}
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <p className="text-sm text-zinc-600 dark:text-zinc-400" role="status">{completed} of {chosen.length} deployment(s) complete.</p>
            <input aria-label="Filter deployments" className={`${inputClass} max-w-[14rem]`} placeholder="Filter by name…" value={filter} onChange={(e) => setFilter(e.target.value)} />
            <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
              <input type="checkbox" checked={onlyIncomplete} onChange={(e) => setOnlyIncomplete(e.target.checked)} />
              Only the incomplete ones
            </label>
          </div>
          <div className="max-h-72 overflow-y-auto mb-5 border border-zinc-200 dark:border-zinc-700 rounded">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 dark:bg-zinc-800/50 text-xs text-zinc-500 dark:text-zinc-400 sticky top-0">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left">Subfolder</th>
                  <th scope="col" className="px-3 py-2 text-left">Location</th>
                  <th scope="col" className="px-3 py-2 text-left">Period</th>
                  <th scope="col" className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
                {visible.map((d) => {
                  const problems = problemsOf(d.name)
                  const fields = drafts[d.name]?.fields
                  return (
                    <tr key={d.name} className={d.name === activeName ? 'bg-blue-50 dark:bg-blue-950/30' : ''}>
                      <td className="px-3 py-1.5">
                        <button type="button" className="font-mono text-left underline-offset-2 hover:underline" aria-current={d.name === activeName ? 'true' : undefined} onClick={() => selectDeployment(d.name)}>{d.name}</button>
                      </td>
                      <td className="px-3 py-1.5 font-mono">{fields?.location_id ?? '—'}</td>
                      <td className="px-3 py-1.5 text-zinc-600 dark:text-zinc-400">{fields?.start_date.slice(0, 10) || '?'} → {fields?.end_date?.slice(0, 10) ?? '?'}</td>
                      <td className="px-3 py-1.5">{problems === 0
                        ? <span className="text-emerald-600 dark:text-emerald-400">✔ Complete</span>
                        : <span className="text-amber-600 dark:text-amber-400">⚠ {problems} to fix</span>}
                        {existingFolder(d.name) && <span className="ml-2 text-amber-600 dark:text-amber-400">⚠ Already exists</span>}</td>
                    </tr>
                  )
                })}
                {visible.length === 0 && <tr><td colSpan={4} className="px-3 py-3 text-zinc-500 dark:text-zinc-400">No deployment matches.</td></tr>}
              </tbody>
            </table>
          </div>

          {active && activeEntry && activeFields && (
            <div aria-label={`Details of ${active.name}`} role="group">
              <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                <h5 className="text-base font-semibold font-mono text-zinc-900 dark:text-zinc-100">{active.name} <span className="text-xs font-sans font-normal text-zinc-500 dark:text-zinc-400">— {activeIndex + 1} of {chosen.length}, {active.image_count} image(s)</span></h5>
                <div className="flex gap-2">
                  <button type="button" className={btnOutline} disabled={activeIndex <= 0} onClick={() => selectDeployment(chosen[activeIndex - 1].name)}>Previous</button>
                  <button type="button" className={btnOutline} disabled={activeIndex >= chosen.length - 1} onClick={() => selectDeployment(chosen[activeIndex + 1].name)}>Next</button>
                  <button type="button" className={btnOutline} disabled={!nextIncomplete} onClick={() => nextIncomplete && selectDeployment(nextIncomplete.name)}>Next incomplete</button>
                </div>
              </div>

              <FormCard title="Identification" description="The revision and the deployment's own location give its id.">
                {duplicated(active.name) && <p className="text-sm text-red-600 dark:text-red-400 mb-3">Another deployment of the session has this id — each needs its own location.</p>}
                {existingFolder(active.name) && (
                  <p role="alert" className="text-sm text-amber-700 dark:text-amber-400 mb-3">
                    ⚠ This deployment already exists: <span className="font-mono break-all">{existingFolder(active.name)}</span> has images in it, and
                    importing it again would be refused as it would mix them. Choose another location, or move that folder away.
                  </p>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <SelectField label="Location" value={activeFields.location_id ?? ''} onChange={(v) => pickLocation(active.name, v)}
                               options={localLocations.map((l) => ({ value: l.location_id, label: l.name ? `${l.location_id} — ${l.name}` : l.location_id }))} />
                  <Field label="Deployment id" readOnly placeholder="Filled in from the revision and the location" value={activeFields.deployment_id} onChange={() => {}} />
                </div>
                {activeEntry.locationFrom && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
                    Deduced from {activeEntry.locationFrom === 'folder' ? `the folder's name, ${active.name}` : `the deployment id in the timestamp log, ${active.log_deployment_id}`} — pick another if it is not the right one.
                  </p>
                )}
                {activeFields.location_id && (activeFields.latitude == null || activeFields.longitude == null) && (
                  <p className="text-sm text-red-600 dark:text-red-400 mt-2">This location has no coordinates, and a deployment needs them.</p>
                )}
                <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-3">
                  <LocationTimeNote locationId={activeFields.location_id} latitude={activeFields.latitude} longitude={activeFields.longitude}
                                    timezone={activeEntry.timezone} ignoreDst={activeEntry.ignoreDst ?? preSettings.ignore_dst} />
                </p>
                {!addingLocation && (
                  <button type="button" className={`${btnOutline} mt-3`} onClick={() => { setAddingLocation(true); setLocationDraft({ ...EMPTY_LOCATION_DRAFT, location_id: matchLocation(active.name, localLocations) ? '' : active.name }); setLocationError(null) }}>
                    Add a location
                  </button>
                )}
                {addingLocation && (
                  <div className="mt-4 p-4 rounded border border-zinc-200 dark:border-zinc-700">
                    <h6 className="text-sm font-semibold mb-3">New location</h6>
                    <div className="grid grid-cols-2 gap-4">
                      <Field label="Location id" required value={locationDraft.location_id} onChange={(v) => setLocationDraft((l) => ({ ...l, location_id: v }))} />
                      <Field label="Location name" value={locationDraft.name} onChange={(v) => setLocationDraft((l) => ({ ...l, name: v }))} />
                      <Field label="Location timezone" value={locationDraft.timezone} error={locationErrors.timezone} placeholder="Europe/Madrid" onChange={(v) => setLocationDraft((l) => ({ ...l, timezone: v }))} />
                      <label className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer mt-7">
                        <input type="checkbox" className="mt-1" checked={locationDraft.ignore_dst} onChange={(e) => setLocationDraft((l) => ({ ...l, ignore_dst: e.target.checked }))} />
                        The location’s cameras ignore summer time (DST)
                      </label>
                      <Field label="Location latitude" required type="number" step="any" value={locationDraft.latitude} error={shown(locationErrors.latitude)} onChange={(v) => setLocationDraft((l) => ({ ...l, latitude: v }))} />
                      <Field label="Location longitude" required type="number" step="any" value={locationDraft.longitude} error={shown(locationErrors.longitude)} onChange={(v) => setLocationDraft((l) => ({ ...l, longitude: v }))} />
                    </div>
                    {locationError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{locationError}</p>}
                    <div className="flex gap-2 mt-4">
                      <button type="button" className={btnPrimary} disabled={!canSaveLocation} onClick={handleSaveLocation}>Save location</button>
                      <button type="button" className={btnOutline} onClick={() => setAddingLocation(false)}>Cancel</button>
                    </div>
                  </div>
                )}
              </FormCard>

              {(hasEarlierRevision(active.name) || fillMessage?.scope === 'one') && (
                <div className="mb-4 flex items-center gap-3 flex-wrap">
                  {hasEarlierRevision(active.name) && (
                    <button type="button" className={btnOutline} disabled={filling} onClick={() => fillFromPrevious([active.name], 'one')}>
                      Fill from the previous revision
                    </button>
                  )}
                  {fillMessage?.scope === 'one' && <span aria-live="polite" className="text-xs text-zinc-500 dark:text-zinc-400">{fillMessage.text}</span>}
                </div>
              )}

              <DeploymentFormBody deployment={activeFields} timezone={activeEntry.timezone} errors={activeErrors} showAll={activeEntry.showAll}
                                  onShowAllChange={(v) => updateEntry(active.name, (e) => ({ ...e, showAll: v }))}
                                  onField={(key, value) => updateField(active.name, key, value)}
                                  datesGuessed={Boolean(active.start_date) && !active.from_timestamp_log}
                                  datesFromLog={active.from_timestamp_log ? scan?.timestamp_log?.name : undefined} />

            </div>
          )}
          {detailsError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{detailsError}</p>}
        </div>
      )}

      {/* ── Step: postvalidation ── */}
      {stepKey === 'checks' && (
        <div>
          <StepHeading>Postvalidation</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Now that each deployment is known, the same checks of its names, dates and statistics over all {chosen.length} of them — pick which to run,
            and which must pass in all of them before moving on.
          </p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">
            Some of these checks can be customized in the settings (Settings › Postvalidation): the tolerance of the image dates, and what the
            comparison with the previous revisions means — the length of a sequence, the way of comparing and how much counts as similar.
          </p>
          {shownDeploymentChecks.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">Every postvalidation check is turned off in the settings, so there is nothing to run here — go on.</p>
          ) : (
            <CheckTable options={shownDeploymentChecks} enabled={deploymentChecks} required={requiredDeploymentChecks}
                        onToggleEnabled={(c) => setDeploymentChecks((prev) => {
                          const next = toggled(prev, c)
                          if (!next.has(c)) setRequiredDeploymentChecks((r) => (r.has(c) ? toggled(r, c) : r))
                          return next
                        })}
                        onToggleRequired={(c) => setRequiredDeploymentChecks((s) => toggled(s, c))}
                        onSetEnabled={setDeploymentChecks} onSetRequired={setRequiredDeploymentChecks} />
          )}
          {shownDeploymentChecks.length > 0 && (
            <button type="button" className={`${btnOutline} flex items-center gap-2`}
                    disabled={checking || runnableDeploymentChecks.length === 0} onClick={handleCheck}>
              {checking && <SmallSpinner />}{checking ? 'Checking…' : 'Run checks'}
            </button>
          )}
          <div className="mt-4 space-y-2">
            {chosen.filter((d) => checks[d.name]).map((d) => {
              const outcome = checks[d.name]
              const bad = Boolean(outcome.error) || runnableDeploymentChecks.some((c) => deploymentCheckPassed(c, outcome.result ?? null) === false)
              return (
                <details key={d.name} className="rounded border border-zinc-200 dark:border-zinc-700 px-3 py-2" open={bad}>
                  <summary className="cursor-pointer text-sm font-mono">{bad ? '⚠' : '✔'} {fieldsOf(d.name).deployment_id}</summary>
                  {outcome.error && <p className="text-sm text-red-600 dark:text-red-400">{outcome.error}</p>}
                  {outcome.result && <DeploymentCheckReport result={outcome.result} toleranceHours={toleranceHours} />}
                </details>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Step: preprocessing ── */}
      {stepKey === 'preprocessing' && (
        <div>
          <StepHeading>Preprocessing</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            What will be done to the images of every deployment as they are imported. The originals are never touched.
            Each optional step can be switched off for this run; its values come from Settings › Preprocessing.
          </p>
          <ol className="space-y-3 mb-2">
            <PreprocessItem title="Copy into the collection" always>
              Each deployment&rsquo;s images are copied into its own folder in the revision&rsquo;s collection. Anything that isn&rsquo;t an image is copied as it is.
            </PreprocessItem>
            <PreprocessItem title="Read the capture dates" always>
              From each image&rsquo;s EXIF, as the camera&rsquo;s local time in its location&rsquo;s timezone, ignoring summer time where the location says so
              {preSettings.convert_to_utc ? ', converted to UTC' : ''}.
            </PreprocessItem>
            <PreprocessItem title="Rename the images" checked={effectiveSteps.has('rename')} onToggle={() => { preprocessTouched.current = true; setPreprocessSteps((s) => toggled(s, 'rename')) }}>
              <span className="font-mono">{'<deployment>__<YYYYMMDD>_<n>.<EXT>'}</span> in upper case.
            </PreprocessItem>
            <PreprocessItem title="Resize the images" checked={effectiveSteps.has('resize')} onToggle={() => { preprocessTouched.current = true; setPreprocessSteps((s) => toggled(s, 'resize')) }}>
              Images wider than <strong>{preSettings.resize_width} px</strong> are resized to that width, keeping their proportions.
            </PreprocessItem>
            <PreprocessItem title="Add metadata" checked={effectiveSteps.has('metadata')} onToggle={() => { preprocessTouched.current = true; setPreprocessSteps((s) => toggled(s, 'metadata')) }}
                            disabledReason={exiftool === false ? 'ExifTool is not installed, and writing the metadata needs it.' : undefined}>
              Authorship, rights and license, written into each image as XMP — owner <span className="font-mono">{preSettings.owner || 'Unknown'}</span>,
              publisher <span className="font-mono">{preSettings.publisher || 'Unknown'}</span>.
            </PreprocessItem>
          </ol>
        </div>
      )}

      {/* ── Step: import ── */}
      {stepKey === 'import' && (
        <div>
          <StepHeading>Import</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Everything is ready — organize the images of the {chosen.length} deployment(s) into revision R{String(revisionNumber).padStart(4, '0')}&rsquo;s collection of{' '}
            <span className="font-mono">{projectId}</span>, {describePreprocessing(effectiveSteps)}.
          </p>
          <ul className="space-y-2 mb-4">
            {chosen.map((d) => {
              const run = runs[d.name]
              const id = fieldsOf(d.name).deployment_id
              return (
                <li key={d.name} className="rounded border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-sm" aria-label={`Import of ${id}`}>
                  <span className="font-mono">{id}</span>{' '}
                  {!run && <span className="text-zinc-500 dark:text-zinc-400">— waiting</span>}
                  {run && !run.done && !run.error && <span className="text-zinc-500 dark:text-zinc-400">— importing…
                    {(() => { const last = [...run.events].reverse().find((e) => e.type === 'copy'); return last && last.type === 'copy' ? ` ${last.index}/${last.total}` : '' })()}</span>}
                  {run?.done && <span className="text-emerald-600 dark:text-emerald-400">✔ imported — <span className="font-mono">{run.destDir}</span></span>}
                  {run?.error && !run.done && <span className="text-red-600 dark:text-red-400">⚠ {run.error}</span>}
                  {run?.events.filter((e) => e.type === 'skipped').map((e, i) => (
                    <p key={i} className="text-xs text-amber-600 dark:text-amber-400">⚠ Skipped {e.type === 'skipped' ? `${e.name}: ${e.detail}` : ''}</p>
                  ))}
                </li>
              )
            })}
          </ul>
          {!allDone && (
            <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={importing || pending.length === 0} onClick={handleImport}>
              {importing && <SmallSpinner />}
              {importing ? 'Importing…' : failures > 0 ? `Import the ${pending.length} left` : `Import ${pending.length} deployment${pending.length === 1 ? '' : 's'}`}
            </button>
          )}
          {allDone && (
            <div className="flex items-center gap-3 flex-wrap">
              <p className="text-sm text-emerald-600 dark:text-emerald-400">✔ Session imported — {chosen.length} deployment(s).</p>
              {collectionPath && <button type="button" className={btnOutline} onClick={handleOpenFolder}>Open folder in file explorer</button>}
              {onUpload && projectId && revisionValid && (
                <button type="button" className={btnPrimary} onClick={() => onUpload({ researchProjectId: projectId, collection: `R${String(revisionNumber).padStart(4, '0')}` })}>
                  Upload to Trapper
                </button>
              )}
              {openFolderError && <p className="text-sm text-red-600 dark:text-red-400">{openFolderError}</p>}
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between items-start mt-10">
        {step > 0 && !importing ? (
          <button type="button" className={btnOutline} onClick={() => setStep((s) => s - 1)} disabled={allDone}>Back</button>
        ) : <div />}
        {stepKey !== 'import' && (
          <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={!canContinue[stepKey]}
                  onClick={stepKey === 'details' ? handleContinueFromDetails : () => setStep((s) => s + 1)}>
            {savingDetails && <SmallSpinner />}Continue
          </button>
        )}
      </div>
    </div>
  )
}

function coordinateError(text: string, limit: number): string | undefined {
  if (text.trim() === '') return 'Required'
  const n = Number(text)
  return Number.isFinite(n) && Math.abs(n) <= limit ? undefined : `Must be between ${-limit} and ${limit}.`
}

/** An error worth showing beside a field — everything but "left empty". */
function shown(message?: string): string | undefined {
  return message && message !== 'Required' ? message : undefined
}
