import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import QrCode, { qrPayload, qrSvg } from './QrCode'

describe('QrCode', () => {
  it('says which entity it is of, and the project it belongs to', () => {
    expect(qrPayload('camera', 'DONA', 'CAM-014')).toBe('wildintel:camera:DONA:CAM-014')
    expect(qrPayload('sdcard', null, 'SD-1')).toBe('wildintel:sdcard::SD-1')
  })

  it('draws it as an SVG that is different for a different text', () => {
    expect(qrSvg('wildintel:camera:DONA:A')).toContain('<svg')
    expect(qrSvg('wildintel:camera:DONA:A')).not.toBe(qrSvg('wildintel:camera:DONA:B'))
  })

  it('shows it with what it says and a way to download it', () => {
    render(<QrCode value="wildintel:camera:DONA:CAM 1" label="CAM 1" />)
    expect(screen.getByRole('img', { name: 'QR code of CAM 1' })).toBeInTheDocument()
    expect(screen.getByText('wildintel:camera:DONA:CAM 1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Download QR code' })).toHaveAttribute('download', 'CAM_1_qr.svg')
  })
})
