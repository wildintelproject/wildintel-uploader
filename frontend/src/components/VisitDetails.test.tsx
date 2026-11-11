import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import VisitDetails from './VisitDetails'
import type { ClosedVisit } from '../types'

const stored = (over: object) => ({
  location_id: 'WICP_02_004', session: 'R0002', date: '2026-10-19', time: '13:15:00', actions: ['Revision'], trappers: 'Luis Gómez', status: null, battery_status: null, card_status: null,
  num_photos: null, sd: '8', date_time_ok: null, latitude: 37.0471, longitude: -6.4815, camera_id: 'SP1776213899', camera_status: null, ...over,
}) as never
const closed: ClosedVisit = {
  visit: stored({ date_time_ok: 'Yes' }),
  end: stored({ session: 'R0003', date: '2026-11-23', time: '13:20:00', actions: ['Revision'], trappers: 'Ana Pérez', num_photos: 920, camera_status: 'Damaged', battery_status: 'OK', card_status: 'OK', date_time_ok: 'Yes' }),
}

describe('VisitDetails', () => {
  it('puts whether the camera date and time were right with the state of the camera, the batteries and the SD card of the visit that collected the card — not in the visit that left it', () => {
    render(<VisitDetails closed={closed} onClose={vi.fn()} />)

    const left = within(screen.getByRole('region', { name: 'The visit that left the card' }))
    const collected = within(screen.getByRole('region', { name: 'The visit that collected it' }))
    expect(left.queryByText('Camera date & time OK')).not.toBeInTheDocument()
    expect(collected.getByText('Camera date & time OK')).toBeInTheDocument()
    expect(collected.getAllByText('OK').length).toBeGreaterThanOrEqual(2)              // batteries and card; the date and time say Yes
    expect(collected.getByText('Damaged')).toBeInTheDocument()
    expect(collected.getByText('920 photos')).toBeInTheDocument()
    expect(screen.getByText('35 days in the field')).toBeInTheDocument()
  })
})
