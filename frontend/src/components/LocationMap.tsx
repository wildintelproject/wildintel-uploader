import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const valid = (lat: string | null, lng: string | null) => {
  const a = Number(lat), b = Number(lng)
  return lat !== null && lng !== null && lat.trim() !== '' && lng.trim() !== '' && Number.isFinite(a) && Number.isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180
}

const PIN = L.divIcon({
  className: '',
  html: '<div style="width:18px;height:18px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#2563eb;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.5)"></div>',
  iconSize: [18, 18], iconAnchor: [9, 18],
})

/** A map of the place: it shows the coordinates typed, and clicking it or dragging the pin changes them. */
export default function LocationMap({ latitude, longitude, onChange, disabled = false }: {
  latitude: string | null; longitude: string | null; onChange: (latitude: string, longitude: string) => void; disabled?: boolean
}) {
  const box = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const pin = useRef<L.Marker | null>(null)
  const change = useRef(onChange)
  change.current = onChange
  const locked = useRef(disabled)
  locked.current = disabled
  const round = (n: number) => String(Math.round(n * 1e6) / 1e6)

  useEffect(() => {
    if (!box.current) return
    try {
      const m = L.map(box.current, { center: [20, 0], zoom: 2, attributionControl: true })
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(m)
      m.on('click', (e: L.LeafletMouseEvent) => { if (!locked.current) change.current(round(e.latlng.lat), round(e.latlng.lng)) })
      map.current = m
    } catch { /* no map where there is no layout (tests) */ }
    return () => { map.current?.remove(); map.current = null; pin.current = null }
  }, [])

  useEffect(() => {
    const m = map.current
    if (!m) return
    if (!valid(latitude, longitude)) { pin.current?.remove(); pin.current = null; return }
    const at = L.latLng(Number(latitude), Number(longitude))
    if (!pin.current) {
      pin.current = L.marker(at, { icon: PIN, draggable: !disabled }).addTo(m)
      pin.current.on('dragend', () => { const p = pin.current!.getLatLng(); change.current(round(p.lat), round(p.lng)) })
      m.setView(at, 13)
    } else {
      pin.current.setLatLng(at)
      if (!m.getBounds().contains(at)) m.panTo(at)
    }
  }, [latitude, longitude, disabled])

  return <div ref={box} role="application" aria-label="Map of the location" className="h-full min-h-56 w-full rounded-xl overflow-hidden border border-zinc-200 dark:border-zinc-700 z-0" />
}
