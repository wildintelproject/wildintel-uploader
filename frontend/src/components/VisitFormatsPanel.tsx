import { useState } from 'react'
import SidePanel from './SidePanel'
import { Glyph } from './ViewSwitch'
import { btnOutline } from '../pages/ImportDeploymentPage'
import { download } from '../csvFile'
import { VISIT_FORMATS, type VisitFormat } from '../visitFormats'
import visitsTemplate from '../visitsTemplate.csv?raw'

const TEMPLATES: Partial<Record<VisitFormat['key'], string>> = { custom: visitsTemplate }
const INFO = <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>
const DOWN = <path d="M12 4v12M7 11l5 5 5-5M4 20h16" />

function TemplateButton({ format }: { format: VisitFormat }) {
  const text = TEMPLATES[format.key]
  if (!format.template || !text) return null
  return (
    <button type="button" className={`${btnOutline} inline-flex items-center gap-2`} aria-label={`Download the template of the ${format.name}`} onClick={() => download(format.template!, text)}>
      <Glyph className="h-4 w-4">{DOWN}</Glyph>Download a template
    </button>
  )
}

/** The panel at the right with the formats of the files of visits that WildINTEL Uploader reads: each with what it is, a button that tells what goes in each of its columns, and
 * the one that downloads its template when it has one. */
export default function VisitFormatsPanel({ onClose }: { onClose: () => void }) {
  const [shown, setShown] = useState<VisitFormat | null>(null)
  return (
    <SidePanel label="Supported formats" title={shown ? shown.name : 'Supported formats'} subtitle={shown ? 'What goes in each column' : 'The files of visits WildINTEL Uploader reads'} onClose={onClose}
               icon={<Glyph className="h-5 w-5"><path d="M4 5h16v14H4zM4 10h16M10 5v14" /></Glyph>}>
      {shown === null ? (
        <div className="mt-2 space-y-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-300">At present WildINTEL Uploader supports these formats. When you choose a file, it detects which one it is.</p>
          {VISIT_FORMATS.map((f) => (
            <section key={f.key} aria-label={f.name} className="rounded-xl border border-zinc-200 dark:border-zinc-700 p-4">
              <h5 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{f.name}</h5>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{f.summary}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className={`${btnOutline} inline-flex items-center gap-2`} aria-label={`What goes in each column of the ${f.name}`} onClick={() => setShown(f)}>
                  <Glyph className="h-4 w-4">{INFO}</Glyph>What goes in each column
                </button>
                <TemplateButton format={f} />
              </div>
            </section>
          ))}
        </div>
      ) : (
        <div className="mt-2">
          <button type="button" className="text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline" onClick={() => setShown(null)}><span aria-hidden="true">← </span>The supported formats</button>
          <p className="mt-3 text-sm text-zinc-600 dark:text-zinc-300">{shown.intro}</p>
          <dl aria-label="Columns" className="mt-4 divide-y divide-zinc-200 dark:divide-zinc-700">
            {shown.columns.map((c) => (
              <div key={c.name} className="py-3">
                <dt className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-100">{c.name}</span>
                  {c.required && <span className="rounded bg-red-100 dark:bg-red-950/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-700 dark:text-red-300">Required</span>}
                </dt>
                <dd className="mt-1 text-sm text-zinc-600 dark:text-zinc-300">{c.meaning}</dd>
                {c.example && <dd className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">Example: <span className="font-mono">{c.example}</span></dd>}
              </div>
            ))}
          </dl>
          {shown.ignored && <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">Not read: <span className="font-mono">{shown.ignored}</span></p>}
          <div className="mt-4"><TemplateButton format={shown} /></div>
        </div>
      )}
    </SidePanel>
  )
}
