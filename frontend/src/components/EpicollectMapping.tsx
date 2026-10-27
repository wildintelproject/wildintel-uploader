import Notice from './Notice'
import { useEffect, useState } from 'react'
import { api } from '../api'
import { ALL_MAPPED_FIELDS, DEPLOYMENT_FIELD_GROUPS, canFill, suggestMapping } from '../epicollectMapping'
import type { MappedField } from '../epicollectMapping'
import type { EpicollectForm, EpicollectInput } from '../types'

const btnSoft = 'px-4 py-2 text-sm rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors'
// color-scheme makes the browser draw the select (and its list) in the page's theme, so the text can't end up light on light.
const selectClass = 'w-full rounded-lg px-3 py-2 text-sm bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-300 dark:border-zinc-700 focus:border-blue-500 outline-none cursor-pointer [color-scheme:light] dark:[color-scheme:dark] [&>option]:bg-white dark:[&>option]:bg-zinc-800 [&_option]:text-zinc-900 dark:[&_option]:text-zinc-100 disabled:opacity-60 disabled:cursor-not-allowed'

const TYPE_NAMES: Record<string, string> = {
  text: 'text', textarea: 'long text', integer: 'whole number', decimal: 'number', date: 'date', time: 'time', location: 'GPS', dropdown: 'dropdown',
  radio: 'one choice', checkbox: 'several choices', searchsingle: 'search', searchmultiple: 'search (several)', barcode: 'barcode', phone: 'phone',
}

const optionLabel = (i: EpicollectInput) => `${i.label} · ${TYPE_NAMES[i.type] ?? i.type}`

interface Props {
  /** Deployment field → ref of the Epicollect5 input that gives it. */
  mapping: Record<string, string>
  onChange: (mapping: Record<string, string>) => void
  /** The project is saved in the settings (the form is read with what is saved, not with what is being typed). */
  projectSaved: boolean
  /** What was typed in the project and the client differs from what is saved. */
  unsavedProject: boolean
}

/** Relates every field asked for when a deployment is defined with an input of the Epicollect5 form — so that the deployment can be
 * filled in from an entry. The mapping is a setting: it is kept with the rest when they are saved. */
