import { Box, Button, Typography } from '@mui/material'
import type { Strings } from '../../i18n'
import type { ThemePrefs } from '../../theme/theme'
import type { Lang } from '../../types'
import { LogoIcon, PauseIcon, PlayIcon } from '../ui/icons'
import { Pill } from '../ui/primitives'
import { SelectField } from '../ui/SelectField'
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
  outputs: OutputOption[]
  output: string
  onOutput: (id: string) => void
  period: string
}

const LANGUAGES = [{ options: [{ value: 'en', label: 'English' }, { value: 'es', label: 'Español' }] }]

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

export function Header({ t, lang, onLang, prefs, onPrefs, run, liveStatus, outputs, output, onOutput, period }: Props) {
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
          <Button variant="contained" onClick={run.onToggle} startIcon={run.running ? <PauseIcon /> : <PlayIcon />} sx={{ minWidth: { sm: 150 }, gridColumn: '1 / -1' }}>
            {run.label}
          </Button>
        )}
        <SelectField label={t.lang} hideLabel value={lang} onChange={(v) => onLang(v as Lang)} groups={LANGUAGES} sx={{ width: { xs: '100%', sm: 'auto' } }} />
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
