import qrcode from 'qrcode-generator'

/** What an entity's QR code says: `wildintel:<kind>:<research project>:<id>` — enough for a scan to tell which camera, location or SD card it is. */
export const qrPayload = (kind: 'camera' | 'location' | 'sdcard', researchProject: string | null | undefined, id: string) => `wildintel:${kind}:${researchProject ?? ''}:${id}`

/** The QR code of a text as an SVG: black on white, with the quiet zone around it that scanners need. */
export function qrSvg(text: string): string {
  const code = qrcode(0, 'M')
  code.addData(text)
  code.make()
  return code.createSvgTag({ cellSize: 6, margin: 4, scalable: true })
}

/** The card that shows the QR code of an entity, with what it says and a way to save it — to print on a label. */
export default function QrCode({ value, label }: { value: string; label: string }) {
  const svg = qrSvg(value)
  const href = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  return (
    <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/60 p-5 flex items-center gap-5 flex-wrap">
      <div role="img" aria-label={`QR code of ${label}`} className="w-36 h-36 shrink-0 rounded-lg bg-white p-1 [&>svg]:w-full [&>svg]:h-full" dangerouslySetInnerHTML={{ __html: svg }} />
      <div className="min-w-0">
        <h5 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">QR code</h5>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">It says <span className="font-mono break-all">{value}</span>. Print it on a label to find this one by scanning it.</p>
        <a href={href} download={`${label.replace(/[^\w.-]+/g, '_')}_qr.svg`} className="inline-flex rounded-lg border border-zinc-300 dark:border-zinc-600 px-3 py-1.5 text-sm font-medium text-zinc-800 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-800">Download QR code</a>
      </div>
    </div>
  )
}
