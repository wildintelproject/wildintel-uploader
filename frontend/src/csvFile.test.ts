import { describe, expect, it } from 'vitest'
import { itemsToCsv, parseCsv, readItems, toCsv } from './csvFile'

const FIELDS = [{ key: 'label' as const, label: 'Label' }, { key: 'brand' as const, label: 'Brand' }, { key: 'in_service' as const, label: 'In production since', kind: 'date' }]
const BLANK = { label: 'New', brand: null, in_service: null } as { label: string; brand: string | null; in_service: string | null }

describe('parseCsv and toCsv', () => {
  it('read quotes, doubled quotes, line breaks inside a cell and the delimiter of the header', () => {
    expect(parseCsv('﻿a;b\r\n"x;y";"say ""hi"""\n\n1;2')).toEqual([['a', 'b'], ['x;y', 'say "hi"'], ['1', '2']])
  })

  it('write what they read', () => {
    const rows = [['a', 'b'], ['x,y', 'say "hi"\nnow']]
    expect(parseCsv(toCsv(rows))).toEqual(rows)
  })
})

describe('readItems', () => {
  it('finds the columns by key or label, and takes a blank as none', () => {
    const { items, problems } = readItems('Brand,label,In_Production_Since\nSanDisk,A12,2025-03-01\n,B2,\n', FIELDS, BLANK, 'SD card')

    expect(items).toEqual([{ label: 'A12', brand: 'SanDisk', in_service: '2025-03-01' }, { label: 'B2', brand: null, in_service: null }])
    expect(problems).toEqual([])
  })

  it('leaves out a row with no name, and a day that is not one, and says so', () => {
    const { items, problems } = readItems('label,in_service\n,2025-01-01\nA1,1/3/2025\n', FIELDS, BLANK, 'SD card')

    expect(items).toEqual([{ label: 'A1', brand: null, in_service: null }])
    expect(problems).toEqual(['Row 2: no label, so it is not a SD card; left out.', 'Row 3: “1/3/2025” is not a day (YYYY-MM-DD); left blank.'])
  })

  it('refuses a file without the column that names the item', () => {
    expect(readItems('brand\nSanDisk\n', FIELDS, BLANK, 'SD card').problems[0]).toMatch(/no column for the label/)
    expect(readItems('', FIELDS, BLANK, 'SD card').problems).toEqual(['The file is empty.'])
  })
})

describe('readItems with a field to pick from', () => {
  const PICK = [...FIELDS, { key: 'status' as const, label: 'Status', kind: 'select', options: [{ value: 'active' }, { value: 'stolen' }] }]
  const BLANK_PICK = { ...BLANK, status: 'active' } as typeof BLANK & { status: string | null }

  it('takes one of the options whatever its case, a blank as what a new item has, and says any other', () => {
    const { items, problems } = readItems('label,status\nA1,STOLEN\nA2,\nA3,gone\n', PICK, BLANK_PICK, 'camera')

    expect(items.map((i) => i.status)).toEqual(['stolen', 'active', 'active'])
    expect(problems).toEqual(['Row 4: status “gone” is none of active, stolen; left as active.'])
  })
})

describe('itemsToCsv', () => {
  it('has a column per field, headed by its key', () => {
    expect(itemsToCsv([{ label: 'A12', brand: null, in_service: '2025-03-01' }], FIELDS)).toBe('label,brand,in_service\r\nA12,,2025-03-01\r\n')
  })
})

describe('readItems with fields that are checked or are yes or no', () => {
  const fields = [
    { key: 'id' as const, label: 'Id' },
    { key: 'lat' as const, label: 'Latitude', validate: (v: string) => (v === '' || Math.abs(Number(v)) <= 90 ? null : 'A number from -90 to 90.') },
    { key: 'dst' as const, label: 'Ignores DST', kind: 'bool' },
  ]
  const blank = { id: '', lat: null, dst: null } as { id: string; lat: string | null; dst: string | null }

  it('leaves blank what a field finds wrong, and says so, and reads yes or no', () => {
    const { items, problems } = readItems('id,lat,dst\nA,95,true\nB,12.5,no\n', fields, blank, 'location')

    expect(items).toEqual([{ id: 'A', lat: null, dst: 'yes' }, { id: 'B', lat: '12.5', dst: null }])
    expect(problems).toEqual(['Row 2: latitude “95” — a number from -90 to 90; left blank.'])
  })
})
