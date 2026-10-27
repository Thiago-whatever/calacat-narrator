import { Box, Button, Typography } from '@mui/material'
import { styled } from '@mui/material/styles'
import { useEffect, useRef, useState } from 'react'
import { openOnAirChannel, type OverlayCard, type OverlayOutput } from '../../data/onAirChannel'
import type { Strings } from '../../i18n'
import type { ThemePrefs } from '../../theme/theme'
import type { Lang } from '../../types'
import { ViewPrefs } from '../header/Header'
import { StaticCard } from '../monitor/OnScreenCard'
import { LiveRegion, Pill, StatusDot } from '../ui/primitives'
import { SegmentedControl } from '../ui/SegmentedControl'

// Before the console answers, the overlay still offers the demo's outputs.
const DEFAULT_OUTPUTS: OverlayOutput[] = [
  { id: 'o1', name: 'TV 1' },
  { id: 'o2', name: 'TV 2' },
  { id: 'o3', name: 'Stream' },
]

// Room left for the header, tally strip and note, so the 16:9 stage fits the window's height.
const STAGE_WIDTH = 'min(100%, calc((100dvh - 230px) * 16 / 9))'

/** Program-sized key: only the on-air card is drawn on it, scaled like the console's monitor (cqw). Red-framed while on air. */
const Stage = styled('div', { shouldForwardProp: (p) => p !== 'live' })<{ live: boolean }>(({ theme, live }) => ({
  position: 'relative',
  aspectRatio: '16 / 9',
  width: STAGE_WIDTH,
  margin: '0 auto',
  overflow: 'hidden',
  borderRadius: theme.custom.radii.card,
  background: theme.custom.colors.stage,
  containerType: 'inline-size',
  outline: `4px solid ${live ? theme.custom.colors.live : 'transparent'}`,
  outlineOffset: 3,
}))

/** Broadcast tally above the stage: ON AIR in red, or OFF AIR, with what is showing. */
function TallyStrip({ live, label, detail }: { live: boolean; label: string; detail: string }) {
  return (
    <Box
      sx={(theme) => ({
        width: STAGE_WIDTH, mx: 'auto', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', p: '8px 14px',
        borderRadius: `${theme.custom.radii.panel}px`, color: theme.custom.colors.onBrand,
        background: live ? theme.custom.colors.live : theme.custom.colors.tallyOff,
      })}
    >
      <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase' }}>
        <StatusDot blink={live} />
        {label}
      </Box>
      <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0, flex: '1 1 12em' }}>{detail}</Box>
    </Box>
  )
}

interface Props {
  t: Strings
  lang: Lang
  onLang: (lang: Lang) => void
  prefs: ThemePrefs
  onPrefs: (prefs: ThemePrefs) => void
  output: string
  onOutput: (id: string) => void
  consoleHref: string
}

/**
 * Overlay view (C14, ADR-043): the card on air for one output, fed by the console in another tab of
 * this browser. Nothing goes over the network; it resets when the console reloads. It is the viewers'
 * side, so it says so: a "what viewers see" tag, a broadcast tally and no editing controls.
 */
export function OverlayView({ t, lang, onLang, prefs, onPrefs, output, onOutput, consoleHref }: Props) {
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
        <div>
          <Typography variant="display" component="h1" sx={{ fontSize: '1.4em', m: 0 }}>
            {t.overlay} · {name}
          </Typography>
          <Pill tone="hot" label={t.overlayTag} sx={{ mt: '6px' }} />
        </div>
        <SegmentedControl label={t.output} compact segments={outputs.map((o) => ({ value: o.id, label: o.name }))} value={output} onChange={onOutput} />
        <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', ml: { sm: 'auto' } }}>
          <Button component="a" href={consoleHref}>{t.backToConsole}</Button>
          <ViewPrefs t={t} lang={lang} onLang={onLang} prefs={prefs} onPrefs={onPrefs} />
        </Box>
      </Box>
      <main>
        <TallyStrip live={!!air} label={`${air ? t.onAir : t.offAir} · ${name}`} detail={air ? air.text.h : t.overlayEmpty} />
        <Stage live={!!air} aria-label={`${t.overlay} · ${name}`} role="region" sx={{ mt: '14px' }}>
          {air && <StaticCard card={air.card} team={air.team} geo={air.geo} text={air.text} mode="live" badge={t.bLive} t={t} />}
        </Stage>
        <Typography variant="hint" sx={{ width: STAGE_WIDTH, mx: 'auto', mt: '12px', display: 'block' }}>{t.overlayNote}</Typography>
      </main>
    </Box>
  )
}
