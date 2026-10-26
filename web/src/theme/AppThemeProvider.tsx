import { CssBaseline, GlobalStyles } from '@mui/material'
import { ThemeProvider } from '@mui/material/styles'
import { useMemo, type ReactNode } from 'react'
import { createAppTheme, type ThemePrefs } from './theme'

const noMotion = { animation: 'none !important', transition: 'none !important' }

/** Theme + baseline + the global motion rule; the live ring stays solid without its pulse. */
export function AppThemeProvider({ prefs, children }: { prefs: ThemePrefs; children: ReactNode }) {
  const theme = useMemo(() => createAppTheme(prefs), [prefs])
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <GlobalStyles
        styles={{
          '*, *::before, *::after': prefs.reduceMotion ? noMotion : {},
          '@media (prefers-reduced-motion: reduce)': { '*, *::before, *::after': noMotion },
        }}
      />
      {children}
    </ThemeProvider>
  )
}