export default function EpicollectMapping({ mapping, onChange, projectSaved, unsavedProject }: Props) {
  const [form, setForm] = useState<EpicollectForm | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [onlyUnmatched, setOnlyUnmatched] = useState(false)

  async function load() {
    setLoading(true); setError(null)
    try {
      setForm(await api.epicollectForm())
    } catch (e) {
      setForm(null)
      setError(e instanceof Error ? e.message : 'Could not read the Epicollect5 form.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (projectSaved) void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectSaved])

  const inputs = form?.inputs ?? []
  const byRef = new Map(inputs.map((i) => [i.ref, i]))
  const mappedCount = ALL_MAPPED_FIELDS.filter((f) => mapping[f.key]).length

  function choose(field: MappedField, ref: string) {
    const next = { ...mapping }
    if (ref) next[field.key] = ref; else delete next[field.key]
    onChange(next)
  }

  function options(field: MappedField): EpicollectInput[] {
    return inputs.filter((i) => canFill(field.kind, i.type) || i.ref === mapping[field.key])
  }

  return (
    <div className="space-y-5">
      <section aria-label="Match the form to a deployment" className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 px-6 py-5 space-y-4">
        <div>
          <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">Match the form to a deployment</h5>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed max-w-prose">
            For each field of a deployment, choose the question of your form that fills it.{' '}
            {form
              ? <>Your form has {inputs.length} {inputs.length === 1 ? 'question' : 'questions'} to choose from.</>
              : 'The questions are read from the project saved in the Epicollect5 section.'}
          </p>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-4 flex-wrap text-xs text-zinc-600 dark:text-zinc-400">
            <span>{mappedCount} of {ALL_MAPPED_FIELDS.length} fields matched</span>
            <span>What is not matched is filled in by hand, as now.</span>
          </div>
          <div role="progressbar" aria-label="Fields matched" aria-valuemin={0} aria-valuemax={ALL_MAPPED_FIELDS.length} aria-valuenow={mappedCount} className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
            <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${(mappedCount / ALL_MAPPED_FIELDS.length) * 100}%` }} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" className={btnSoft} disabled={inputs.length === 0} onClick={() => onChange(suggestMapping(inputs, mapping))}>Match by name</button>
          <button type="button" className={btnSoft} disabled={mappedCount === 0} onClick={() => onChange({})}>Clear all</button>
          <button type="button" className={btnSoft} disabled={!projectSaved || loading} onClick={() => void load()}>{loading ? 'Reading…' : 'Reload the form'}</button>
          <button type="button" aria-pressed={onlyUnmatched} className={`${btnSoft} ${onlyUnmatched ? 'ring-2 ring-blue-500' : ''}`} onClick={() => setOnlyUnmatched((v) => !v)}>Only fields not matched</button>
        </div>
      </section>

      {!projectSaved && (
        <Notice kind="warning" role="status">There is no Epicollect5 project saved yet: set its slug in the Epicollect5 section and save, and its form is read here.</Notice>
      )}
      {projectSaved && unsavedProject && (
        <Notice kind="warning" role="status">The project or the client was changed and not saved yet: the form shown is the one of what is saved. Save, then reload the form.</Notice>
      )}
      {error && <Notice kind="error" role="alert">{error}</Notice>}

      {DEPLOYMENT_FIELD_GROUPS.filter((group) => !onlyUnmatched || group.fields.some((f) => !mapping[f.key])).map((group) => (
        <section key={group.id} aria-label={group.label} className="rounded-xl border border-zinc-200 dark:border-zinc-800">
          {(() => {
            const matched = group.fields.filter((f) => mapping[f.key]).length
            return (
              <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-zinc-200 dark:border-zinc-800">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{group.label}</h3>
                <span className={`text-xs ${matched === group.fields.length ? 'text-emerald-700 dark:text-emerald-400' : 'text-zinc-500 dark:text-zinc-400'}`}>{matched} of {group.fields.length} matched</span>
              </div>
            )
          })()}
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {group.fields.filter((f) => !onlyUnmatched || !mapping[f.key]).map((field) => {
              const ref = mapping[field.key] ?? ''
              const current = byRef.get(ref)
              const stale = Boolean(ref) && form !== null && !current
              const mismatch = Boolean(current) && !canFill(field.kind, current!.type)
              const groups = [...new Set(options(field).map((i) => i.group ?? ''))]
              return (
                <li key={field.key} className="grid grid-cols-1 md:grid-cols-[14rem_1fr] gap-x-6 gap-y-1 px-4 py-3 items-start">
                  <div>
                    <p className="text-sm text-zinc-800 dark:text-zinc-200">{field.label}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">{field.hint}</p>
                  </div>
                  <div className="min-w-0">
                    <select className={selectClass} value={ref} aria-label={`Epicollect5 input for ${field.label}`} disabled={form === null && !ref}
                            onChange={(e) => choose(field, e.target.value)}>
                      <option value="">Not matched</option>
                      {stale && <option value={ref}>{ref} — not in the form any more</option>}
                      {groups.map((g) => {
                        const items = options(field).filter((i) => (i.group ?? '') === g)
                        const list = items.map((i) => <option key={i.ref} value={i.ref}>{optionLabel(i)}</option>)
                        return g ? <optgroup key={g} label={g}>{list}</optgroup> : list
                      })}
                    </select>
                    {stale && <p className="text-xs text-red-600 dark:text-red-400 mt-1">That input is not in the form any more — choose another, or clear it.</p>}
                    {mismatch && <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">A {TYPE_NAMES[current!.type] ?? current!.type} input can’t fill this field.</p>}
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
