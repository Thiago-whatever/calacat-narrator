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

/** Fills the row height on desktop so the monitor can take whatever the control bar leaves. */
export const MonitorColumn = styled('section')(({ theme }) => ({
  display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, minHeight: 0, alignSelf: 'stretch',
  // MonitorFit reads this width (cqw) to stop growing once the monitor is width-bound.
  containerType: 'inline-size',
  [theme.custom.media.stacked]: { alignSelf: 'start' },
}))

/**
 * Fits the 16:9 monitor into the height left above the control bar, however tall the bar wraps.
 * `chrome` only estimates the column width; this guarantees the bar stays on screen.
 */
export const MonitorFit = styled('div')(({ theme }) => ({
  flex: 1,
  minHeight: 0,
  // Never taller than a 16:9 monitor at full column width, so the bar sits right under it.
  maxHeight: 'calc(100cqw * 9 / 16)',
  containerType: 'size',
  '& > [role=region]': { width: 'min(100cqw, 100cqh * 16 / 9)' },
  [theme.custom.media.stacked]: { flex: 'none', maxHeight: 'none', containerType: 'normal', '& > [role=region]': { width: '100%' } },
}))
