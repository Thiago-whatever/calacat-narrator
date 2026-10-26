import { Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import { useId } from 'react'

export interface Segment<T extends string | number> {
  value: T
  label: string
  ariaLabel?: string
}

interface Props<T extends string | number> {
  label: string
  segments: Segment<T>[]
  /** null when no segment matches (e.g. a custom size). */
  value: T | null
  onChange: (value: T) => void
  disabled?: boolean
}

/** Exclusive choice shown as a 56px segmented control (control-bar size presets). */
export function SegmentedControl<T extends string | number>({ label, segments, value, onChange, disabled }: Props<T>) {
  const labelId = useId()
  return (
    <Stack direction="row" spacing="8px" sx={{ alignItems: 'center' }}>
      <Typography variant="label" id={labelId} className="segmented-label">{label}</Typography>
      <ToggleButtonGroup
        exclusive
        value={value}
        onChange={(_, next: T | null) => next !== null && onChange(next)}
        aria-labelledby={labelId}
        disabled={disabled}
        sx={(theme) => ({
          height: theme.custom.sizes.targetLarge,
          border: `2px solid ${theme.custom.colors.line}`,
          borderRadius: `${theme.custom.radii.large}px`,
          p: '4px',
          gap: '4px',
          flexWrap: 'nowrap',
          background: theme.custom.colors.surface,
          flex: { xs: 1, sm: 'none' },
          '& .MuiToggleButtonGroup-grouped, & .MuiToggleButtonGroup-grouped:not(:first-of-type)': {
            border: 0,
            borderRadius: '9px',
            margin: 0,
          },
        })}
      >
        {segments.map((s) => (
          <ToggleButton
            key={s.value}
            value={s.value}
            aria-label={s.ariaLabel ?? s.label}
            sx={(theme) => ({
              height: '100%', minWidth: 46, fontWeight: 700, flex: { xs: 1, sm: 'none' },
              '&:hover': { background: theme.custom.colors.tint },
              // Keep the chosen preset readable while the group is disabled.
              '&.Mui-selected.Mui-disabled': { background: theme.custom.colors.ink, color: theme.custom.colors.onBrand },
            })}
          >
            {s.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </Stack>
  )
}
