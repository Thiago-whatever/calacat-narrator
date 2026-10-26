import { ListSubheader, MenuItem, Select, Stack, Typography, type SxProps, type Theme } from '@mui/material'
import { useId } from 'react'
import { SrOnly } from './primitives'
import { ChevronIcon } from './icons'

export interface SelectOption {
  value: string
  label: string
}

export interface SelectGroup {
  label?: string
  options: SelectOption[]
}

interface Props {
  label: string
  /** Visually hidden label for selects whose purpose is obvious from the value (e.g. language). */
  hideLabel?: boolean
  value: string
  onChange: (value: string) => void
  groups: SelectGroup[]
  /** Pill-shaped, compact variant used in the feed filters. */
  pill?: boolean
  /** Layout of the label + select wrapper, e.g. `{ width: '100%' }`; the select fills it. */
  sx?: SxProps<Theme>
}

/** Labelled single-choice select with optional option groups. */
export function SelectField({ label, hideLabel, value, onChange, groups, pill, sx }: Props) {
  const labelId = useId()
  return (
    <Stack direction="row" spacing="10px" sx={[{ alignItems: 'center', minWidth: 0 }, ...(Array.isArray(sx) ? sx : [sx])]}>
      {hideLabel ? <SrOnly id={labelId}>{label}</SrOnly> : <Typography variant="label" id={labelId}>{label}</Typography>}
      <Select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        labelId={labelId}
        IconComponent={ChevronIcon}
        displayEmpty
        sx={(theme) => ({
          minWidth: 0,
          flex: 1,
          ...(pill ? { borderRadius: `${theme.custom.radii.pill}px`, fontSize: '.85em' } : {}),
          '& .MuiSelect-icon': { width: 14, height: 14, right: '.8em', top: 'calc(50% - 7px)' },
        })}
      >
        {groups.flatMap((g) => [
          ...(g.label ? [<ListSubheader key={`h-${g.label}`}>{g.label}</ListSubheader>] : []),
          ...g.options.map((o) => <MenuItem key={o.value} value={o.value}>{o.label}</MenuItem>),
        ])}
      </Select>
    </Stack>
  )
}
