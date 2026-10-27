import { Box, Button, Typography } from '@mui/material'
import type { Strings } from '../../i18n'
import type { ThemePrefs } from '../../theme/theme'
import type { Lang } from '../../types'
import { LogoIcon, PauseIcon, PlayIcon } from '../ui/icons'
import { Pill } from '../ui/primitives'
import { SegmentedControl } from '../ui/SegmentedControl'
import { AccessibilityMenu } from './AccessibilityMenu'
import { OutputSwitcher, type OutputOption } from './OutputSwitcher'

interface Props {
  t: Strings
  lang: Lang
  onLang: (lang: Lang) => void
  prefs: ThemePrefs
  onPrefs: (prefs: ThemePrefs) => void
  /** Demo only: Start / Pause / Resume / Restart drives the simulated clock. Omitted in live mode. */
  run?: { label: string; running: boolean; onToggle: () => void }
  liveStatus?: string
  /** Opens the overlay view for the selected output in a new tab (C14). */
  overlay: { label: string; href: string }
  /** Live builds only: starts a match on the server (C16); `message` is its status, announced politely. */
  start?: { label: string; busy: boolean; message: string; onStart: () => void }
  outputs: OutputOption[]
  output: string
  onOutput: (id: string) => void
  period: string
}

const LANGUAGES = [
  { value: 'en' as const, label: 'EN', ariaLabel: 'English' },
  { value: 'es' as const, label: 'ES', ariaLabel: 'Español' },
]

function Brand({ sub }: { sub: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: '12px', flex: { xs: '1 1 auto', sm: '0 1 230px' } }}>
      <Box
        aria-hidden
        sx={(theme) => ({
          width: theme.custom.sizes.target, height: theme.custom.sizes.target, borderRadius: '50%', flex: 'none',
          background: theme.custom.colors.brand, color: theme.custom.colors.onBrand, display: 'grid', placeItems: 'center',
        })}
      >
        <LogoIcon />
      </Box>
      <div>
        <Typography variant="display" component="h1" sx={{ fontSize: '1.5em', m: 0 }}>Calacat Narrator</Typography>
        <Typography sx={{ fontSize: '.8em', color: 'text.secondary' }}>{sub}</Typography>
      </div>
    </Box>
  )
}

export function Header({ t, lang, onLang, prefs, onPrefs, run, liveStatus, start, overlay, outputs, output, onOutput, period }: Props) {
  return (
    <Box
      component="header"
      sx={(theme) => ({
        flex: 'none', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: { xs: '12px', sm: '12px 24px' },
        px: { xs: 2, sm: 3 }, py: '12px', borderBottom: `1.5px solid ${theme.custom.colors.line}`,
      })}
    >
      <Brand sub={t.sub} />
      <OutputSwitcher label={t.output} liveText={t.outLive} offText={t.outOff} outputs={outputs} value={output} onChange={onOutput}>
        <Pill label={period} />
        {liveStatus && <Pill label={liveStatus} role="status" />}
      </OutputSwitcher>
      <Box
        sx={{
          display: { xs: 'grid', sm: 'flex' }, gridTemplateColumns: '1fr auto', alignItems: 'center', gap: '10px',
          flexWrap: 'wrap', ml: { xs: 0, sm: 'auto' }, width: { xs: '100%', sm: 'auto' },
        }}
      >
        {run && (
          // Next to Start live match, the demo is the secondary action, so the two never look alike.
          <Button variant={start ? 'outlined' : 'contained'} onClick={run.onToggle} startIcon={run.running ? <PauseIcon /> : <PlayIcon />} sx={{ minWidth: { sm: 150 }, gridColumn: '1 / -1' }}>
            {run.label}
          </Button>
        )}
        {start && (
          // aria-disabled, not disabled, so keyboard focus stays on the button while it works.
          <Button variant="contained" onClick={start.busy ? undefined : start.onStart} aria-disabled={start.busy} startIcon={<PlayIcon />} sx={{ gridColumn: '1 / -1' }}>
            {start.label}
          </Button>
        )}
        {start && (
          <Typography role="status" sx={{ gridColumn: '1 / -1', fontSize: '.85em', maxWidth: { sm: 260 } }}>
            {start.message}
          </Typography>
        )}
        <Button component="a" href={overlay.href} target="_blank" rel="noopener" sx={{ gridColumn: '1 / -1' }}>{overlay.label}</Button>
        {/* Switches the interface and the cards (English, or the Reviewer's Spanish), and is remembered. */}
        <SegmentedControl label={t.lang} hideLabel compact segments={LANGUAGES} value={lang} onChange={onLang} />
        <AccessibilityMenu
          label={t.a11y}
          options={{ highContrast: t.hc, largeText: t.lg, reduceMotion: t.rm }}
          shortcuts={t.shortcuts}
          prefs={prefs}
          onChange={onPrefs}
        />
      </Box>
    </Box>
  )
}
