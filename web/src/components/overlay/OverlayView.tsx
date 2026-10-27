import { Box, Button, Typography } from '@mui/material'
import { styled } from '@mui/material/styles'
import { useEffect, useRef, useState } from 'react'
import { openOnAirChannel, type OverlayCard, type OverlayOutput } from '../../data/onAirChannel'
import type { Strings } from '../../i18n'
import { StaticCard } from '../monitor/OnScreenCard'
import { LiveRegion } from '../ui/primitives'
import { SegmentedControl } from '../ui/SegmentedControl'

// Before the console answers, the overlay still offers the demo's outputs.
const DEFAULT_OUTPUTS: OverlayOutput[] = [
  { id: 'o1', name: 'TV 1' },
  { id: 'o2', name: 'TV 2' },
  { id: 'o3', name: 'Stream' },
]

/** Program-sized key: only the on-air card is drawn on it, scaled like the console's monitor (cqw). */
const Stage = styled('div')(({ theme }) => ({
  position: 'relative',
  aspectRatio: '16 / 9',
  width: 'min(100%, calc((100dvh - 120px) * 16 / 9))',
  margin: '0 auto',
  overflow: 'hidden',
  borderRadius: theme.custom.radii.card,
  background: theme.custom.colors.stage,
  containerType: 'inline-size',
}))

interface Props {
  t: Strings
  output: string
  onOutput: (id: string) => void
  consoleHref: string
}

/**
 * Overlay view (C14, ADR-043): the card on air for one output, fed by the console in another tab of
 * this browser. Nothing goes over the network; it resets when the console reloads.
 */
export function OverlayView({ t, output, onOutput, consoleHref }: Props) {
  const [outputs, setOutputs] = useState(DEFAULT_OUTPUTS)
  const [onAir, setOnAir] = useState<Record<string, OverlayCard | null>>({})
  const [announce, setAnnounce] = useState('')
  const lastAnnounced = useRef<string | null | undefined>(undefined)

  useEffect(() => {
    const channel = openOnAirChannel((message) => {
      if (message.type !== 'state') return
      if (message.outputs.length) setOutputs(message.outputs)
      setOnAir(message.onAir)
    })
    channel.post({ type: 'hello' })
    return channel.close
  }, [])

  const name = outputs.find((o) => o.id === output)?.name ?? output
  const air = onAir[output] ?? null

  // Announce changes to this output only, not the first state that arrives.
  useEffect(() => {
    const id = air?.id ?? null
    if (lastAnnounced.current !== undefined && lastAnnounced.current !== id) {
      setAnnounce(air ? `${t.onAir} · ${name}: ${air.text.h}` : `${t.offAir} · ${name}`)
    }
    lastAnnounced.current = id
  }, [air, name, t])

  return (
    <Box
      sx={(theme) => ({
        minHeight: '100dvh', display: 'flex', flexDirection: 'column', gap: '12px', p: { xs: 2, sm: 3 },
        background: theme.custom.colors.bg, color: theme.custom.colors.ink, fontSize: theme.custom.fontSize,
      })}
    >
      <LiveRegion politeness="polite">{announce}</LiveRegion>
      <Box component="header" sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '12px 24px' }}>
        <Typography variant="display" component="h1" sx={{ fontSize: '1.4em', m: 0 }}>
          {t.overlay} · {name}
        </Typography>
        <SegmentedControl label={t.output} compact segments={outputs.map((o) => ({ value: o.id, label: o.name }))} value={output} onChange={onOutput} />
        <Typography sx={{ color: 'text.secondary', fontSize: '.9em' }}>{air ? t.onAir : t.overlayEmpty}</Typography>
        <Button component="a" href={consoleHref} sx={{ ml: { sm: 'auto' } }}>{t.backToConsole}</Button>
      </Box>
      <main>
        <Stage aria-label={`${t.overlay} · ${name}`} role="region">
          {air && <StaticCard card={air.card} team={air.team} geo={air.geo} text={air.text} mode="live" badge={t.bLive} t={t} />}
        </Stage>
      </main>
    </Box>
  )
}
