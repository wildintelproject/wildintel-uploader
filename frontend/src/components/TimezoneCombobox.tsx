import { useMemo } from 'react'
import Combobox from './Combobox'
import { knownTimezones } from '../deploymentValidation'

/** The list of time zones, to pick from or filter by typing — the same box as the research projects. */
export default function TimezoneCombobox({ id, value, onChange, invalid = false, disabled = false }: {
  id: string; value: string; onChange: (v: string) => void; invalid?: boolean; disabled?: boolean
}) {
  const options = useMemo(() => {
    const zones = knownTimezones()
    if (value && !zones.includes(value)) zones.push(value)
    return zones.map((tz) => ({ value: tz, label: tz }))
  }, [value])
  return <Combobox id={id} options={options} value={value} onChange={onChange} placeholder="Pick a time zone" clearLabel="Clear time zone" invalid={invalid} disabled={disabled} />
}
