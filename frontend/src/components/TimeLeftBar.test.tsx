import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import TimeLeftBar, { timeLeft, timeLeftText } from './TimeLeftBar'

describe('timeLeft', () => {
  it('is unknown until the first batch ends', () => {
    expect(timeLeft({ start: 0, at: 0, done: 0, total: 1000 }, 5_000)).toBeNull()
  })

  it('is as long as the batches took for each item, for the items still to do, counted down', () => {
    // 200 of 1000 in 60 s: 300 s in all
    expect(timeLeft({ start: 0, at: 60_000, done: 200, total: 1000 }, 60_000)).toBe(240_000)
    expect(timeLeft({ start: 0, at: 60_000, done: 200, total: 1000 }, 90_000)).toBe(210_000)   // half a minute later, before the next batch
    expect(timeLeft({ start: 0, at: 60_000, done: 200, total: 1000 }, 400_000)).toBe(0)        // never below nothing
  })
})

describe('timeLeftText', () => {
  it('says seconds, minutes or hours, plainly', () => {
    expect(timeLeftText(38_000)).toBe('about 40 s')
    expect(timeLeftText(1_000)).toBe('about 5 s')
    expect(timeLeftText(185_000)).toBe('about 3 min')
    expect(timeLeftText(70 * 60_000)).toBe('about 1 h 10 min')
    expect(timeLeftText(120 * 60_000)).toBe('about 2 h')
  })
})

describe('TimeLeftBar', () => {
  it('says how many of how many, and the time left once it is known', () => {
    const now = Date.now()
    const { rerender } = render(<TimeLeftBar timing={{ start: now, at: now, done: 0, total: 1000 }} noun="images" label="Images done" />)
    expect(screen.getByText(/0 of 1,000 images · estimating the time left/)).toBeInTheDocument()

    rerender(<TimeLeftBar timing={{ start: now - 60_000, at: now, done: 200, total: 1000 }} noun="images" label="Images done" />)
    expect(screen.getByRole('progressbar', { name: 'Images done' })).toHaveAttribute('aria-valuenow', '200')
    expect(screen.getByText(/200 of 1,000 images · about 4 min left/)).toBeInTheDocument()
  })
})
