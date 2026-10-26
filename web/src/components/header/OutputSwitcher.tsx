import { Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material'
import { useId, type ReactNode } from 'react'
import { SrOnly, StatusDot } from '../ui/primitives'

export interface OutputOption {
  id: string
  name: string
  score: string
  live: boolean
  disabled: boolean
}

interface Props {
  label: string
  liveText: string
  offText: string
  outputs: OutputOption[]
  value: string
  onChange: (id: string) => void
  /** Trailing pills (period, live-feed status). */
  children?: ReactNode
}

/** Transmission switcher (ADR-034): one button per output with its score and an on-air dot. */
export function OutputSwitcher({ label, liveText, offText, outputs, value, onChange, children }: Props) {
  const labelId = useId()
  return (
    <Stack
      direction="row"
      useFlexGap
      sx={(theme) => ({
        flex: '1 1 100%', order: 3, alignItems: 'center', flexWrap: 'wrap', gap: '6px',
        pt: '12px', borderTop: `1.5px solid ${theme.custom.colors.line}`,
      })}
    >
      <Typography variant="label" id={labelId}>{label}</Typography>
      <ToggleButtonGroup exclusive value={value} onChange={(_, id: string | null) => id && onChange(id)} aria-labelledby={labelId}>
        {outputs.map((o) => (
          <ToggleButton key={o.id} value={o.id} disabled={o.disabled}>
            <StatusDot tone={o.live ? 'live' : 'off'} blink={o.live} aria-hidden />
            <Typography component="span" sx={{ fontWeight: 700 }}>{o.name}</Typography>
            <Typography component="span" sx={{ fontSize: '.8em', opacity: 0.8, fontWeight: 600 }}>{o.score}</Typography>
            <SrOnly>{o.live ? liveText : offText}</SrOnly>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {children}
    </Stack>
  )
}
