import { Box, Button, Typography } from '@mui/material'
import { styled } from '@mui/material/styles'
import type { Strings } from '../../i18n'
import { SIZES } from '../../state'
import { blinking, srOnly } from '../../theme/theme'
import { drain } from '../../theme/motion'
import { BroadcastIcon, StopIcon, UndoIcon } from '../ui/icons'
import { KeyHint } from '../ui/primitives'
import { SegmentedControl } from '../ui/SegmentedControl'

export type BarMode = 'idle' | 'ready' | 'pending' | 'air'

const Bar = styled('div', { shouldForwardProp: (p) => p !== 'mode' })<{ mode: BarMode }>(({ theme, mode }) => {
  const c = theme.custom.colors
  return {
    position: 'relative', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', minHeight: 80, overflow: 'hidden',
    padding: '10px 10px 10px 16px', borderRadius: theme.custom.radii.card,
    background: mode === 'pending' ? c.liveSoft : c.surface,
    border: `1.5px solid ${mode === 'pending' || mode === 'air' ? c.live : c.line}`,
    // On 1280–1366px laptops the bar is ~800px wide: drop the key hints and the Size caption
    // (still announced) and tighten the big buttons, so status and actions stay on one row.
    containerType: 'inline-size',
    '@container (max-width: 999.98px)': {
      '& kbd': { display: 'none' },
      '& .segmented-label': srOnly,
      '& .MuiButton-sizeXl': { minWidth: 0, paddingInline: '1em' },
    },
  }
})

const Lamp = styled('span', { shouldForwardProp: (p) => p !== 'mode' })<{ mode: BarMode }>(({ theme, mode }) => {
  const c = theme.custom.colors
  const look = { idle: [c.line, c.ink2], ready: [c.lampOff, c.grey], air: [c.live, c.live], pending: [c.live, c.live] }[mode]
  return { width: 14, height: 14, borderRadius: '50%', flex: 'none', background: look[0], border: `2px solid ${look[1]}`, ...(mode === 'air' ? blinking : {}) }
})

const Countdown = styled('span')(({ theme }) => ({
  ...theme.typography.display, width: theme.custom.sizes.targetLarge, height: theme.custom.sizes.targetLarge, borderRadius: theme.custom.radii.large,
  background: theme.custom.colors.live, color: theme.custom.colors.onBrand, display: 'grid', placeItems: 'center', fontSize: '2em', flex: 'none',
}))

/** Red bar draining over the 5 s countdown (ADR-033). */
const Drain = styled('span')(({ theme }) => ({
  position: 'absolute', left: 0, bottom: 0, height: 5, background: theme.custom.colors.live,
  animation: `${drain} ${theme.custom.motion.countdownMs}ms linear forwards`,
}))

const Actions = styled('div')(({ theme }) => ({
  display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
  [theme.custom.media.phone]: { width: '100%', '& > .MuiButton-root': { flex: '1 1 100%', minWidth: 0 } },
}))

interface Props {
  t: Strings
  title: string
  sub: string
  mode: BarMode
  countdown: number
  /** Selected size preset width, or null for a custom size. */
  sizePreset: number | null
  canEdit: boolean
  canSend: boolean
  canPull: boolean
  liveLabel: string
  onSize: (width: number) => void
  onSend: () => void
  onPull: () => void
  onGoNow: () => void
  onCancel: () => void
}

/** Always directly under the monitor. During the countdown, Go live / Pull become Go live now / Cancel. */
export function ControlBar(p: Props) {
  const { t } = p
  const pending = p.mode === 'pending'
  return (
    <Bar mode={p.mode} role="region" aria-label={t.control}>
      <Box sx={(theme) => ({ display: 'flex', alignItems: 'center', gap: '12px', flex: '1 1 120px', minWidth: 0, minHeight: theme.custom.sizes.targetLarge })}>
        {pending ? <Countdown aria-hidden>{p.countdown}</Countdown> : <Lamp mode={p.mode} aria-hidden />}
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '1.02em' }}>{p.title}</Typography>
          <Typography sx={{ fontSize: '.85em', color: 'text.secondary', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.sub}</Typography>
        </Box>
      </Box>

      {pending ? (
        <>
          <Actions>
            <Button size="xl" onClick={p.onGoNow}>{t.goNow}</Button>
            <Button size="xl" variant="solid" onClick={p.onCancel} startIcon={<UndoIcon />} endIcon={<KeyHint>Esc</KeyHint>}>{t.cancel}</Button>
          </Actions>
          <Drain aria-hidden />
        </>
      ) : (
        <Actions>
          <SegmentedControl
            label={t.size}
            segments={SIZES.map((z) => ({ value: z.width, label: z.label, ariaLabel: t[z.key] }))}
            value={p.sizePreset}
            onChange={p.onSize}
            disabled={!p.canEdit}
          />
          <Button size="xl" disabled={!p.canPull} onClick={p.onPull} startIcon={<StopIcon />}>{t.pull}</Button>
          <Button size="xl" variant="contained" disabled={!p.canSend} onClick={p.onSend} startIcon={<BroadcastIcon />} endIcon={<KeyHint>Enter</KeyHint>}>
            {p.liveLabel}
          </Button>
        </Actions>
      )}
    </Bar>
  )
}
