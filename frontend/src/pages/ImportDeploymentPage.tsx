import ReportPanel from '../components/ReportPanel'
import TrapperAccountNotice, { trapperAccountReady } from '../components/TrapperAccountNotice'
import type { TrapperAccount } from '../components/TrapperAccountNotice'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { TrapperCredentials } from '../api'
import CheckboxList from '../components/CheckboxList'
import Combobox from '../components/Combobox'
import OptionCards from '../components/OptionCards'
import type { Option } from '../components/OptionCards'
import { EMPTY_DEPLOYMENT_FIELDS, EMPTY_RESEARCH_PROJECT } from '../types'
import { RESEARCH_PROJECT_LIMITS, shownProjectErrors, validateResearchProject } from '../researchProjectValidation'
import { isValidTimezone, knownTimezones, shownErrors, stampTimezone, validateDeployment } from '../deploymentValidation'
import type {
  AppSettings, CameraGroup, CollectionPath, PreprocessingOptions, SimilarityMethod, StatisticCheck, StatisticsParams, TimestampLogResult, ExifField, DeploymentCheck, DeploymentCheckResult, DeploymentFields,
  FeatureType, ImageCheck, ImportEvent, Location, LocalLocation, LocalResearchProject, PreviousDeployment, ResearchProject, ScanResult,
  SessionSummary, UploadTarget, ValidationResult,
} from '../types'

export const inputClass = 'w-full px-3 py-2 text-sm rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono'
export const labelClass = 'block text-sm font-semibold mb-1.5 text-zinc-700 dark:text-zinc-300'
export const hintClass = 'text-xs text-zinc-500 dark:text-zinc-400 mt-1'
export const btnPrimary = 'px-4 py-2 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
export const btnOutline = 'px-4 py-2 text-sm border border-zinc-300 dark:border-zinc-600 text-zinc-700 dark:text-zinc-300 rounded hover:bg-zinc-100 dark:hover:bg-zinc-700 transition-colors disabled:opacity-50'

export function SmallSpinner() {
  return <div className="w-4 h-4 border border-zinc-500 border-t-zinc-200 rounded-full animate-spin" />
}

export function StepHeading({ children }: { children: ReactNode }) {
  return <h4 className="text-lg font-semibold mb-1 text-zinc-900 dark:text-zinc-100">{children}</h4>
}

type ConnStatus = 'idle' | 'testing' | 'ok' | 'error'

function fieldId(label: string) {
  return `field-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
}

function FieldLabel({ id, label, required }: { id: string; label: string; required?: boolean }) {
  return (
    <div className="flex items-baseline justify-between mb-1.5">
      <label className="text-sm font-semibold text-zinc-700 dark:text-zinc-300" htmlFor={id}>{label}</label>
      {required && <span className="text-[11px] uppercase tracking-wide text-blue-600 dark:text-blue-400">Required</span>}
    </div>
  )
}

/** A single optional text/number field in the deployment details grid. */
export function Field({ label, value, onChange, type = 'text', min, max, step, hint, required, placeholder, error, list, maxLength, readOnly }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; min?: number; max?: number; step?: number | string
  hint?: string; required?: boolean; placeholder?: string; error?: string; list?: string; maxLength?: number; readOnly?: boolean
}) {
  const id = fieldId(label)
  return (
    <div>
      <FieldLabel id={id} label={label} required={required} />
      <input id={id} className={`${inputClass} ${error ? 'border-red-500 dark:border-red-500' : ''} ${readOnly ? 'bg-zinc-100 dark:bg-zinc-900 cursor-default' : ''}`} type={type} min={min} max={max} step={step} value={value}
             placeholder={placeholder} list={list} maxLength={maxLength} readOnly={readOnly} aria-invalid={error ? true : undefined} onChange={(e) => onChange(e.target.value)} />
      {error && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>}
      {hint && <p className={hintClass}>{hint}</p>}
    </div>
  )
}

/** A date-and-time field with the browser's own calendar picker. Values
 * travel as ISO local timestamps ("2024-09-04T13:10:00"), the format the
 * scan and the API already use. */
export function DateTimeField({ label, value, onChange, hint, required, error }: {
  label: string; value: string; onChange: (v: string) => void; hint?: string; required?: boolean; error?: string
}) {
  const id = fieldId(label)
  const shown = value.slice(0, 19) // a timezone suffix would make the input reject it
  return (
    <div>
      <FieldLabel id={id} label={label} required={required} />
      <input id={id} type="datetime-local" step={1} className={`${inputClass} [color-scheme:light] dark:[color-scheme:dark]`}
             aria-invalid={error ? true : undefined}
             value={shown} onChange={(e) => onChange(e.target.value.length === 16 ? `${e.target.value}:00` : e.target.value)} />
      {error && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>}
      {value.length > 19 && <p className="text-xs font-mono text-zinc-500 dark:text-zinc-400 mt-1">Saved as {value}</p>}
      {hint && <p className={hintClass}>{hint}</p>}
    </div>
  )
}

/** A titled group of related fields. */
export function FormCard({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="mb-5 p-5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50/60 dark:bg-zinc-800/40">
      <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h5>
      {description && <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

/** A dropdown field restricted to a fixed set of options, with a blank
 * "not set" choice. */
export function SelectField({ label, value, onChange, options, hint, allowEmpty = true }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; hint?: string; allowEmpty?: boolean
}) {
  const id = fieldId(label)
  return (
    <div>
      <FieldLabel id={id} label={label} />
      <select id={id} className={inputClass} value={value} onChange={(e) => onChange(e.target.value)}>
        {allowEmpty && <option value="">—</option>}
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {hint && <p className={hintClass}>{hint}</p>}
    </div>
  )
}

/** A single yes/no field — unchecked means "not recorded", not "no". */
function CheckboxField({ label, checked, onChange, hint }: { label: string; checked: boolean; onChange: (v: boolean) => void; hint?: string }) {
  return (
    <div>
      <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        {label}
      </label>
      {hint && <p className={`${hintClass} ml-6`}>{hint}</p>}
    </div>
  )
}

/** Each field's description, as worded by Camtrap DP's own
 * deployments-table-schema.json. */
const DESCRIPTIONS = {
  deploymentID: 'Unique identifier of the deployment.',
  locationID: 'Identifier of the deployment location.',
  locationName: 'Name given to the deployment location.',
  latitude: 'Latitude of the deployment location in decimal degrees, using the WGS84 datum.',
  longitude: 'Longitude of the deployment location in decimal degrees, using the WGS84 datum.',
  coordinateUncertainty: 'Horizontal distance from the given latitude and longitude describing the smallest circle containing the deployment location. Expressed in meters. Especially relevant when coordinates are rounded to protect sensitive species.',
  deploymentStart: 'Date and time at which the deployment was started. Formatted as an ISO 8601 string with timezone designator (YYYY-MM-DDThh:mm:ssZ or YYYY-MM-DDThh:mm:ss±hh:mm).',
  deploymentEnd: 'Date and time at which the deployment was ended. Formatted as an ISO 8601 string with timezone designator (YYYY-MM-DDThh:mm:ssZ or YYYY-MM-DDThh:mm:ss±hh:mm).',
  timezone: "IANA timezone the camera's clock was set to (e.g. Europe/Madrid). It gives both dates their timezone designator.",
  setupBy: 'Name or identifier of the person or organization that deployed the camera.',
  cameraID: 'Identifier of the camera used for the deployment (e.g. the camera device serial number).',
  cameraModel: 'Manufacturer and model of the camera. Formatted as manufacturer-model.',
  cameraDelay: 'Predefined duration after detection when further activity is ignored. Expressed in seconds.',
  cameraHeight: 'Height at which the camera was deployed. Expressed in meters. Not to be combined with camera depth.',
  cameraDepth: 'Depth at which the camera was deployed. Expressed in meters. Not to be combined with camera height.',
  cameraTilt: 'Angle at which the camera was deployed in the vertical plane. Expressed in degrees, with -90 facing down, 0 horizontal and 90 facing up.',
  cameraHeading: 'Angle at which the camera was deployed in the horizontal plane. Expressed in decimal degrees clockwise from north, with values ranging from 0 to 360: 0 = north, 90 = east, 180 = south, 270 = west.',
  detectionDistance: 'Maximum distance at which the camera can reliably detect activity. Expressed in meters. Typically measured by having a human move in front of the camera.',
  timestampIssues: 'True if timestamps in the media resource for the deployment are known to have (unsolvable) issues (e.g. unknown timezone, am/pm switch).',
  baitUse: 'True if bait was used for the deployment. More information can be provided in tags or comments.',
  featureType: 'Type of the feature (if any) associated with the deployment.',
  habitat: 'Short characterization of the habitat at the deployment location.',
  deploymentGroups: 'Deployment group(s) associated with the deployment. Deployment groups can have a spatial (arrays, grids, clusters), temporal (sessions, seasons, months, years) or other context. Formatted as a pipe (|) separated list for multiple values, with values preferably formatted as key:value pairs.',
  deploymentTags: 'Tag(s) associated with the deployment. Formatted as a comma separated list for multiple values, with values optionally formatted as key:value pairs.',
  deploymentComments: 'Comments or notes about the deployment.',
} as const

/** A multi-line field. */
export function TextAreaField({ label, value, onChange, maxLength, error, hint }: {
  label: string; value: string; onChange: (v: string) => void; maxLength?: number; error?: string; hint?: string
}) {
  const id = fieldId(label)
  return (
    <div>
      <FieldLabel id={id} label={label} />
      <textarea id={id} rows={4} maxLength={maxLength} value={value} aria-invalid={error ? true : undefined}
                className={`${inputClass} ${error ? 'border-red-500 dark:border-red-500' : ''}`} onChange={(e) => onChange(e.target.value)} />
      {error && <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>}
      {(hint || maxLength) && <p className={hintClass}>{hint}{hint && maxLength ? ' ' : ''}{maxLength ? `${value.length}/${maxLength}` : ''}</p>}
    </div>
  )
}

// The choices of Trapper's own "Add research project" form, keyed by its option numbers.
export const SAMPLING_DESIGN_OPTIONS = ['simpleRandom', 'systematicRandom', 'clusteredRandom', 'experimental', 'targeted', 'opportunistic']
  .map((label, i) => ({ value: String(i + 1), label }))
export const SENSOR_METHOD_OPTIONS = ['activityDetection', 'timeLapse', 'both'].map((label, i) => ({ value: String(i + 1), label }))
export const ANIMAL_TYPES_OPTIONS = ['unmarked', 'marked', 'both'].map((label, i) => ({ value: String(i + 1), label }))
export const BAIT_USE_OPTIONS = ['none', 'scent', 'food', 'visual', 'acoustic', 'other'].map((label, i) => ({ value: String(i + 1), label }))

/** One thing the preprocessing does — optional (a box to tick) or always done. */
export function PreprocessItem({ title, always, checked, onToggle, disabledReason, children }: {
  title: string; always?: boolean; checked?: boolean; onToggle?: () => void; disabledReason?: string; children: ReactNode
}) {
  return (
    <li className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-700">
      <div className="flex items-center gap-2 mb-1">
        {always ? (
          <span className="text-xs uppercase tracking-wide px-1.5 py-0.5 rounded bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300">Always</span>
        ) : (
          <input type="checkbox" aria-label={title} checked={Boolean(checked) && !disabledReason} disabled={Boolean(disabledReason)} onChange={onToggle} />
        )}
        <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{title}</h5>
      </div>
      <div className="text-sm text-zinc-600 dark:text-zinc-400">{children}</div>
      {disabledReason && <p className="text-xs text-red-600 dark:text-red-400 mt-2">{disabledReason}</p>}
    </li>
  )
}

/** "renaming, resizing and adding metadata", for the import step's sentence. */
export function describePreprocessing(steps: Set<PreprocessStep>): string {
  const names = [steps.has('rename') && 'renaming', steps.has('resize') && 'resizing', steps.has('metadata') && 'adding metadata to'].filter(Boolean) as string[]
  if (names.length === 0) return 'as they are'
  return `${names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}` : names[0]} them`
}

/** The opt-in checks as a table: one row per check, with whether to run it
 * and whether it must pass to move past this step. "Required" is only
 * meaningful — and only enabled — alongside "run". */
