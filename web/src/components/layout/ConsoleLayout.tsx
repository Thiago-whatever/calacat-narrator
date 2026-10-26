import { styled } from '@mui/material/styles'

/** Whole console. One viewport with no page scroll on desktop; a scrolling column when stacked (ADR-032). */
export const ConsoleRoot = styled('div', { shouldForwardProp: (p) => p !== 'dragging' })<{ dragging: boolean }>(({ theme, dragging }) => ({
  fontFamily: theme.typography.fontFamily,
  fontSize: theme.custom.fontSize,
  lineHeight: 1.35,
  color: theme.custom.colors.ink,
  background: theme.custom.colors.bg,
  height: '100dvh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
  ...(dragging && { '&, & *': { cursor: 'grabbing !important', userSelect: 'none' } }),
  [theme.custom.media.stacked]: { height: 'auto', minHeight: '100dvh', overflow: 'visible' },
}))

/** Monitor column, capped by viewport height so monitor and control bar always fit, then the feed. */
export const ConsoleMain = styled('main')(({ theme }) => ({
  flex: 1,
  minHeight: 0,
  display: 'grid',
  gridTemplateColumns: `minmax(0, calc((100dvh - ${theme.custom.chrome}px) * 16 / 9)) minmax(360px, 1fr)`,
  gap: 20,
  padding: '16px 24px',
  alignItems: 'start',
  [theme.custom.media.stacked]: { gridTemplateColumns: 'minmax(0, 1fr)' },
  [theme.custom.media.phone]: { padding: '12px 16px' },
}))

export const MonitorColumn = styled('section')({ display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 })
