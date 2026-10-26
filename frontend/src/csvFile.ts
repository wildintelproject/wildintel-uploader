/** Reading and writing the CSV files of the lists kept in the settings (trappers, SD cards, cameras). */

/** The rows of a CSV text, the first being the header — the delimiter is the one the header has most of: comma, semicolon or tab. */
export function parseCsv(text: string): string[][] {
  const source = text.replace(/^﻿/, '')
  const head = source.split(/\r?\n/, 1)[0] ?? ''
  const delimiter = [',', ';', '\t'].reduce((best, d) => (head.split(d).length > head.split(best).length ? d : best), ',')
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < source.length; i++) {
    const c = source[i]
    if (quoted) {
      if (c === '"' && source[i + 1] === '"') { cell += '"'; i++ }
      else if (c === '"') quoted = false
      else cell += c
    } else if (c === '"') quoted = true
    else if (c === delimiter) { row.push(cell); cell = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && source[i + 1] === '\n') i++
      row.push(cell); cell = ''
      rows.push(row); row = []
    } else cell += c
  }
  if (cell || row.length > 0) { row.push(cell); rows.push(row) }
  return rows.filter((r) => r.some((c) => c.trim()))
}

/** The rows as CSV text, a cell quoted when it has to be. */
export function toCsv(rows: string[][]): string {
  const cell = (c: string) => (/[",;\n\r\t]/.test(c) ? `"${c.replace(/"/g, '""')}"` : c)
  return rows.map((r) => r.map(cell).join(',')).join('\r\n') + '\r\n'
}

/** Offers the text to be saved as a file with the name given. */
export function download(name: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

const squash = (name: string) => name.toLowerCase().replace(/[^a-z0-9]/g, '')

/** What reading a CSV text as the items of a list gave. */
export interface ItemsRead<T> { items: T[]; problems: string[] }

/** The items of a CSV text: the columns are found by the key or the label of a field (whatever the case, the spaces or the underscores).
 * A blank is none (null), a day must be YYYY-MM-DD, a yes/no is read as yes (yes, true, 1) or none, a value a field finds wrong is left blank and said, and a row without the first field — the one that names the item — is left out and said. */
export function readItems<T extends object>(
  text: string, fields: { key: keyof T & string; label: string; kind?: string; validate?: (value: string) => string | null }[], blank: T, noun: string,
): ItemsRead<T> {
  const [header, ...rows] = parseCsv(text)
  if (!header) return { items: [], problems: ['The file is empty.'] }
  const columns = fields.map((f) => header.findIndex((h) => [squash(f.key), squash(f.label)].includes(squash(h))))
  if (columns[0] < 0) return { items: [], problems: [`The file has no column for the ${fields[0].label.toLowerCase()}: ${header.join(', ')}.`] }
  const items: T[] = []
  const problems: string[] = []
  rows.forEach((row, i) => {
    const item: Record<string, unknown> = { ...(blank as Record<string, unknown>) }
    fields.forEach((f, j) => {
      const value = columns[j] >= 0 ? (row[columns[j]] ?? '').trim() : ''
      item[f.key] = j === 0 ? value : value || null
      if (f.kind === 'bool') item[f.key] = /^(yes|true|1|y|si|sí)$/i.test(value) ? 'yes' : null
      const wrong = j > 0 ? f.validate?.(value) : null
      if (wrong) {
        item[f.key] = null
        problems.push(`Row ${i + 2}: ${f.label.toLowerCase()} “${value}” — ${wrong.replace(/\.$/, '').toLowerCase()}; left blank.`)
      }
      if (f.kind === 'date' && value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        item[f.key] = null
        problems.push(`Row ${i + 2}: “${value}” is not a day (YYYY-MM-DD); left blank.`)
      }
    })
    if (!item[fields[0].key]) problems.push(`Row ${i + 2}: no ${fields[0].label.toLowerCase()}, so it is not a ${noun}; left out.`)
    else items.push(item as T)
  })
  return { items, problems }
}

/** The items as CSV text — a column per field, headed by its key. */
export function itemsToCsv<T extends object>(items: T[], fields: { key: keyof T & string }[]): string {
  return toCsv([fields.map((f) => f.key), ...items.map((it) => fields.map((f) => String((it as Record<string, unknown>)[f.key] ?? '')))])
}