export function CheckTable<T extends string>({ options, enabled, required, onToggleEnabled, onToggleRequired, onSetEnabled, onSetRequired }: {
  options: { value: T; label: string }[]; enabled: Set<T>; required: Set<T>
  onToggleEnabled: (value: T) => void; onToggleRequired: (value: T) => void
  /** The whole new set of checks to run / that must pass — what the "all" boxes in the header ask for. */
  onSetEnabled: (next: Set<T>) => void; onSetRequired: (next: Set<T>) => void
}) {
  const th = 'px-3 py-2 text-xs font-medium text-zinc-500 dark:text-zinc-400'
  const values = options.map((o) => o.value)
  const runValues = values.filter((v) => enabled.has(v))
  const allRun = runValues.length === values.length
  const someRun = runValues.length > 0
  // "Required" only means something for a check that runs, so the "all" box speaks for those.
  const allRequired = runValues.length > 0 && runValues.every((v) => required.has(v))
  const someRequired = runValues.some((v) => required.has(v))
  const without = (set: Set<T>) => new Set([...set].filter((v) => !values.includes(v)))
  const indeterminate = (partial: boolean) => (el: HTMLInputElement | null) => { if (el) el.indeterminate = partial }
  return (
    <table className="w-full text-sm mb-4 border border-zinc-200 dark:border-zinc-700 rounded">
      <thead className="bg-zinc-50 dark:bg-zinc-800/50">
        <tr>
          <th scope="col" className={`${th} text-left`}>Check</th>
          <th scope="col" className={`${th} text-center`}>
            <span className="inline-flex items-center gap-2">
              <input type="checkbox" aria-label="Run all checks" checked={allRun} ref={indeterminate(someRun && !allRun)}
                     onChange={() => {
                       if (allRun) { onSetEnabled(without(enabled)); onSetRequired(without(required)) } else onSetEnabled(new Set([...enabled, ...values]))
                     }} />
              Run
            </span>
          </th>
          <th scope="col" className={`${th} text-center`}>
            <span className="inline-flex items-center gap-2">
              <input type="checkbox" aria-label="Require all checks" checked={allRequired} disabled={!someRun} ref={indeterminate(someRequired && !allRequired)}
                     onChange={() => onSetRequired(allRequired ? without(required) : new Set([...required, ...runValues]))} />
              Required to continue
            </span>
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-zinc-200 dark:divide-zinc-700">
        {options.map((opt) => (
          <tr key={opt.value}>
            <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{opt.label}</td>
            <td className="px-3 py-2 text-center">
              <input type="checkbox" aria-label={opt.label} checked={enabled.has(opt.value)} onChange={() => onToggleEnabled(opt.value)} />
            </td>
            <td className="px-3 py-2 text-center">
              <input type="checkbox" aria-label="Required to continue" checked={required.has(opt.value)}
                     disabled={!enabled.has(opt.value)} onChange={() => onToggleRequired(opt.value)} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function toggled<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set)
  if (next.has(value)) next.delete(value); else next.add(value)
  return next
}

/** What's wrong with a typed number that must lie in a range ('' is only "missing" when required). */
function rangeError(text: string, min: number, max: number, required: boolean): string | undefined {
  if (text.trim() === '') return required ? 'Required' : undefined
  const n = Number(text)
  return Number.isFinite(n) && n >= min && n <= max ? undefined : `Must be between ${min} and ${max}.`
}

export type OriginSource = 'trapper' | 'manual'

// A new location's form, its numbers as typed.
const EMPTY_LOCATION_DRAFT = { location_id: '', name: '', timezone: '', ignore_dst: true, latitude: '', longitude: '', coordinate_uncertainty: '' }

export const ORIGIN_SOURCE_OPTIONS: Option<OriginSource>[] = [
  { value: 'trapper', emoji: '🪤', title: 'From Trapper', description: 'Connect to Trapper and pick one — its fields fill in the form.', available: true },
  { value: 'manual', emoji: '✍️', title: 'By hand', description: 'Fill in the form yourself.', available: true },
]

export const IMAGE_CHECK_OPTIONS: { value: ImageCheck; label: string }[] = [
  { value: 'corrupted', label: 'Corrupted images' },
  { value: 'sequence', label: 'Shooting order vs. filename sequence' },
  { value: 'structure', label: 'Folder structure (subdirectories)' },
  { value: 'camera', label: 'Same camera (model and id) on every image' },
  { value: 'exif', label: 'Required EXIF fields (capture date, camera model and id)' },
  { value: 'duplicates', label: 'Duplicate images (same content)' },
]

export const DEPLOYMENT_CHECK_OPTIONS: { value: DeploymentCheck; label: string }[] = [
  { value: 'deployment_id', label: 'Deployment id format (R0033-DONA_01)' },
  { value: 'collection_prefix', label: 'Deployment id starts with its collection' },
  { value: 'collection_name', label: 'Collection name (R0033)' },
  { value: 'location', label: "Deployment id's location is the one chosen" },
  { value: 'time_range', label: 'Image dates fit the deployment (first at the start, last at the end)' },
  { value: 'camera', label: 'Camera consistency' },
  { value: 'image_count', label: 'Number of images is like the previous revisions' },
  { value: 'sequence_count', label: 'Number of sequences is like the previous revisions' },
  { value: 'sequence_length', label: 'Length of the sequences is like the previous revisions' },
]

export const STATISTIC_CHECKS: StatisticCheck[] = ['image_count', 'sequence_count', 'sequence_length']

export const SIMILARITY_METHODS: { value: SimilarityMethod; label: string }[] = [
  { value: 'median', label: 'The median of the previous revisions' },
  { value: 'mean', label: 'The mean of the previous revisions' },
  { value: 'last', label: 'The last previous revision' },
  { value: 'range', label: 'The range the previous revisions span' },
]

export const ALL_DEPLOYMENT_CHECKS: DeploymentCheck[] = DEPLOYMENT_CHECK_OPTIONS.map((o) => o.value)

export const RANGE_RULE_LABELS = {
  first: 'the first image should be at the start',
  last: 'the last image should be at the end',
  between: 'it should be within the deployment',
} as const

/** The postvalidation's own leeway, in hours, around the deployment's start and end. */
export const DEFAULT_TOLERANCE_HOURS = 1

/** Every check shown, as before anything is configured (or when the settings can't be read). */
export type WizardSettings = Pick<AppSettings, 'VALIDATION' | 'POSTVALIDATION' | 'PREPROCESSING'>

export const DEFAULT_CHECK_SETTINGS: WizardSettings = {
  VALIDATION: { corrupted: true, sequence: true, structure: true, camera: true, exif: true, duplicates: true },
  POSTVALIDATION: {
    deployment_id: true, collection_prefix: true, collection_name: true, location: true, time_range: true, camera: true,
    image_count: true, sequence_count: true, sequence_length: true, tolerance_hours: DEFAULT_TOLERANCE_HOURS,
    sequence_gap_seconds: 60, min_revisions: 2, similarity_method: 'median',
    image_count_tolerance: 50, sequence_count_tolerance: 50, sequence_length_tolerance: 50,
  },
  PREPROCESSING: {
    rename: true, resize: true, resize_width: 2400, metadata: true, owner: '', publisher: '', coverage: '',
    license_url: 'https://creativecommons.org/licenses/by-nc/4.0/', ignore_dst: true, convert_to_utc: true,
  },
}

export type PreprocessStep = 'rename' | 'resize' | 'metadata'

/** The statistical parameters as typed (strings), from the settings. */
export function statParamsOf(post: AppSettings['POSTVALIDATION']) {
  return {
    gap: String(post.sequence_gap_seconds), minRevisions: String(post.min_revisions), method: post.similarity_method,
    imageTol: String(post.image_count_tolerance), seqCountTol: String(post.sequence_count_tolerance), seqLenTol: String(post.sequence_length_tolerance),
  }
}

/** The numbers the typed statistical parameters mean, or null where one isn't valid. */
export function statParamsValid(p: ReturnType<typeof statParamsOf>): StatisticsParams | null {
  const number = (text: string) => (text.trim() !== '' && Number.isFinite(Number(text)) ? Number(text) : NaN)
  const gap = number(p.gap), minRevisions = number(p.minRevisions)
  const tolerances = [p.imageTol, p.seqCountTol, p.seqLenTol].map(number)
  if (!(gap > 0 && gap <= 86400) || !Number.isInteger(minRevisions) || minRevisions < 1 || minRevisions > 50) return null
  if (tolerances.some((t) => !(t >= 0 && t <= 1000))) return null
  return {
    sequence_gap_seconds: gap, min_revisions: minRevisions, method: p.method,
    image_count_tolerance: tolerances[0], sequence_count_tolerance: tolerances[1], sequence_length_tolerance: tolerances[2],
  }
}

// Camtrap DP's own "featureType" enum — deployments-table-schema.json.
const FEATURE_TYPE_OPTIONS: { value: FeatureType; label: string }[] = [
  { value: 'roadPaved', label: 'Road (paved)' },
  { value: 'roadDirt', label: 'Road (dirt)' },
  { value: 'trailHiking', label: 'Trail (hiking)' },
  { value: 'trailGame', label: 'Trail (game)' },
  { value: 'roadUnderpass', label: 'Road underpass' },
  { value: 'roadOverpass', label: 'Road overpass' },
  { value: 'roadBridge', label: 'Road bridge' },
  { value: 'culvert', label: 'Culvert' },
  { value: 'burrow', label: 'Burrow' },
  { value: 'nestSite', label: 'Nest site' },
  { value: 'carcass', label: 'Carcass' },
  { value: 'waterSource', label: 'Water source' },
  { value: 'fruitingTree', label: 'Fruiting tree' },
]

// ── Step model ───────────────────────────────────────────────────────────────
// The wizard's screens, in order: the folder of images, what can be checked of
// it without knowing the deployment, where it was taken, the deployment's own
// details, what can be checked once they are known, the list of what is done to
// the images, and the import into the local collections folder.

type StepKey = 'folder' | 'validate' | 'origin' | 'deployment' | 'checks' | 'preprocessing' | 'import'

interface StepDescriptor { key: StepKey; label: string }

const STEPS: StepDescriptor[] = [
  { key: 'folder', label: 'Folder' },
  { key: 'validate', label: 'Validate' },
  { key: 'origin', label: 'Origin' },
  { key: 'deployment', label: 'Details' },
  { key: 'checks', label: 'Postvalidation' },
  { key: 'preprocessing', label: 'Preprocessing' },
  { key: 'import', label: 'Import' },
]

/** The naming wildintel-tools expects: R + the revision as four digits, a
 * hyphen and the location id — "R0003-DONA_01". Empty until both are known. */
export function revisionOf(deploymentId: string): string {
  const match = /^R(\d{4})-/.exec(deploymentId)
  return match ? String(Number(match[1])) : ''
}

export function buildDeploymentId(revision: string, locationId: string | null | undefined): string {
  const n = Number(revision)
  if (!revision.trim() || !Number.isInteger(n) || n < 1 || n > 9999 || !locationId?.trim()) return ''
  return `R${String(n).padStart(4, '0')}-${locationId.trim()}`
}

export const EXIF_FIELD_LABELS: Record<ExifField, string> = { date: 'a capture date', camera_model: 'a camera model', camera_id: 'a camera id' }

/** "Reconyx HC600 · id P800HG08", whichever of the two is known. */
export function describeCamera(camera: CameraGroup): string {
  return [camera.model ?? 'unknown model', camera.camera_id ? `id ${camera.camera_id}` : 'no id'].join(' · ')
}

export function imageCheckPassed(check: ImageCheck, result: ValidationResult | null): boolean | null {
  if (!result) return null
  if (check === 'corrupted') return result.corrupted !== undefined ? result.corrupted.length === 0 : null
  if (check === 'sequence') return result.sequence_issues !== undefined ? result.sequence_issues.length === 0 : null
  if (check === 'exif') return result.exif_missing !== undefined ? Object.values(result.exif_missing).every((m) => m.count === 0) : null
  if (check === 'duplicates') return result.duplicates !== undefined ? result.duplicates.length === 0 : null
  if (check === 'camera') return result.cameras !== undefined ? result.cameras.length === 1 && (result.cameras_without_info ?? 0) === 0 : null
  return result.subdirectories !== undefined ? result.subdirectories.length === 0 : null
}

export function deploymentCheckPassed(check: DeploymentCheck, result: DeploymentCheckResult | null): boolean | null {
  if (!result) return null
  if (check === 'time_range') return result.out_of_range !== undefined ? result.out_of_range.length === 0 : null
  if (check !== 'camera') return result[check] !== undefined ? result[check]!.ok : null  // the naming and the statistical checks all say {ok}
  if (result.camera_mismatches === undefined) return null
  return result.camera_mismatches.length === 0 && (result.camera_models_found?.length ?? 0) <= 1
}

/** Where the deployment was taken, and the timezone and summer-time setting it is read in. They are the location's — kept with it,
 * never asked for a deployment: every deployment there is read in them, and Trapper only accepts a package that declares the same ones. */
export function LocationTimeNote({ locationId, latitude, longitude, timezone, ignoreDst }: {
  locationId: string | null | undefined; latitude?: number | null; longitude?: number | null; timezone: string; ignoreDst: boolean
}) {
  if (!locationId) return null
  if (!timezone) {
    return <span className="block text-red-600 dark:text-red-400">The location <strong>{locationId}</strong> has no timezone, and a deployment needs it: add it to the location.</span>
  }
  return (
    <>
      You are entering the details of a deployment taken at location <strong>{locationId}</strong>
      {latitude != null && longitude != null && <> (GPS <strong>{latitude}, {longitude}</strong>)</>}
      , in the timezone <strong>{timezone}</strong>, which <strong>{ignoreDst ? 'ignores' : 'does not ignore'}</strong> summer time.{' '}
    </>
  )
}

/** The deployment's period, and — behind a tick — its camera, site and notes: Camtrap DP's own fields. */
export function DeploymentFormBody({ deployment, timezone, errors, showAll, onShowAllChange, onField, datesGuessed, datesFromLog }: {
  deployment: DeploymentFields; timezone: string; errors: ReturnType<typeof shownErrors>
  showAll: boolean; onShowAllChange: (v: boolean) => void
  onField: <K extends keyof DeploymentFields>(key: K, value: DeploymentFields[K]) => void
  datesGuessed: boolean
  /** The FileTimestampLog the dates were read from, if they were. */
  datesFromLog?: string
}) {
  return (
    <>
    <FormCard title="Period" description="When the camera was recording. Pick a date from the calendar or type it.">
      <div className="grid grid-cols-2 gap-4">
        <DateTimeField label="Start date" required hint={DESCRIPTIONS.deploymentStart} error={errors.start_date}
                       value={deployment.start_date} onChange={(v) => onField('start_date', stampTimezone(v, timezone))} />
        <DateTimeField label="End date" required hint={DESCRIPTIONS.deploymentEnd} error={errors.end_date}
                       value={deployment.end_date ?? ''} onChange={(v) => onField('end_date', v ? stampTimezone(v, timezone) : null)} />
      </div>
      {datesGuessed && <p className={hintClass}>The dates were guessed from the images' EXIF data.</p>}
      {datesFromLog && <p className={hintClass}>The dates were taken from {datesFromLog}, not from the images' EXIF data.</p>}
    </FormCard>

    <label className="flex items-center gap-2 text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-4 cursor-pointer">
      <input type="checkbox" checked={showAll} onChange={(e) => onShowAllChange(e.target.checked)} />
      Camera setup, habitat, bait and comments
    </label>
    {showAll && (
      <>
        <FormCard title="Camera">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Camera model" placeholder="e.g. Reconyx-PC800" hint={DESCRIPTIONS.cameraModel}
                   value={deployment.camera_model ?? ''} onChange={(v) => onField('camera_model', v || null)} />
            <Field label="Camera id" placeholder="e.g. P800HG08192031" hint={DESCRIPTIONS.cameraID}
                   value={deployment.camera_id ?? ''} onChange={(v) => onField('camera_id', v || null)} />
            <Field label="Camera delay (s)" type="number" min={0} step={1} placeholder="e.g. 120" hint={DESCRIPTIONS.cameraDelay} error={errors.camera_interval}
                   value={deployment.camera_interval?.toString() ?? ''} onChange={(v) => onField('camera_interval', v ? Number(v) : null)} />
            <Field label="Detection distance (m)" type="number" min={0} step="any" placeholder="e.g. 9.5" hint={DESCRIPTIONS.detectionDistance} error={errors.detection_distance}
                   value={deployment.detection_distance?.toString() ?? ''} onChange={(v) => onField('detection_distance', v ? Number(v) : null)} />
            <Field label="Camera height (m)" type="number" min={0} step="any" placeholder="e.g. 1.2" hint={DESCRIPTIONS.cameraHeight} error={errors.camera_height}
                   value={deployment.camera_height?.toString() ?? ''} onChange={(v) => onField('camera_height', v ? Number(v) : null)} />
            <Field label="Camera depth (m)" type="number" min={0} step="any" placeholder="e.g. 4.8" hint={DESCRIPTIONS.cameraDepth} error={errors.camera_depth}
                   value={deployment.camera_depth?.toString() ?? ''} onChange={(v) => onField('camera_depth', v ? Number(v) : null)} />
            <Field label="Camera tilt (°)" type="number" min={-90} max={90} step={1} placeholder="e.g. -90" hint={DESCRIPTIONS.cameraTilt} error={errors.camera_tilt}
                   value={deployment.camera_tilt?.toString() ?? ''} onChange={(v) => onField('camera_tilt', v ? Number(v) : null)} />
            <Field label="Camera heading (°)" type="number" min={0} max={360} step={1} placeholder="e.g. 225" hint={DESCRIPTIONS.cameraHeading} error={errors.camera_heading}
                   value={deployment.camera_heading?.toString() ?? ''} onChange={(v) => onField('camera_heading', v ? Number(v) : null)} />
          </div>
          {deployment.camera_height != null && deployment.camera_depth != null && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mt-3">Camera height and depth are mutually exclusive — only one should be set.</p>
          )}
        </FormCard>

        <FormCard title="Site">
          <div className="grid grid-cols-2 gap-4">
            <SelectField label="Feature type" value={deployment.feature_type ?? ''} options={FEATURE_TYPE_OPTIONS} hint={DESCRIPTIONS.featureType}
                         onChange={(v) => onField('feature_type', (v || null) as FeatureType | null)} />
            <Field label="Habitat" placeholder="e.g. Mixed temperate low-land forest" hint={DESCRIPTIONS.habitat}
                   value={deployment.habitat ?? ''} onChange={(v) => onField('habitat', v || null)} />
            <Field label="Set up by" placeholder="e.g. Jakub Bubnicki" hint={DESCRIPTIONS.setupBy}
                   value={deployment.setup_by ?? ''} onChange={(v) => onField('setup_by', v || null)} />
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4">
            <CheckboxField label="Bait used" hint={DESCRIPTIONS.baitUse} checked={!!deployment.bait_use} onChange={(v) => onField('bait_use', v || null)} />
            <CheckboxField label="Timestamps have issues" hint={DESCRIPTIONS.timestampIssues} checked={!!deployment.timestamp_issues} onChange={(v) => onField('timestamp_issues', v || null)} />
          </div>
        </FormCard>

        <FormCard title="Grouping and notes">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Deployment groups" placeholder="e.g. season:winter 2020 | grid:A1" hint={DESCRIPTIONS.deploymentGroups}
                   value={deployment.deployment_groups ?? ''} onChange={(v) => onField('deployment_groups', v || null)} />
            <Field label="Tags (comma-separated)" placeholder="e.g. forest edge, bait:food" hint={DESCRIPTIONS.deploymentTags}
                   value={deployment.tags.join(', ')} onChange={(v) => onField('tags', v.split(',').map((t) => t.trim()).filter(Boolean))} />
            <div className="col-span-2">
              <Field label="Comments" hint={DESCRIPTIONS.deploymentComments}
                     value={deployment.comments ?? ''} onChange={(v) => onField('comments', v || null)} />
            </div>
          </div>
        </FormCard>
      </>
    )}
    </>
  )
}

/** What the image checks found — only the checks that were run have something to say. */
export function ValidationReport({ validation }: { validation: ValidationResult }) {
  return (
    <div className="mt-4 text-sm space-y-1 mb-2">
      {validation.corrupted !== undefined && (
        <p className={validation.corrupted.length ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'}>
          {validation.corrupted.length
            ? `⚠ ${validation.corrupted.length} corrupted image(s): ${validation.corrupted.map((c) => c.path).join(', ')}`
            : '✔ No corrupted images.'}
        </p>
      )}
      {validation.sequence_issues !== undefined && (
        <p className={validation.sequence_issues.length ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
          {validation.sequence_issues.length
            ? `⚠ ${validation.sequence_issues.length} out-of-order shot(s): ${validation.sequence_issues.map((i) => `${i.path_a} (${i.date_a.slice(0, 10)}) → ${i.path_b} (${i.date_b.slice(0, 10)})`).join('; ')}`
            : '✔ Shots are in chronological order.'}
        </p>
      )}
      {validation.cameras !== undefined && (
        <div className={imageCheckPassed('camera', validation) ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}>
          {imageCheckPassed('camera', validation) ? (
            <p>✔ Every image was taken by the same camera: <span className="font-mono">{describeCamera(validation.cameras[0])}</span>.</p>
          ) : (
            <>
              {validation.cameras.length > 1 && <p>⚠ The images come from {validation.cameras.length} different cameras:</p>}
              {validation.cameras.length > 0 && (
                <ul className="list-disc ml-6">
                  {validation.cameras.map((c, i) => (
                    <li key={i}>
                      <span className="font-mono">{describeCamera(c)}</span> — {c.count} image(s), e.g. {c.examples.join(', ')}
                    </li>
                  ))}
                </ul>
              )}
              {(validation.cameras_without_info ?? 0) > 0 && <p>⚠ {validation.cameras_without_info} image(s) have no camera information.</p>}
            </>
          )}
          {validation.exiftool === false && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">ExifTool isn't installed, so the camera id (serial number) may be missing — install it for a fuller reading.</p>
          )}
        </div>
      )}
      {validation.exif_missing !== undefined && (
        <div className={imageCheckPassed('exif', validation) ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}>
          {imageCheckPassed('exif', validation) ? (
            <p>✔ Every image has its capture date, camera model and camera id.</p>
          ) : (
            <ul className="list-disc ml-6">
              {(Object.keys(EXIF_FIELD_LABELS) as ExifField[]).filter((f) => validation.exif_missing![f].count > 0).map((f) => (
                <li key={f}>
                  ⚠ {validation.exif_missing![f].count} image(s) without {EXIF_FIELD_LABELS[f]}, e.g. {validation.exif_missing![f].examples.join(', ')}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {validation.duplicates !== undefined && (
        <div className={validation.duplicates.length ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
          {validation.duplicates.length === 0 ? (
            <p>✔ No duplicate images.</p>
          ) : (
            <>
              <p>⚠ {validation.duplicates.length} group(s) of duplicate images ({validation.duplicates.reduce((n, g) => n + g.files.length - 1, 0)} extra copies):</p>
              <ul className="list-disc ml-6">
                {validation.duplicates.map((g, i) => <li key={i} className="font-mono">{g.files.join(' = ')}</li>)}
              </ul>
            </>
          )}
        </div>
      )}
      {validation.subdirectories !== undefined && (
        <p className={validation.subdirectories.length ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
          {validation.subdirectories.length
            ? `⚠ Images are spread across ${validation.subdirectories.length} subfolder(s): ${validation.subdirectories.join(', ')}`
            : '✔ All images are directly in this folder.'}
        </p>
      )}
    </div>
  )
}

/** What the postvalidation found — only the checks that were run have something to say. */
export function DeploymentCheckReport({ result, toleranceHours }: { result: DeploymentCheckResult; toleranceHours: string }) {
  return (
    <div className="mt-4 text-sm space-y-1 mb-2">
      {(['deployment_id', 'collection_name', 'collection_prefix', 'location'] as const).map((key) => {
        const check = result[key]
        return check === undefined ? null : (
          <p key={key} className={check.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}>
            {check.ok ? '✔' : '⚠'} {check.message}
          </p>
        )
      })}
      {STATISTIC_CHECKS.map((key) => {
        const stat = result[key]
        return stat === undefined ? null : (
          <div key={key} className={stat.skipped ? 'text-zinc-500 dark:text-zinc-400' : stat.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'}>
            <p>{stat.skipped ? 'ℹ' : stat.ok ? '✔' : '⚠'} {stat.message}</p>
            {stat.history.length > 0 && (
              <p className="text-xs ml-5 text-zinc-500 dark:text-zinc-400 font-mono">
                {stat.history.map((h) => `R${String(h.revision).padStart(4, '0')}: ${Number.isInteger(h.value) ? h.value : h.value.toFixed(1)}`).join(' · ')}
              </p>
            )}
          </div>
        )
      })}
      {result.out_of_range !== undefined && (
        result.out_of_range.length === 0 ? (
          <p className="text-emerald-600 dark:text-emerald-400">
            ✔ The first image is at the start, the last at the end and the rest in between (± {result.tolerance_hours ?? toleranceHours} h).
          </p>
        ) : (
          <div className="text-amber-600 dark:text-amber-400">
            <p>⚠ {result.out_of_range.length} image(s) outside the deployment's dates (± {result.tolerance_hours ?? toleranceHours} h):</p>
            <ul className="list-disc ml-6">
              {result.out_of_range.map((o) => (
                <li key={o.path}>
                  <span className="font-mono">{o.path}</span> — {o.date.replace('T', ' ')}, {RANGE_RULE_LABELS[o.rule ?? 'between']}{o.expected ? ` (${o.expected.replace(/T/g, ' ')})` : ''}
                </li>
              ))}
            </ul>
          </div>
        )
      )}
      {result.camera_mismatches !== undefined && (
        <>
          <p className={result.camera_mismatches.length ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
            {result.camera_mismatches.length
              ? `⚠ ${result.camera_mismatches.length} image(s) with a different camera model than declared: ${result.camera_mismatches.map((m) => `${m.path} (${m.detected})`).join(', ')}`
              : '✔ No camera-model mismatches with the declared camera.'}
          </p>
          <p className={(result.camera_models_found?.length ?? 0) > 1 ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'}>
            {(result.camera_models_found?.length ?? 0) > 1
              ? `⚠ ${result.camera_models_found!.length} distinct camera models found across images: ${result.camera_models_found!.join(', ')}`
              : '✔ All images share the same camera model.'}
          </p>
        </>
      )}
    </div>
  )
}

/** What is filled in from the previous revision of the same deployment: its camera setup, site and notes — everything but what
 * is each revision's own (the id, the start and end dates, whether its timestamps had issues) and the location's (its coordinates). */
export const FILLED_FROM_PREVIOUS = [
  'camera_interval', 'detection_distance', 'camera_height', 'camera_depth', 'camera_tilt', 'camera_heading',
  'feature_type', 'habitat', 'setup_by', 'bait_use', 'deployment_groups', 'tags', 'comments',
] as const satisfies readonly (keyof DeploymentFields)[]

/** `current` filled in from the same deployment's previous revision, keeping its own id, location and dates. The camera model and id
 * only fill in what the images did not give, as what they say is more reliable than what was written down before. */
export function fillFromPreviousRevision(current: DeploymentFields, previous: DeploymentFields): DeploymentFields {
  return {
    ...current, ...Object.fromEntries(FILLED_FROM_PREVIOUS.map((k) => [k, previous[k]])), tags: previous.tags ?? [],
    camera_model: current.camera_model || previous.camera_model, camera_id: current.camera_id || previous.camera_id,
  }
}

interface Props {
  /** A run left unfinished by an earlier visit (see ResumeSessionsPage) —
   * its source folder and scan are restored, and, if it had got as far as
   * the deployment's details, those too. Where the images were taken isn't
   * kept in a session, so the wizard picks up at that step. */
  resumeSession?: SessionSummary
  /** Offered once a deployment is imported: goes to the upload page, on the collection it went into. */
  onUpload?: (target: UploadTarget) => void
}

// Blank credentials: the backend uses the ones saved in the settings.
const NO_CREDENTIALS: TrapperCredentials = {}

export default function ImportDeploymentPage({ resumeSession, onUpload }: Props) {
  const [step, setStep] = useState(resumeSession ? STEPS.findIndex((s) => s.key === 'origin') : 0)

  // The Trapper account is the one saved in the settings: nothing is asked for here, and the backend
  // fills in the blank credentials from it.
  const [account, setAccount] = useState<TrapperAccount | null>(null)
  const [conn, setConn] = useState<{ status: ConnStatus; message: string }>({ status: 'idle', message: '' })

  const [researchProjects, setResearchProjects] = useState<ResearchProject[]>([])
  // This run's session on disk (see services.session_store) — null until the
  // source folder is scanned, which is when it's first created.
  const [taskId, setTaskId] = useState<string | null>(resumeSession?.task_id ?? null)

  const [sourceDir, setSourceDir] = useState('')
  const [browsing, setBrowsing] = useState(false)
  const [browseError, setBrowseError] = useState<string | null>(null)
  const [scan, setScan] = useState<ScanResult | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)

  // Step "validate": opt-in checks over the scanned folder's images.
  const [imageChecks, setImageChecks] = useState<Set<ImageCheck>>(new Set(['corrupted', 'sequence', 'structure', 'camera', 'exif', 'duplicates']))
  const [requiredImageChecks, setRequiredImageChecks] = useState<Set<ImageCheck>>(new Set())
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)

  // Step "origin": where the images were taken — a research project and
  // one of its locations, both kept in the local collections folder. Each
  // is picked from what's there or added: by hand, or filled in from
  // Trapper. `origin` holds the resolved choice.
  const [origin, setOrigin] = useState({ researchProject: '', locationId: '', locationName: '', timezone: '' })
  const [localProjects, setLocalProjects] = useState<LocalResearchProject[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState('')
  const [addingProject, setAddingProject] = useState(false)
  const [projectSource, setProjectSource] = useState<OriginSource | null>(null)
  // The new research project's form, in Trapper's own "Add research project" fields.
  const [projectDraft, setProjectDraft] = useState(EMPTY_RESEARCH_PROJECT)
  const [trapperProjectPks, setTrapperProjectPks] = useState<string[]>([])
  const [savingProject, setSavingProject] = useState(false)
  const [localLocations, setLocalLocations] = useState<LocalLocation[]>([])
  const [selectedLocationId, setSelectedLocationId] = useState('')
  const [addingLocation, setAddingLocation] = useState(false)
  const [locationSource, setLocationSource] = useState<OriginSource | null>(null)
  const [locationDraft, setLocationDraft] = useState(EMPTY_LOCATION_DRAFT)
  const [trapperLocationProjectPk, setTrapperLocationProjectPk] = useState('')
  const [trapperLocations, setTrapperLocations] = useState<Location[]>([])
  const [trapperLocationPks, setTrapperLocationPks] = useState<string[]>([])
  const [loadingTrapperLocations, setLoadingTrapperLocations] = useState(false)
  const [savingLocation, setSavingLocation] = useState(false)
  const [originError, setOriginError] = useState<string | null>(null)

  // Step "checks"/"import": where the deployment's collection is kept locally by
  // default — <collections folder>/<research project id>/<R0003> — and whether it's there.
  // The folder where this deployment is already kept, if it is — importing it again would be refused.
  const [existingFolder, setExistingFolder] = useState<string | null>(null)
  // The closest earlier revision of this deployment, if one was kept — to offer filling the form in from it.
  const [previousRevision, setPreviousRevision] = useState<PreviousDeployment | null>(null)
  const [filledFrom, setFilledFrom] = useState<string | null>(null)
  const [plannedCollection, setPlannedCollection] = useState<CollectionPath | null>(null)
  const [plannedCollectionError, setPlannedCollectionError] = useState<string | null>(null)

  const [deployment, setDeployment] = useState<DeploymentFields>(EMPTY_DEPLOYMENT_FIELDS)
  const [revision, setRevision] = useState('')
  const [timezone, setTimezone] = useState('')
  // Both belong to the location (see LocationTimeSettings): the deployment only reads them from it.
  // null: the location doesn't say (it was kept before this was asked), so the setting's default stands.
  const [ignoreDstChoice, setIgnoreDst] = useState<boolean | null>(null)
  // The revision starts as the next one expected for the location, until it is typed.
  const revisionTouched = useRef(false)
  const [revisionHint, setRevisionHint] = useState<string | null>(null)
  const [showAllFields, setShowAllFields] = useState(false)
  const [savingDetails, setSavingDetails] = useState(false)

  // Step "checks": opt-in checks of the images against the deployment's own
  // fields, once it's known.
  const [deploymentChecks, setDeploymentChecks] = useState<Set<DeploymentCheck>>(new Set(ALL_DEPLOYMENT_CHECKS))
  // Which checks the settings page turns on, and the tolerance and the statistical parameters the postvalidation uses — read again
  // when the validate and postvalidation steps are shown, since the settings can change meanwhile.
  const [checkSettings, setCheckSettings] = useState<WizardSettings>(DEFAULT_CHECK_SETTINGS)
  const [preprocessSteps, setPreprocessSteps] = useState<Set<PreprocessStep>>(new Set(['rename', 'resize', 'metadata']))
  // Set the moment a value is edited here (a ref, so a settings response arriving meanwhile never puts it back).
  const preprocessTouched = useRef(false)
  const [exiftool, setExiftool] = useState<boolean | null>(null) // whether ExifTool is installed; null until known
  // The deployment's row in its collection's FileTimestampLog, written on leaving the details.
  const [timestampLog, setTimestampLog] = useState<TimestampLogResult | null>(null)
  const [timestampLogError, setTimestampLogError] = useState<string | null>(null)
  const [requiredDeploymentChecks, setRequiredDeploymentChecks] = useState<Set<DeploymentCheck>>(new Set())
  const [checkingDeployment, setCheckingDeployment] = useState(false)
  const [deploymentCheck, setDeploymentCheck] = useState<DeploymentCheckResult | null>(null)
  const [deploymentCheckError, setDeploymentCheckError] = useState<string | null>(null)

  const [importing, setImporting] = useState(false)
  const [events, setEvents] = useState<ImportEvent[]>([])
  const [importError, setImportError] = useState<string | null>(null)
  const [destDir, setDestDir] = useState<string | null>(null)

  const stepKey = STEPS[step]?.key

  useEffect(() => {
    if (stepKey !== 'validate' && stepKey !== 'checks' && stepKey !== 'preprocessing') return
    let cancelled = false
    api.getSettings()
      .then((s) => {
        if (cancelled) return
        setCheckSettings({ VALIDATION: s.VALIDATION, POSTVALIDATION: s.POSTVALIDATION, PREPROCESSING: s.PREPROCESSING })
        // What can be edited in the wizard starts from the settings, until it has been.
        if (!preprocessTouched.current) setPreprocessSteps(new Set((['rename', 'resize', 'metadata'] as const).filter((step) => s.PREPROCESSING[step])))
      })
      .catch(() => { /* the settings can't be read: every check stays shown */ })
    return () => { cancelled = true }
  }, [stepKey])

  // Adding metadata needs ExifTool: find out when the preprocessing is listed.
  useEffect(() => {
    if (stepKey !== 'preprocessing') return
    let cancelled = false
    api.exiftoolStatus()
      .then((s) => { if (!cancelled) setExiftool(s.available) })
      .catch(() => { if (!cancelled) setExiftool(null) })
    return () => { cancelled = true }
  }, [stepKey])

  // What is shown — and so run — is what the settings turn on.
  const shownImageChecks = IMAGE_CHECK_OPTIONS.filter((o) => checkSettings.VALIDATION[o.value])
  const shownDeploymentChecks = DEPLOYMENT_CHECK_OPTIONS.filter((o) => checkSettings.POSTVALIDATION[o.value])
  const runnableImageChecks = shownImageChecks.map((o) => o.value).filter((c) => imageChecks.has(c))
  const runnableDeploymentChecks = shownDeploymentChecks.map((o) => o.value).filter((c) => deploymentChecks.has(c))

  // What is done to the images: the steps chosen, less the metadata if ExifTool isn't there to write it.
  const preSettings = checkSettings.PREPROCESSING
  const ignoreDst = ignoreDstChoice ?? preSettings.ignore_dst
  const effectivePreprocessSteps = new Set([...preprocessSteps].filter((step) => step !== 'metadata' || exiftool !== false))
  const startDay = (scan?.start_date ?? '').slice(0, 10).replace(/-/g, '')
  const exampleImageName = `${deployment.deployment_id || 'R0003-DONA_01'}__${startDay || 'YYYYMMDD'}_1.JPEG`.toUpperCase()
  function togglePreprocessStep(step: PreprocessStep) {
    preprocessTouched.current = true
    setPreprocessSteps((current) => toggled(current, step))
  }

  useEffect(() => {
    api.trapperGetConfig()
      .then(setAccount)
      .catch(() => setAccount(null))
  }, [])

  // The resumed session's source folder and scan are restored straight away. Where
  // it was taken isn't kept in a session, so the run picks up at that step — with
  // the deployment's details, if it had got as far as filling them in.
  useEffect(() => {
    if (!resumeSession) return
    setSourceDir(resumeSession.source_dir)
    setScan(resumeSession.scan)
    if (resumeSession.deployment) {
      setDeployment(resumeSession.deployment)
      setRevision(revisionOf(resumeSession.deployment.deployment_id)); revisionTouched.current = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeSession])

  async function handleBrowse() {
    setBrowsing(true); setBrowseError(null)
    try {
      const { path } = await api.browseFolder()
      if (path) {
        setSourceDir(path); setScan(null); setValidation(null); setValidationError(null)
      }
    } catch (e) {
      setBrowseError(e instanceof Error ? e.message : 'Could not open the folder browser.')
    } finally {
      setBrowsing(false)
    }
  }

  async function handleScan() {
    setScanning(true); setScanError(null); setScan(null); setValidation(null); setValidationError(null)
    try {
      const result = await api.scanFolder(sourceDir)
      setScan(result)
      setDeployment((d) => ({
        ...d,
        start_date: d.start_date || result.start_date || '',
        end_date: d.end_date || result.end_date,
        camera_model: d.camera_model || result.camera_model,
        camera_id: d.camera_id || result.camera_id,
      }))
      try {
        const session = await api.saveScan(sourceDir, result, taskId ?? undefined)
        setTaskId(session.task_id)
      } catch {
        // Best-effort — the run still works even if the session can't be saved.
      }
    } catch (e) {
      setScanError(e instanceof Error ? e.message : 'Could not scan the folder.')
    } finally {
      setScanning(false)
    }
  }

  function toggleImageCheck(check: ImageCheck) {
    setImageChecks((prev) => {
      const next = toggled(prev, check)
      if (!next.has(check)) setRequiredImageChecks((r) => (r.has(check) ? toggled(r, check) : r))
      return next
    })
  }

  async function handleValidate() {
    setValidating(true); setValidationError(null); setValidation(null)
    try {
      setValidation(await api.validateImages(sourceDir, runnableImageChecks))
    } catch (e) {
      setValidationError(e instanceof Error ? e.message : 'Could not validate the images.')
    } finally {
      setValidating(false)
    }
  }

  const requiredImageChecksOk = [...requiredImageChecks]
    .filter((c) => checkSettings.VALIDATION[c])
    .every((c) => imageCheckPassed(c, validation) === true)

  const projectErrors = validateResearchProject(projectDraft)
  const shownProjectFieldErrors = shownProjectErrors(projectErrors)
  const selectedProject = localProjects.find((p) => p.acronym === selectedProjectId)
  const selectedLocation = localLocations.find((l) => l.location_id === selectedLocationId)
  // The deployment needs coordinates (Camtrap DP requires them) — they come with the location.
  const locationLacksCoordinates = Boolean(selectedLocation) && (selectedLocation!.latitude == null || selectedLocation!.longitude == null)
  const originReady = Boolean(selectedProjectId && origin.locationId.trim()) && !locationLacksCoordinates && !addingProject && !addingLocation
  const locationErrors = {
    location_id: locationDraft.location_id.trim() ? undefined : 'Required',
    timezone: locationDraft.timezone && !isValidTimezone(locationDraft.timezone) ? 'Not a known IANA timezone (e.g. Europe/Madrid).' : undefined,
    latitude: rangeError(locationDraft.latitude, -90, 90, true),
    longitude: rangeError(locationDraft.longitude, -180, 180, true),
    coordinate_uncertainty: locationDraft.coordinate_uncertainty.trim() === ''
      ? undefined
      : (Number.isInteger(Number(locationDraft.coordinate_uncertainty)) && Number(locationDraft.coordinate_uncertainty) >= 1 ? undefined : 'Must be a whole number, 1 or more.'),
  }
  const canSaveProject = projectSource !== null && Object.keys(projectErrors).length === 0 && !savingProject
  const canSaveLocation = locationSource === 'manual' && Object.values(locationErrors).every((e) => !e) && !savingLocation
  const accountReady = trapperAccountReady(account)

  async function handleTestConnection() {
    setConn({ status: 'testing', message: '' })
    try {
      const result = await api.trapperTestConnection(NO_CREDENTIALS)
      const { results } = await api.trapperResearchProjects(NO_CREDENTIALS)
      setResearchProjects(results)
      setConn({ status: 'ok', message: `Connected — ${result.research_projects_count} research project(s) available.` })
    } catch (e) {
      setConn({ status: 'error', message: e instanceof Error ? e.message : 'Could not connect to Trapper.' })
    }
  }

  // Adding a research project or a location from Trapper connects, with the account of the settings, as soon as it is asked for.
  const wantsTrapper = (addingProject && projectSource === 'trapper') || (addingLocation && locationSource === 'trapper')
  useEffect(() => {
    if (wantsTrapper && accountReady && conn.status === 'idle') void handleTestConnection()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantsTrapper, accountReady, conn.status])

  function resetOriginChoice() {
    setOrigin({ researchProject: '', locationId: '', locationName: '', timezone: '' })
    setSelectedProjectId(''); setAddingProject(false); setProjectSource(null); setProjectDraft(EMPTY_RESEARCH_PROJECT)
    setTrapperProjectPks([])
    setLocalLocations([]); setSelectedLocationId(''); setAddingLocation(false); setLocationSource(null)
    setLocationDraft(EMPTY_LOCATION_DRAFT)
    setTrapperLocationProjectPk(''); setTrapperLocations([]); setTrapperLocationPks([]); setOriginError(null)
    setDeployment((d) => ({ ...d, location_id: '', location_name: null }))
  }

  /** The location the images were taken at is also the deployment's own. */
  function applyOriginLocation(location?: LocalLocation) {
    const locationId = location?.location_id ?? ''
    setDeployment((d) => ({
      ...d, location_id: locationId || null, location_name: location?.name || null, deployment_id: buildDeploymentId(revision, locationId),
      latitude: location?.latitude ?? null, longitude: location?.longitude ?? null, coordinate_uncertainty: location?.coordinate_uncertainty ?? null,
    }))
  }

  function updateProject<K extends keyof typeof EMPTY_RESEARCH_PROJECT>(key: K, value: (typeof EMPTY_RESEARCH_PROJECT)[K]) {
    setProjectDraft((p) => ({ ...p, [key]: value }))
  }

  /** The revision number, and with it the deployment id. */
  function applyRevision(value: string) {
    setRevision(value)
    setDeployment((d) => ({ ...d, deployment_id: buildDeploymentId(value, d.location_id) }))
  }

  function handleRevisionChange(value: string) {
    revisionTouched.current = true; setRevisionHint(null)
    applyRevision(value)
  }

  // ── Research project ──

  function selectProject(project: LocalResearchProject | undefined) {
    setSelectedProjectId(project?.acronym ?? '')
    setSelectedLocationId(''); setAddingLocation(false); setOriginError(null)
    setOrigin({ researchProject: project ? `${project.acronym} — ${project.name}` : '', locationId: '', locationName: '', timezone: '' })
    applyOriginLocation(undefined)
  }

  function startAddingProject() {
    setAddingProject(true); setProjectSource(null); setProjectDraft(EMPTY_RESEARCH_PROJECT)
    setTrapperProjectPks([]); setOriginError(null)
  }

  function handleProjectSourceChange(source: OriginSource) {
    setProjectSource(source); setProjectDraft(EMPTY_RESEARCH_PROJECT); setTrapperProjectPks([])
  }

  /** Keeps a research project in the collections folder and picks it. */
  async function addProject(project: LocalResearchProject) {
    setSavingProject(true); setOriginError(null)
    try {
      const saved = await api.saveResearchProject(project)
      setLocalProjects((list) => [...list, saved].sort((a, b) => a.acronym.toLowerCase().localeCompare(b.acronym.toLowerCase())))
      setAddingProject(false)
      selectProject(saved)
    } catch (e) {
      setOriginError(e instanceof Error ? e.message : 'Could not save the research project.')
    } finally {
      setSavingProject(false)
    }
  }

  function handleSaveProject() {
    return addProject({
      ...projectDraft, name: projectDraft.name.trim(), acronym: projectDraft.acronym.trim(),
      event_interval: projectDraft.event_interval ?? 0, trapper_pk: null,
    })
  }

  /** From Trapper: the research projects ticked there are simply added — no form, as many as are ticked.
   * One already kept here is just picked. The first is the one marked by default afterwards. */
  async function handleAddTrapperProjects() {
    setSavingProject(true); setOriginError(null)
    const problems: string[] = []
    const chosen: LocalResearchProject[] = []
    const added: LocalResearchProject[] = []
    for (const pk of trapperProjectPks) {
      const rp = researchProjects.find((p) => String(p.pk) === pk)
      if (!rp) continue
      const already = localProjects.find((p) => p.acronym === rp.acronym)
      if (already) { chosen.push(already); continue }
      const project: LocalResearchProject = { ...EMPTY_RESEARCH_PROJECT, name: rp.name, acronym: rp.acronym ?? '', trapper_pk: rp.pk }
      const problem = validateResearchProject(project)
      if (problem.name || problem.acronym) {
        problems.push(`“${rp.name}” can't be added from Trapper as it is: ${problem.acronym ?? problem.name} Add it by hand instead.`)
        continue
      }
      try {
        const saved = await api.saveResearchProject(project)
        added.push(saved); chosen.push(saved)
      } catch (e) {
        problems.push(`“${rp.name}”: ${e instanceof Error ? e.message : 'could not be saved.'}`)
      }
    }
    if (added.length) setLocalProjects((list) => [...list, ...added].sort((a, b) => a.acronym.toLowerCase().localeCompare(b.acronym.toLowerCase())))
    setSavingProject(false)
    if (chosen.length) { setAddingProject(false); selectProject(chosen[0]) }
    if (problems.length) setOriginError(problems.join(' '))
  }

  // ── Location ──

  function selectLocation(location: LocalLocation | undefined) {
    setSelectedLocationId(location?.location_id ?? '')
    setOrigin((o) => ({ ...o, locationId: location?.location_id ?? '', locationName: location?.name ?? '', timezone: location?.timezone ?? '' }))
    applyOriginLocation(location)
    applyTimezone(location?.timezone ?? '')
    setIgnoreDst(location?.ignore_dst ?? null)
  }

  function startAddingLocation() {
    setAddingLocation(true); setLocationSource(null); setLocationDraft(EMPTY_LOCATION_DRAFT)
    setTrapperLocationProjectPk(''); setTrapperLocations([]); setTrapperLocationPks([]); setOriginError(null)
  }

  function handleLocationSourceChange(source: OriginSource) {
    setLocationSource(source); setLocationDraft(EMPTY_LOCATION_DRAFT)
    setTrapperLocationPks([])
  }

  /** From Trapper: the locations of the chosen Trapper research project. */
  async function handleTrapperLocationProjectChange(pk: string) {
    setTrapperLocationProjectPk(pk)
    setTrapperLocations([]); setTrapperLocationPks([]); setOriginError(null)
    if (!pk) return
    setLoadingTrapperLocations(true)
    try {
      const { results } = await api.trapperLocations(NO_CREDENTIALS, Number(pk))
      setTrapperLocations(results)
    } catch (e) {
      setOriginError(e instanceof Error ? e.message : "Could not load the research project's locations.")
    } finally {
      setLoadingTrapperLocations(false)
    }
  }

  /** Keeps a location in the research project's folder and picks it. */
  async function addLocation(location: LocalLocation) {
    setSavingLocation(true); setOriginError(null)
    try {
      const saved = await api.saveLocalLocation(selectedProjectId, location)
      setLocalLocations((list) => [...list, saved])
      setAddingLocation(false)
      selectLocation(saved)
    } catch (e) {
      setOriginError(e instanceof Error ? e.message : 'Could not save the location.')
    } finally {
      setSavingLocation(false)
    }
  }

  function handleSaveLocation() {
    return addLocation({
      location_id: locationDraft.location_id.trim(), name: locationDraft.name.trim() || null,
      timezone: locationDraft.timezone.trim() || null, ignore_dst: locationDraft.ignore_dst, trapper_pk: null,
      latitude: Number(locationDraft.latitude), longitude: Number(locationDraft.longitude),
      coordinate_uncertainty: locationDraft.coordinate_uncertainty.trim() ? Number(locationDraft.coordinate_uncertainty) : null,
    })
  }

  /** From Trapper: the locations ticked there are simply added — no form, as many as are ticked. One
   * already kept here is just picked. The first is the one marked by default afterwards. */
  async function handleAddTrapperLocations() {
    setSavingLocation(true); setOriginError(null)
    const problems: string[] = []
    const chosen: LocalLocation[] = []
    const added: LocalLocation[] = []
    for (const pk of trapperLocationPks) {
      const loc = trapperLocations.find((l) => String(l.pk) === pk)
      if (!loc) continue
      const already = localLocations.find((l) => l.location_id.toLowerCase() === loc.location_id.toLowerCase())
      if (already) { chosen.push(already); continue }
      if (loc.latitude == null || loc.longitude == null) {
        problems.push(`“${loc.location_id}” has no coordinates in Trapper, and a deployment needs them. Add it by hand instead.`)
        continue
      }
      try {
        const saved = await api.saveLocalLocation(selectedProjectId, {
          location_id: loc.location_id, name: loc.name || null,
          timezone: loc.timezone && isValidTimezone(loc.timezone) ? loc.timezone : null, ignore_dst: loc.ignore_dst ?? null, trapper_pk: loc.pk,
          latitude: loc.latitude, longitude: loc.longitude, coordinate_uncertainty: null,
        })
        added.push(saved); chosen.push(saved)
      } catch (e) {
        problems.push(`“${loc.location_id}”: ${e instanceof Error ? e.message : 'could not be saved.'}`)
      }
    }
    if (added.length) setLocalLocations((list) => [...list, ...added])
    setSavingLocation(false)
    if (chosen.length) { setAddingLocation(false); selectLocation(chosen[0]) }
    if (problems.length) setOriginError(problems.join(' '))
  }

  /** Sets the timezone and re-stamps both dates with the designator it
   * gives them — the wall-clock time stays, its offset follows. */
  function applyTimezone(tz: string) {
    setTimezone(tz)
    setDeployment((d) => ({
      ...d, start_date: stampTimezone(d.start_date, tz), end_date: d.end_date ? stampTimezone(d.end_date, tz) : d.end_date,
    }))
  }

  function toggleDeploymentCheck(check: DeploymentCheck) {
    setDeploymentChecks((prev) => {
      const next = toggled(prev, check)
      if (!next.has(check)) setRequiredDeploymentChecks((r) => (r.has(check) ? toggled(r, check) : r))
      return next
    })
  }

  async function handleCheckDeployment() {
    setCheckingDeployment(true); setDeploymentCheckError(null); setDeploymentCheck(null)
    try {
      setDeploymentCheck(await api.validateDeployment(sourceDir, deployment, runnableDeploymentChecks, {
        // The collection is the one the deployment id names (its R0003 prefix).
        collectionName: null,
        expectedLocationId: origin.locationId || null,
        toleranceHours: Number(toleranceHours),
        researchProjectId: researchProjectId || null,
        statistics: statistics ?? undefined,
      }))
    } catch (e) {
      setDeploymentCheckError(e instanceof Error ? e.message : 'Could not check the deployment.')
    } finally {
      setCheckingDeployment(false)
    }
  }

  // The tolerance and what the statistical checks mean by a sequence and by similar come from the settings.
  const toleranceHours = String(checkSettings.POSTVALIDATION.tolerance_hours)
  const statistics = statParamsValid(statParamsOf(checkSettings.POSTVALIDATION))
  const requiredDeploymentChecksOk = [...requiredDeploymentChecks]
    .filter((c) => checkSettings.POSTVALIDATION[c])
    .every((c) => deploymentCheckPassed(c, deploymentCheck) === true)

  // Camtrap DP's own rules for the deployment's fields (required ones,
  // ranges, the dates' timezone designator…) — what a new deployment must
  // satisfy to leave the details, and what's flagged under each field.
  const deploymentErrors = validateDeployment(deployment, timezone)
  const fieldErrors = shownErrors(deploymentErrors)
  const revisionNumber = Number(revision)
  const revisionValid = revision.trim() !== '' && Number.isInteger(revisionNumber) && revisionNumber >= 1 && revisionNumber <= 9999
  const deploymentConforms = Object.keys(deploymentErrors).length === 0
  const newDetailsReady = revisionValid && deploymentConforms
  // What names this research project's folder in the local collections folder: its acronym.
  const researchProjectId = selectedProjectId

  // Every collection is kept locally before anything is uploaded: once the
  // deployment is known, work out where its collection goes by default — for the
  // postvalidation's checks and to say so at the import.
  useEffect(() => {
    if (stepKey !== 'checks' && stepKey !== 'preprocessing' && stepKey !== 'import') return
    if (!researchProjectId || !deployment.deployment_id) return
    let cancelled = false
    api.collectionPath(researchProjectId, deployment.deployment_id)
      .then((result) => { if (!cancelled) { setPlannedCollection(result); setPlannedCollectionError(null) } })
      .catch((e) => {
        if (cancelled) return
        setPlannedCollection(null)
        setPlannedCollectionError(e instanceof Error ? e.message : 'Could not work out where the collection is kept.')
      })
    return () => { cancelled = true }
  }, [stepKey, researchProjectId, deployment.deployment_id])

  // Whether the deployment the revision and the location name is already kept — said as soon as it can be known.
  useEffect(() => {
    const id = deployment.deployment_id
    if (stepKey !== 'deployment' || !researchProjectId || !id) { setExistingFolder(null); return }
    let cancelled = false
    api.existingDeployments(researchProjectId, [id])
      .then(({ results }) => { if (!cancelled) setExistingFolder(results[id] ?? null) })
      .catch(() => { if (!cancelled) setExistingFolder(null) })
    return () => { cancelled = true }
  }, [stepKey, researchProjectId, deployment.deployment_id])

  // The revision starts as the next one expected for the location — one after the highest kept — until it is typed.
  useEffect(() => {
    if (stepKey !== 'deployment' || !selectedProjectId || !deployment.location_id || revisionTouched.current) return
    let cancelled = false
    api.nextRevision(selectedProjectId, deployment.location_id)
      .then(({ last, next }) => {
        if (cancelled || revisionTouched.current) return
        applyRevision(String(next))
        setRevisionHint(last
          ? `Filled in as the next after R${String(last).padStart(4, '0')}, the latest kept for this location — change it if it is not right.`
          : 'Filled in as the first revision of this location — change it if it is not right.')
      })
      .catch(() => { /* no suggestion: it is typed */ })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepKey, selectedProjectId, deployment.location_id])

  // ...and whether an earlier revision of it was kept, to offer its details.
  useEffect(() => {
    const id = deployment.deployment_id
    setFilledFrom(null)
    if (stepKey !== 'deployment' || !researchProjectId || !id) { setPreviousRevision(null); return }
    let cancelled = false
    api.previousDeployments(researchProjectId, [id])
      .then(({ results }) => { if (!cancelled) setPreviousRevision(results[id] ?? null) })
      .catch(() => { if (!cancelled) setPreviousRevision(null) })
    return () => { cancelled = true }
  }, [stepKey, researchProjectId, deployment.deployment_id])

  function handleFillFromPrevious() {
    if (!previousRevision) return
    setDeployment((d) => fillFromPreviousRevision(d, previousRevision.deployment))
    setShowAllFields(true) // so what was filled in is there to see
    setFilledFrom(previousRevision.deployment_id)
  }

  // The research projects kept in the collections folder — read each time the origin step is shown.
  useEffect(() => {
    if (stepKey !== 'origin') return
    let cancelled = false
    api.listResearchProjects()
      .then(({ results }) => { if (!cancelled) setLocalProjects(results) })
      .catch((e) => { if (!cancelled) setOriginError(e instanceof Error ? e.message : 'Could not read the collections folder.') })
    return () => { cancelled = true }
  }, [stepKey])

  // ...and the locations of the one picked.
  useEffect(() => {
    if (!selectedProjectId) { setLocalLocations([]); return }
    let cancelled = false
    api.listLocalLocations(selectedProjectId)
      .then(({ results }) => { if (!cancelled) setLocalLocations(results) })
      .catch((e) => { if (!cancelled) setOriginError(e instanceof Error ? e.message : 'Could not read the locations.') })
    return () => { cancelled = true }
  }, [selectedProjectId])

  // Adding a location from Trapper: start from the Trapper research project this one was filled in from.
  useEffect(() => {
    if (locationSource !== 'trapper' || conn.status !== 'ok' || trapperLocationProjectPk || !selectedProject?.trapper_pk) return
    void handleTrapperLocationProjectChange(String(selectedProject.trapper_pk))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locationSource, conn.status, trapperLocationProjectPk, selectedProject])

  const canImport = Boolean(plannedCollection) && Boolean(researchProjectId) && deploymentConforms

  function handleBack() {
    setStep((s) => s - 1)
  }

  /** Saves the deployment's own fields (best-effort) before moving on to
   * the postvalidation. */
  async function handleContinueFromDeployment() {
    setSavingDetails(true); setTimestampLogError(null)
    if (taskId) {
      try { await api.saveDetails(taskId, deployment) } catch { /* best-effort */ }
    }
    try {
      // The collection's FileTimestampLog — wildintel-tools' file, one row per deployment — before the postvalidation.
      setTimestampLog(await api.writeTimestampLog(researchProjectId, deployment))
    } catch (e) {
      setTimestampLogError(e instanceof Error ? e.message : 'Could not write the collection\'s timestamp log.')
      setSavingDetails(false)
      return
    }
    setSavingDetails(false)
    setStep((s) => s + 1)
  }

  async function handleImport() {
    setImporting(true); setEvents([]); setImportError(null); setDestDir(null)
    const onEvent = (event: ImportEvent) => {
      setEvents((prev) => [...prev, event])
      if (event.type === 'done') {
        setDestDir(event.dest_dir)
        // The run finished — nothing left to resume.
        if (taskId) api.discardSession(taskId).catch(() => {})
      }
    }
    try {
      // Into its collection in the collections folder (a new one is named like the deployment's R0003 prefix).
      const options: PreprocessingOptions = {
        rename: effectivePreprocessSteps.has('rename'), resize: effectivePreprocessSteps.has('resize'), resize_width: preSettings.resize_width,
        metadata: effectivePreprocessSteps.has('metadata'), owner: preSettings.owner, publisher: preSettings.publisher,
        coverage: preSettings.coverage, license_url: preSettings.license_url, research_project: selectedProject?.name ?? '',
        convert_to_utc: preSettings.convert_to_utc,
      }
      await api.importLocal(
        sourceDir, plannedCollection!.path, plannedCollection!.exists ? null : plannedCollection!.collection, deployment, options, onEvent,
      )
    } catch (e) {
      setImportError(e instanceof Error ? e.message : 'The import failed.')
    } finally {
      setImporting(false)
    }
  }

  const [openFolderError, setOpenFolderError] = useState<string | null>(null)
  async function handleOpenFolder() {
    setOpenFolderError(null)
    try { await api.openFolder(destDir!) } catch (e) { setOpenFolderError(e instanceof Error ? e.message : String(e)) }
  }

  function handleStartOver() {
    setStep(0)
    setSourceDir(''); setScan(null); setScanError(null); setValidation(null); setValidationError(null)
    setImageChecks(new Set(['corrupted', 'sequence', 'structure', 'camera', 'exif', 'duplicates'])); setRequiredImageChecks(new Set())
    resetOriginChoice()
    setConn({ status: 'idle', message: '' })
    setResearchProjects([])
    setDeployment(EMPTY_DEPLOYMENT_FIELDS); setTimezone('')
    setPlannedCollection(null); setPlannedCollectionError(null)
    setDeploymentCheck(null); setDeploymentCheckError(null)
    preprocessTouched.current = false
    setShowAllFields(false); setRevision(''); revisionTouched.current = false; setRevisionHint(null)
    setDeploymentChecks(new Set(ALL_DEPLOYMENT_CHECKS)); setRequiredDeploymentChecks(new Set())
    setTimestampLog(null); setTimestampLogError(null)
    setEvents([]); setImportError(null); setDestDir(null)
    setTaskId(null)
  }

  function updateField<K extends keyof DeploymentFields>(key: K, value: DeploymentFields[K]) {
    setDeployment((d) => ({ ...d, [key]: value }))
  }

  const connectionForm = <TrapperAccountNotice account={account} conn={conn} onRetry={handleTestConnection} />

  return (
    <div className="max-w-screen-md mx-auto px-4 py-8">
      <h2 className="text-xl font-bold mb-1 text-zinc-900 dark:text-zinc-100">Import deployment</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
        Organizes a folder of camera-trap images into a local collection. It doesn't upload them to Trapper yet.
      </p>

      {/* Step indicator */}
      <div className="flex items-start mb-10">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-start flex-1">
            <div className="flex flex-col items-center" style={{ minWidth: 56 }}>
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center font-bold mb-1 text-sm ${
                  i < step ? 'bg-emerald-600 text-white' : i === step ? 'bg-blue-600 text-white' : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-500 dark:text-zinc-400'
                }`}
              >
                {i < step ? '✓' : i + 1}
              </div>
              <small className={`text-xs whitespace-nowrap ${i === step ? 'text-zinc-900 dark:text-zinc-100' : 'text-zinc-500 dark:text-zinc-400'}`}>
                {s.label}
              </small>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 border-t mx-1 mt-[18px] ${i < step ? 'border-emerald-500' : 'border-zinc-300 dark:border-zinc-700'}`} />
            )}
          </div>
        ))}
      </div>

      {/* ── Step: source folder ── */}
      {stepKey === 'folder' && (
        <div>
          <StepHeading>Source images folder</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">Where the deployment's camera-trap images are, on this machine.</p>
          <div className="mb-4 rounded border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-sm text-amber-800 dark:text-amber-300">
            Copy the images from the camera's memory card to a local folder first — don't point this at the card itself.
          </div>
          <div className="mb-2">
            <label className={labelClass} htmlFor="source-dir">Folder path</label>
            <div className="flex gap-2">
              <input id="source-dir" className={`${inputClass} flex-1`} placeholder="/home/me/Pictures/R0001-SITE_01"
                     value={sourceDir} onChange={(e) => { setSourceDir(e.target.value); setScan(null); setValidation(null); setValidationError(null) }} />
              <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={browsing} onClick={handleBrowse}>
                {browsing && <SmallSpinner />}
                {browsing ? 'Browsing…' : 'Browse…'}
              </button>
              <button type="button" className={btnOutline} disabled={!sourceDir || scanning} onClick={handleScan}>
                {scanning ? <SmallSpinner /> : 'Scan'}
              </button>
            </div>
            {browseError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{browseError}</p>}
            {scanError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{scanError}</p>}
            {scan && (
              <div className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
                {scan.file_count} file(s), {scan.image_count} image(s) — {scan.start_date?.slice(0, 10) ?? '?'} → {scan.end_date?.slice(0, 10) ?? '?'}
                {scan.warnings.map((w, i) => <p key={i} className="text-amber-600 dark:text-amber-400">⚠ {w}</p>)}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Step: validate folder contents ── */}
      {stepKey === 'validate' && (
        <div>
          <StepHeading>Validate folder contents</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Pick which checks to run over the scanned images, and which of them must pass before moving on.
          </p>
          {shownImageChecks.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">
              Every validation check is turned off in the settings, so there is nothing to run here — go on.
            </p>
          ) : (
            <>
              <CheckTable options={shownImageChecks} enabled={imageChecks} required={requiredImageChecks}
                          onToggleEnabled={toggleImageCheck} onToggleRequired={(v) => setRequiredImageChecks((s) => toggled(s, v))}
                          onSetEnabled={setImageChecks} onSetRequired={setRequiredImageChecks} />
              <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={validating || runnableImageChecks.length === 0} onClick={handleValidate}>
                {validating && <SmallSpinner />}
                {validating ? 'Validating…' : 'Run validation'}
              </button>
            </>
          )}
          {validationError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{validationError}</p>}
          {validation && <ValidationReport validation={validation} />}
          {validation?.report_id && <ReportPanel reportId={validation.report_id} />}
        </div>
      )}

      {/* ── Step: where the images were taken ── */}
      {stepKey === 'origin' && (
        <div>
          <StepHeading>Where was it taken?</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-6">
            The research project and the location the images come from. They are kept in the collections folder — pick one that
            is already there, or add a new one, by hand or from Trapper.
          </p>

          <FormCard title="Research project" description="Those found in the collections folder.">
            {!addingProject ? (
              <>
                <label className={labelClass} htmlFor="origin-research-project">Research project</label>
                <Combobox
                  id="origin-research-project" options={localProjects.map((p) => ({ value: p.acronym, label: `${p.acronym} — ${p.name}` }))}
                  value={selectedProjectId} onChange={(id) => selectProject(localProjects.find((p) => p.acronym === id))}
                  placeholder={localProjects.length === 0 ? 'No research projects yet' : 'Select a research project…'}
                  clearLabel="Clear research project"
                />
                {localProjects.length === 0 && <p className={hintClass}>The collections folder has no research projects yet — add the first one.</p>}
                <div className="mt-3">
                  <button type="button" className={btnOutline} onClick={startAddingProject}>➕ Add a new research project</button>
                </div>
              </>
            ) : (
              <div>
                <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-3">New research project</p>
                <OptionCards options={ORIGIN_SOURCE_OPTIONS} selected={projectSource} onChoose={handleProjectSourceChange} />

                {projectSource === 'trapper' && (
                  <div className="mt-4">
                    {conn.status !== 'ok' ? connectionForm : (
                      <>
                        <p className={labelClass}>Trapper research projects</p>
                        <CheckboxList
                          filterLabel="Filter Trapper research projects" emptyText="No research projects found in Trapper." disabled={savingProject}
                          options={researchProjects.map((p) => ({ value: String(p.pk), label: p.acronym ? `${p.acronym} — ${p.name}` : p.name }))}
                          selected={trapperProjectPks} onChange={setTrapperProjectPks}
                        />
                        <p className={hintClass}>Tick one or more — they are added to the collections folder as they are, and the first one is picked.</p>
                      </>
                    )}
                  </div>
                )}

                {projectSource === 'manual' && (
                  <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="col-span-2">
                      <Field label="Name" required maxLength={RESEARCH_PROJECT_LIMITS.name} value={projectDraft.name} error={shownProjectFieldErrors.name}
                             onChange={(v) => updateProject('name', v)} />
                    </div>
                    <Field label="Acronym" required maxLength={RESEARCH_PROJECT_LIMITS.acronymMax} placeholder="e.g. DONA" value={projectDraft.acronym}
                           hint={`Between ${RESEARCH_PROJECT_LIMITS.acronymMin} and ${RESEARCH_PROJECT_LIMITS.acronymMax} characters. It names the project's folder.`} error={shownProjectFieldErrors.acronym}
                           onChange={(v) => updateProject('acronym', v)} />
                    <Field label="Event interval" type="number" required min={0} step={1} value={projectDraft.event_interval?.toString() ?? ''}
                           error={shownProjectFieldErrors.event_interval} onChange={(v) => updateProject('event_interval', v ? Number(v) : null)} />
                    <SelectField label="Sampling design" allowEmpty={false} options={SAMPLING_DESIGN_OPTIONS} value={String(projectDraft.sampling_design)}
                                 onChange={(v) => updateProject('sampling_design', Number(v))} />
                    <SelectField label="Sensor method" allowEmpty={false} options={SENSOR_METHOD_OPTIONS} value={String(projectDraft.sensor_method)}
                                 onChange={(v) => updateProject('sensor_method', Number(v))} />
                    <SelectField label="Animal types" allowEmpty={false} options={ANIMAL_TYPES_OPTIONS} value={String(projectDraft.animal_types)}
                                 onChange={(v) => updateProject('animal_types', Number(v))} />
                    <SelectField label="Bait use" allowEmpty={false} options={BAIT_USE_OPTIONS} value={String(projectDraft.bait_use)}
                                 onChange={(v) => updateProject('bait_use', Number(v))} />
                    <div className="col-span-2">
                      <Field label="Keywords" hint="Comma or space delimited tags." value={projectDraft.keywords} onChange={(v) => updateProject('keywords', v)} />
                    </div>
                    <div className="col-span-2">
                      <TextAreaField label="Abstract" maxLength={RESEARCH_PROJECT_LIMITS.text} value={projectDraft.abstract} error={shownProjectFieldErrors.abstract}
                                     onChange={(v) => updateProject('abstract', v)} />
                    </div>
                    <div className="col-span-2">
                      <TextAreaField label="Methods" maxLength={RESEARCH_PROJECT_LIMITS.text} value={projectDraft.methods} error={shownProjectFieldErrors.methods}
                                     onChange={(v) => updateProject('methods', v)} />
                    </div>
                    <div className="col-span-2">
                      <TextAreaField label="Description" maxLength={RESEARCH_PROJECT_LIMITS.text} value={projectDraft.description} error={shownProjectFieldErrors.description}
                                     onChange={(v) => updateProject('description', v)} />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-3 mt-4">
                  {projectSource === 'manual' && (
                    <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={!canSaveProject} onClick={handleSaveProject}>
                      {savingProject && <SmallSpinner />}
                      Save research project
                    </button>
                  )}
                  {projectSource === 'trapper' && conn.status === 'ok' && (
                    <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={trapperProjectPks.length === 0 || savingProject} onClick={handleAddTrapperProjects}>
                      {savingProject && <SmallSpinner />}
                      {`Add ${trapperProjectPks.length} research project${trapperProjectPks.length === 1 ? '' : 's'}`}
                    </button>
                  )}
                  <button type="button" className={btnOutline} onClick={() => { setAddingProject(false); setOriginError(null) }}>Cancel</button>
                </div>
              </div>
            )}
          </FormCard>

          {selectedProjectId && !addingProject && (
            <FormCard title="Location" description={`Locations of ${selectedProjectId}, found in the collections folder.`}>
              {!addingLocation ? (
                <>
                  <label className={labelClass} htmlFor="origin-location">Location</label>
                  <Combobox
                    id="origin-location" options={localLocations.map((l) => ({ value: l.location_id, label: `${l.location_id}${l.name ? ` — ${l.name}` : ''}` }))}
                    value={selectedLocationId} onChange={(id) => selectLocation(localLocations.find((l) => l.location_id === id))}
                    placeholder={localLocations.length === 0 ? 'No locations yet' : 'Select a location…'}
                    clearLabel="Clear location"
                  />
                  {localLocations.length === 0 && <p className={hintClass}>{selectedProjectId} has no locations yet — add the first one.</p>}
                  {locationLacksCoordinates && (
                    <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">{selectedLocationId} has no coordinates, and a deployment needs them — pick another location.</p>
                  )}
                  <div className="mt-3">
                    <button type="button" className={btnOutline} onClick={startAddingLocation}>➕ Add a new location</button>
                  </div>
                </>
              ) : (
                <div>
                  <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-200 mb-3">New location</p>
                  <OptionCards options={ORIGIN_SOURCE_OPTIONS} selected={locationSource} onChoose={handleLocationSourceChange} />

                  {locationSource === 'trapper' && (
                    <div className="mt-4">
                      {conn.status !== 'ok' ? connectionForm : (
                        <>
                          <div className="mb-4">
                            <label className={labelClass} htmlFor="trapper-location-project">Trapper research project</label>
                            <Combobox
                              id="trapper-location-project" options={researchProjects.map((p) => ({ value: String(p.pk), label: p.acronym ? `${p.acronym} — ${p.name}` : p.name }))}
                              value={trapperLocationProjectPk} onChange={handleTrapperLocationProjectChange}
                              placeholder={researchProjects.length === 0 ? 'No research projects found' : 'Select a research project…'}
                              clearLabel="Clear Trapper research project"
                            />
                          </div>
                          {trapperLocationProjectPk && (
                            <div>
                              <p className={labelClass}>Trapper locations</p>
                              <CheckboxList
                                filterLabel="Filter Trapper locations" emptyText={loadingTrapperLocations ? 'Loading locations…' : 'No locations found.'}
                                disabled={loadingTrapperLocations || savingLocation}
                                options={trapperLocations.map((l) => ({ value: String(l.pk), label: `${l.location_id}${l.name ? ` — ${l.name}` : ''}` }))}
                                selected={trapperLocationPks} onChange={setTrapperLocationPks}
                              />
                              <p className={hintClass}>Tick one or more — they are added to {selectedProjectId} as they are, and the first one is picked.</p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {locationSource === 'manual' && (
                    <div className="grid grid-cols-2 gap-4 mt-4">
                      <Field label="Location id" required placeholder="e.g. DONA_01" hint={DESCRIPTIONS.locationID} value={locationDraft.location_id}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, location_id: v }))} />
                      <Field label="Location name (optional)" placeholder="e.g. Doñana site 1" hint={DESCRIPTIONS.locationName} value={locationDraft.name}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, name: v }))} />
                      <Field label="Latitude" type="number" required min={-90} max={90} step="any" placeholder="e.g. 52.70442"
                             hint={DESCRIPTIONS.latitude} error={locationDraft.latitude ? locationErrors.latitude : undefined} value={locationDraft.latitude}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, latitude: v }))} />
                      <Field label="Longitude" type="number" required min={-180} max={180} step="any" placeholder="e.g. 23.84995"
                             hint={DESCRIPTIONS.longitude} error={locationDraft.longitude ? locationErrors.longitude : undefined} value={locationDraft.longitude}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, longitude: v }))} />
                      <Field label="Coordinate uncertainty (m)" type="number" min={1} step={1} placeholder="e.g. 100"
                             hint={DESCRIPTIONS.coordinateUncertainty} error={locationErrors.coordinate_uncertainty} value={locationDraft.coordinate_uncertainty}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, coordinate_uncertainty: v }))} />
                      <Field label="Timezone (IANA)" placeholder="e.g. Europe/Madrid" list="timezone-options" error={locationErrors.timezone}
                             hint="The location's own — every deployment there is read in it." value={locationDraft.timezone}
                             onChange={(v) => setLocationDraft((d) => ({ ...d, timezone: v }))} />
                      <label className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300 cursor-pointer mt-7">
                        <input type="checkbox" className="mt-1" checked={locationDraft.ignore_dst} onChange={(e) => setLocationDraft((d) => ({ ...d, ignore_dst: e.target.checked }))} />
                        The location’s cameras ignore summer time (DST)
                      </label>
                      <datalist id="timezone-options">
                        {knownTimezones().map((tz) => <option key={tz} value={tz} />)}
                      </datalist>
                    </div>
                  )}

                  <div className="flex items-center gap-3 mt-4">
                    {locationSource === 'manual' && (
                      <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={!canSaveLocation} onClick={handleSaveLocation}>
                        {savingLocation && <SmallSpinner />}
                        Save location
                      </button>
                    )}
                    {locationSource === 'trapper' && conn.status === 'ok' && (
                      <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={trapperLocationPks.length === 0 || savingLocation} onClick={handleAddTrapperLocations}>
                        {savingLocation && <SmallSpinner />}
                        {`Add ${trapperLocationPks.length} location${trapperLocationPks.length === 1 ? '' : 's'}`}
                      </button>
                    )}
                    <button type="button" className={btnOutline} onClick={() => { setAddingLocation(false); setOriginError(null) }}>Cancel</button>
                  </div>
                </div>
              )}
            </FormCard>
          )}

          {originError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{originError}</p>}
        </div>
      )}

      {/* ── Step: deployment details ── */}
      {stepKey === 'deployment' && (
        <div>
          <StepHeading>Deployment details</StepHeading>

          {(
            <>
              <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1 mb-5">
                <LocationTimeNote locationId={deployment.location_id} latitude={deployment.latitude} longitude={deployment.longitude} timezone={timezone} ignoreDst={ignoreDst} />
                Tell us about the deployment. Its names and dates are checked next.
              </p>

              <FormCard title="Identification" description="The revision number and the location give the deployment its id.">
                <div className="grid grid-cols-2 gap-4">
                  <Field label="Revision" type="number" required min={1} max={9999} step={1} placeholder="e.g. 3"
                         hint={revisionHint ?? 'The revision the images belong to: 1, 2, 3…'}
                         error={revision.trim() !== '' && !revisionValid ? 'Must be a whole number between 1 and 9999.' : undefined}
                         value={revision} onChange={handleRevisionChange} />
                  <Field label="Deployment id" readOnly placeholder="Filled in from the revision and the location"
                         hint={`R + the revision as four digits + “-” + the location id, e.g. R0003-DONA_01. ${DESCRIPTIONS.deploymentID}`}
                         error={fieldErrors.deployment_id} value={deployment.deployment_id} onChange={() => {}} />
                </div>
                {previousRevision && (
                  <div className="mt-3 rounded border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 px-3 py-2 text-sm text-blue-900 dark:text-blue-200">
                    <p>
                      There is an earlier revision of this deployment, <span className="font-mono">{previousRevision.deployment_id}</span>.
                      Do you want to fill this form in from it? Everything is copied except the start and end dates.
                    </p>
                    <div className="mt-2 flex items-center gap-3 flex-wrap">
                      <button type="button" className={btnOutline} onClick={handleFillFromPrevious}>Fill in from {previousRevision.deployment_id}</button>
                      {filledFrom && <span role="status" className="text-xs text-blue-800 dark:text-blue-300">Filled in from {filledFrom} — check the camera, site and notes below.</span>}
                    </div>
                  </div>
                )}
                {existingFolder && (
                  <p role="alert" className="mt-3 text-sm text-amber-700 dark:text-amber-400">
                    ⚠ This deployment already exists: <span className="font-mono break-all">{existingFolder}</span> is already kept, and importing again
                    would be refused as it would mix them. Choose another revision or location, or move that folder away.
                  </p>
                )}
              </FormCard>

              <DeploymentFormBody deployment={deployment} timezone={timezone} errors={fieldErrors} showAll={showAllFields}
                                  onShowAllChange={setShowAllFields} onField={updateField}
                                  datesGuessed={Boolean(scan?.start_date)} />
            </>
          )}
        </div>
      )}

      {/* ── Step: postvalidation ── */}
      {stepKey === 'checks' && (
        <div>
          <StepHeading>Postvalidation</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Now that the deployment is known, checks its names and dates against wildintel-tools' own rules, and the scanned
            images against the deployment — pick which to run, and which must pass before moving on.
          </p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">
            Some of these checks can be customized in the settings (Settings › Postvalidation): the tolerance of the image dates, and what the
            comparison with the previous revisions means — the length of a sequence, the way of comparing and how much counts as similar.
          </p>
          {timestampLog && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-4">
              {timestampLog.action === 'added' ? 'Added' : timestampLog.action === 'updated' ? 'Updated' : 'Already in'} the deployment in{' '}
              <span className="font-mono">{timestampLog.path}</span> — {timestampLog.rows} deployment(s) in that collection&rsquo;s timestamp log.
            </p>
          )}
          {shownDeploymentChecks.length === 0 ? (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">
              Every postvalidation check is turned off in the settings, so there is nothing to run here — go on.
            </p>
          ) : (
            <CheckTable options={shownDeploymentChecks} enabled={deploymentChecks} required={requiredDeploymentChecks}
                        onToggleEnabled={toggleDeploymentCheck} onToggleRequired={(v) => setRequiredDeploymentChecks((s) => toggled(s, v))}
                        onSetEnabled={setDeploymentChecks} onSetRequired={setRequiredDeploymentChecks} />
          )}
          {shownDeploymentChecks.length > 0 && (
            <button type="button" className={`${btnOutline} flex items-center gap-2`} disabled={checkingDeployment || runnableDeploymentChecks.length === 0} onClick={handleCheckDeployment}>
              {checkingDeployment && <SmallSpinner />}
              {checkingDeployment ? 'Checking…' : 'Run checks'}
            </button>
          )}
          {deploymentCheckError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{deploymentCheckError}</p>}
          {deploymentCheck && <DeploymentCheckReport result={deploymentCheck} toleranceHours={toleranceHours} />}
          {deploymentCheck?.report_id && <ReportPanel reportId={deploymentCheck.report_id} />}
        </div>
      )}

      {/* ── Step: preprocessing ── */}
      {stepKey === 'preprocessing' && (
        <div>
          <StepHeading>Preprocessing</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            What will be done to the images as they are imported. The originals in the source folder are never touched.
            Each optional step can be switched off for this run; its values come from Settings › Preprocessing.
          </p>
          <ol className="space-y-3 mb-2">
            <PreprocessItem title="Copy into the collection" always>
              The images are copied into{' '}
              <span className="font-mono">{plannedCollection ? `${plannedCollection.path}/${deployment.deployment_id}` : 'the deployment’s folder in the collections folder'}</span>.
              Anything that isn&rsquo;t an image is copied as it is.
            </PreprocessItem>
            <PreprocessItem title="Read the capture dates" always>
              From each image&rsquo;s EXIF, as the camera&rsquo;s local time in <span className="font-mono">{timezone || 'the timezone of the details'}</span>
              {ignoreDst ? ', ignoring summer time' : ''}{preSettings.convert_to_utc ? ', converted to UTC' : ''}.
              They go into the names and the metadata. An image with no EXIF date uses its file&rsquo;s date.
            </PreprocessItem>
            <PreprocessItem title="Rename the images" checked={effectivePreprocessSteps.has('rename')} onToggle={() => togglePreprocessStep('rename')}>
              <span className="font-mono">{'<deployment>__<YYYYMMDD>_<n>.<EXT>'}</span> in upper case — for example{' '}
              <span className="font-mono">{exampleImageName}</span>. The images end up together in the deployment&rsquo;s folder, numbered in file-name order.
            </PreprocessItem>
            <PreprocessItem title="Resize the images" checked={effectivePreprocessSteps.has('resize')} onToggle={() => togglePreprocessStep('resize')}>
              Images wider than <strong>{preSettings.resize_width} px</strong> are resized to that width, keeping their proportions, EXIF and colour profile.
              Narrower ones stay as they are.
            </PreprocessItem>
            <PreprocessItem
              title="Add metadata" checked={effectivePreprocessSteps.has('metadata')} onToggle={() => togglePreprocessStep('metadata')}
              disabledReason={exiftool === false ? 'ExifTool is not installed, and writing the metadata needs it.' : undefined}
            >
              Authorship, rights and license, written into each image as XMP:
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 mt-2 text-xs">
                <dt className="text-zinc-500 dark:text-zinc-400">Creator</dt>
                <dd className="font-mono">{`CT (<camera make and model> ${selectedProject?.name || 'Unknown'})`}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">Owner</dt>
                <dd className="font-mono">{preSettings.owner || 'Unknown'}{!preSettings.owner && <span className="ml-2 text-amber-600 dark:text-amber-400 font-sans">not set in Settings</span>}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">Publisher</dt>
                <dd className="font-mono">{preSettings.publisher || 'Unknown'}{!preSettings.publisher && <span className="ml-2 text-amber-600 dark:text-amber-400 font-sans">not set in Settings</span>}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">Rights</dt>
                <dd className="font-mono">{`© ${preSettings.owner || 'Unknown'}, ${new Date().getFullYear()}. All rights reserved.`}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">License</dt>
                <dd className="font-mono break-all">{preSettings.license_url}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">Coverage</dt>
                <dd className="font-mono">{preSettings.coverage || deployment.location_name || deployment.location_id || 'the deployment’s location'}</dd>
                <dt className="text-zinc-500 dark:text-zinc-400">Identifiers</dt>
                <dd>The hash of each original and of the image kept, so each can be traced back.</dd>
              </dl>
            </PreprocessItem>
          </ol>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            What was done to each image is recorded in a <span className="font-mono">preprocessing.json</span> beside them.
          </p>
        </div>
      )}

      {/* ── Step: import ── */}
      {stepKey === 'import' && (
        <div>
          <StepHeading>Import</StepHeading>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            Everything is ready — organize the images into their collection in the local collections folder
            {`, ${describePreprocessing(effectivePreprocessSteps)}`}.
          </p>
          {plannedCollection && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
              The images are kept locally in <span className="font-mono">{`${plannedCollection.path}/${deployment.deployment_id}`}</span> before they are uploaded.
            </p>
          )}
          {plannedCollectionError && <p className="text-sm text-red-600 dark:text-red-400 mb-4">{plannedCollectionError}</p>}
          <div className="flex justify-end mb-6">
            <button type="button" className={btnPrimary} disabled={!canImport || importing} onClick={handleImport}>
              {importing ? 'Importing…' : 'Import deployment'}
            </button>
          </div>

          {events.length > 0 && (
            <div className="rounded border border-zinc-200 dark:border-zinc-700 p-3 text-sm text-zinc-600 dark:text-zinc-400 max-h-48 overflow-y-auto mb-4">
              {events.map((e, i) => (
                <p key={i}>
                  {e.type === 'copy' && `[${e.index}/${e.total}] ${e.name}`}
                  {e.type === 'registering' && 'Registering the deployment in Trapper…'}
                  {e.type === 'sealing' && 'Checking the images and sealing the deployment…'}
                  {e.type === 'metadata' && `Writing the metadata of ${e.total} image(s)…`}
                  {e.type === 'skipped' && <span className="text-amber-600 dark:text-amber-400">⚠ Skipped {e.name}: {e.detail}</span>}
                  {e.type === 'done' && `✔ Imported${e.processed !== undefined ? ` ${e.processed} image(s)${e.skipped ? `, ${e.skipped} skipped` : ''}` : ''} — organized in ${e.dest_dir}${e.sealed === false ? ' (could not be sealed — see the log)' : ''}`}
                </p>
              ))}
            </div>
          )}
          {importError && <p className="text-sm text-red-600 dark:text-red-400">{importError}</p>}
          {(() => { const done = events.find((e) => e.type === 'done'); return done && done.type === 'done' && done.report_id ? <ReportPanel reportId={done.report_id} /> : null })()}
          {destDir && (
            <div className="flex items-center gap-3 flex-wrap">
              <p className="text-sm text-emerald-600 dark:text-emerald-400">✔ Deployment imported.</p>
              <button type="button" className={btnOutline} onClick={handleOpenFolder}>Open folder in file explorer</button>
              {onUpload && selectedProjectId && plannedCollection && (
                <button type="button" className={btnPrimary} onClick={() => onUpload({ researchProjectId: selectedProjectId, collection: plannedCollection.collection })}>
                  Upload to Trapper
                </button>
              )}
              {openFolderError && <p className="text-sm text-red-600 dark:text-red-400">{openFolderError}</p>}
            </div>
          )}
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-start mt-10">
        {destDir ? (
          <button type="button" className={btnOutline} onClick={handleStartOver}>Start over</button>
        ) : step > 0 ? (
          <button type="button" className={btnOutline} disabled={importing} onClick={handleBack}>Back</button>
        ) : (
          <div />
        )}

        {!destDir && stepKey === 'folder' && (
          <button type="button" className={btnPrimary} disabled={!scan} onClick={() => setStep((s) => s + 1)}>Next</button>
        )}
        {!destDir && stepKey === 'validate' && (
          <div className="flex flex-col items-end gap-1">
            {!requiredImageChecksOk && <p className="text-xs text-amber-600 dark:text-amber-400">Run validation and resolve the required checks to continue.</p>}
            <button type="button" className={btnPrimary} disabled={!requiredImageChecksOk} onClick={() => setStep((s) => s + 1)}>Continue</button>
          </div>
        )}
        {!destDir && stepKey === 'origin' && (
          <button type="button" className={btnPrimary} disabled={!originReady} onClick={() => setStep((s) => s + 1)}>Next</button>
        )}
        {!destDir && stepKey === 'deployment' && (
          <div className="flex flex-col items-end gap-1 max-w-md">
            {timestampLogError && <p className="text-xs text-red-600 dark:text-red-400 text-right">{timestampLogError}</p>}
            <button type="button" className={`${btnPrimary} flex items-center gap-2`} disabled={!newDetailsReady || savingDetails} onClick={handleContinueFromDeployment}>
              {savingDetails && <SmallSpinner />}
              {savingDetails ? 'Saving…' : 'Next'}
            </button>
          </div>
        )}
        {!destDir && stepKey === 'preprocessing' && (
          <button type="button" className={btnPrimary} onClick={() => setStep((s) => s + 1)}>Continue</button>
        )}
        {!destDir && stepKey === 'checks' && (
          <div className="flex flex-col items-end gap-1">
            {!requiredDeploymentChecksOk && <p className="text-xs text-amber-600 dark:text-amber-400">Run the checks and resolve the required ones to continue.</p>}
            <button type="button" className={btnPrimary} disabled={!requiredDeploymentChecksOk} onClick={() => setStep((s) => s + 1)}>Continue</button>
          </div>
        )}
      </div>
    </div>
  )
}
