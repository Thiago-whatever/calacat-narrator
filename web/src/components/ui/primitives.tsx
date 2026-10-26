import { Box, Chip, LinearProgress, Typography, type ChipProps } from '@mui/material'
import { styled } from '@mui/material/styles'
import type { ReactNode } from 'react'
import { blinking, srOnly } from '../../theme/theme'

/** Text for assistive tech only. */
export const SrOnly = styled('span')(srOnly)

/** Screen-reader announcement region (`polite` for routine updates, `assertive` for goals). */
export function LiveRegion({ politeness, children }: { politeness: 'polite' | 'assertive'; children: ReactNode }) {
  return <SrOnly aria-live={politeness}>{children}</SrOnly>
}

type DotTone = 'current' | 'off' | 'live' | 'ready'

/** Small round status indicator; `blink` marks on-air states. */
export const StatusDot = styled('span', { shouldForwardProp: (p) => p !== 'tone' && p !== 'blink' })<{ tone?: DotTone; blink?: boolean }>(
  ({ theme, tone = 'current', blink }) => {
    const c = theme.custom.colors
    const bg = { current: 'currentColor', off: c.lampOff, live: c.live, ready: c.lampOff }[tone]
    return { width: '.65em', height: '.65em', borderRadius: '50%', flex: 'none', display: 'inline-block', background: bg, ...(blink ? blinking : {}) }
  },
)

export type PillTone = 'soft' | 'hot' | 'live' | 'new' | 'team'

/** Non-interactive label pill: topics, states, periods, team tags. */
export function Pill({ tone = 'soft', dot, label, ...rest }: { tone?: PillTone; dot?: boolean; label: ReactNode } & Omit<ChipProps, 'variant' | 'label'>) {
  return (
    <Chip
      variant={tone}
      label={<>{dot && <StatusDot blink />}{label}</>}
      {...rest}
    />
  )
}

/** Keyboard shortcut hint inside a button (Enter, Esc). */
export const KeyHint = styled('kbd')({
  display: 'inline-flex', alignItems: 'center', height: '1.6em', font: 'inherit', fontSize: '.7em', fontWeight: 700,
  padding: '0 .5em', borderRadius: 5, border: '1.5px solid currentColor', opacity: 0.8, letterSpacing: '.04em',
})

/** Editor salience as a bar plus its number. */
export function SalienceMeter({ value, label }: { value: number; label: string }) {
  return (
    <>
      <LinearProgress variant="determinate" value={Math.round(value * 100)} aria-hidden sx={{ flex: 1 }} />
      <Box component="span" sx={{ flex: 'none', fontWeight: 600 }}>{label} {value.toFixed(2)}</Box>
    </>
  )
}

/** Dashed placeholder panel with a big decorative word and a message. */
export function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Box
      sx={(theme) => ({
        p: '28px 24px', display: 'flex', flexDirection: 'column', gap: '10px', background: theme.custom.colors.surface,
        border: `1.5px dashed ${theme.custom.colors.line}`, borderRadius: `${theme.custom.radii.panel}px`,
      })}
    >
      <Typography variant="display" aria-hidden sx={(theme) => ({ fontSize: '2.6em', color: theme.custom.prefs.highContrast ? theme.custom.colors.ink : theme.custom.colors.tint })}>
        {title}
      </Typography>
      <Typography sx={{ color: 'text.secondary', m: 0 }}>{message}</Typography>
    </Box>
  )
}
