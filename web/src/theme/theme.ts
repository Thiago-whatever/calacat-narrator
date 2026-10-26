import { createTheme, type CSSObject, type Theme } from '@mui/material/styles'
import { blink } from './motion'
import { baseFontSize, breakpoints, chrome, fonts, media, motion, palettes, radii, sizes, type ColorTokens } from './tokens'

export interface ThemePrefs {
  highContrast: boolean
  largeText: boolean
  reduceMotion: boolean
}

interface Custom {
  colors: ColorTokens
  prefs: ThemePrefs
  fontSize: number
  chrome: number
  media: typeof media
  radii: typeof radii
  sizes: typeof sizes
  motion: typeof motion
}

declare module '@mui/material/styles' {
  interface Theme {
    custom: Custom
  }
  interface ThemeOptions {
    custom?: Custom
  }
  interface TypographyVariants {
    display: CSSObject
    label: CSSObject
    hint: CSSObject
  }
  interface TypographyVariantsOptions {
    display?: CSSObject
    label?: CSSObject
    hint?: CSSObject
  }
}

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    display: true
    label: true
    hint: true
  }
}

declare module '@mui/material/Button' {
  interface ButtonPropsVariantOverrides {
    solid: true
  }
  interface ButtonPropsSizeOverrides {
    xl: true
  }
}

declare module '@mui/material/Chip' {
  interface ChipPropsVariantOverrides {
    soft: true
    hot: true
    live: true
    new: true
    team: true
  }
}

/** Visible 3px focus ring on every control (design.md, Accessibility). */
export const focusRing = (theme: Theme): CSSObject => ({
  '&:focus-visible, &.Mui-focusVisible': { outline: `3px solid ${theme.custom.colors.focus}`, outlineOffset: 2 },
})

export const srOnly: CSSObject = {
  position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap',
}

export const blinking: CSSObject = { animation: `${blink} ${motion.blink} infinite` }

export function createAppTheme(prefs: ThemePrefs): Theme {
  const c = prefs.highContrast ? palettes.highContrast : palettes.light
  const custom: Custom = {
    colors: c,
    prefs,
    fontSize: prefs.largeText ? baseFontSize.large : baseFontSize.normal,
    chrome: prefs.largeText ? chrome.large : chrome.normal,
    media,
    radii,
    sizes,
    motion,
  }
  const display: CSSObject = { fontFamily: fonts.display, fontWeight: 700, letterSpacing: '.01em', textTransform: 'uppercase', lineHeight: 0.95 }
  const hc = prefs.highContrast

  return createTheme({
    custom,
    palette: {
      primary: { main: c.brand, contrastText: c.onBrand },
      error: { main: c.live },
      text: { primary: c.ink, secondary: c.ink2 },
      background: { default: c.bg, paper: c.surface },
      divider: c.line,
    },
    breakpoints: { values: breakpoints },
    shape: { borderRadius: radii.button },
    typography: {
      fontFamily: fonts.body,
      // Component text is sized in em against the console root, so "Larger text" scales everything.
      allVariants: { fontSize: '1em' },
      display,
      label: { fontSize: '.74em', fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: c.ink2 },
      hint: { fontSize: '.78em', color: c.ink2, margin: 0 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: { body: { backgroundColor: c.bg } },
      },
      MuiTypography: {
        defaultProps: { variantMapping: { display: 'span', label: 'span', hint: 'p' } },
      },
      // Flat UI: no ripples or elevation; every control gets the 3px focus ring.
      MuiButtonBase: {
        defaultProps: { disableRipple: true },
        styleOverrides: { root: ({ theme }) => focusRing(theme) },
      },
      MuiButton: {
        defaultProps: { disableElevation: true, variant: 'outlined', color: 'inherit' },
        styleOverrides: {
          root: {
            font: 'inherit',
            fontWeight: 600,
            height: sizes.target,
            padding: '0 1.1em',
            borderRadius: radii.button,
            textTransform: 'none',
            whiteSpace: 'nowrap',
            lineHeight: 1,
            gap: '.55em',
            '& svg': { width: 18, height: 18, flex: 'none' },
            '&.Mui-disabled': { opacity: 0.38 },
            variants: [
              {
                props: { variant: 'outlined' },
                style: {
                  border: `1.5px solid ${c.line}`, background: c.surface, color: c.ink,
                  '&:hover': { borderColor: c.ink, background: c.surface },
                  '&.Mui-disabled': { borderColor: c.line, color: c.ink },
                },
              },
              {
                props: { variant: 'contained' },
                style: {
                  background: c.brand, color: c.onBrand, border: `1.5px solid ${c.brand}`,
                  '&:hover': { background: c.brand, filter: 'brightness(.9)' },
                  '&.Mui-disabled': { background: c.brand, color: c.onBrand },
                },
              },
              {
                props: { variant: 'solid' },
                style: {
                  background: c.ink, color: c.onBrand, border: `1.5px solid ${c.ink}`,
                  '&:hover': { background: c.ink, filter: 'brightness(1.25)' },
                },
              },
              {
                props: { size: 'xl' },
                style: {
                  height: sizes.targetLarge, padding: '0 1.5em', fontSize: '1.05em', borderRadius: radii.large,
                  minWidth: sizes.xlMinWidth, borderWidth: 2, '& svg': { width: 20, height: 20 },
                },
              },
              {
                // Large outlined buttons have an ink border that fills on hover.
                props: { size: 'xl', variant: 'outlined' },
                style: {
                  borderColor: c.ink,
                  '&:hover': { background: c.ink, color: c.onBrand },
                  '&.Mui-disabled': { borderColor: c.ink },
                },
              },
            ],
          },
        },
      },
      MuiToggleButtonGroup: {
        styleOverrides: { root: { gap: 6, flexWrap: 'wrap' }, grouped: { margin: 0, '&&': { borderRadius: radii.button, border: `1.5px solid ${c.line}` } } },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            font: 'inherit',
            textTransform: 'none',
            height: sizes.target,
            padding: '0 .9em',
            gap: '.55em',
            color: c.ink,
            background: c.surface,
            whiteSpace: 'nowrap',
            '&:hover': { borderColor: c.ink, background: c.surface },
            '&.Mui-selected, &.Mui-selected:hover': { background: c.ink, color: c.onBrand, borderColor: c.ink },
            '&.Mui-disabled': { opacity: 0.45, color: c.ink },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            font: 'inherit',
            fontSize: '.78em',
            fontWeight: 600,
            height: 'auto',
            padding: '.28em .8em',
            borderRadius: radii.pill,
            gap: '.45em',
            '& .MuiChip-label': { padding: 0, display: 'inline-flex', alignItems: 'center', gap: '.45em' },
            ...(hc ? { border: `1px solid ${c.ink}` } : {}),
            variants: [
              { props: { variant: 'soft' }, style: { background: c.tint, color: c.ink } },
              { props: { variant: 'hot' }, style: { background: c.brand, color: c.onBrand } },
              { props: { variant: 'live' }, style: { background: c.live, color: c.onBrand } },
              { props: { variant: 'new' }, style: { background: 'transparent', border: `1.5px solid ${c.brand}`, color: c.brand } },
              {
                props: { variant: 'team' },
                style: { borderRadius: 6, fontSize: '.74em', fontWeight: 700, letterSpacing: '.06em', padding: '.3em .6em', background: c.tint, color: c.ink },
              },
            ],
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            font: 'inherit',
            fontWeight: 600,
            borderRadius: radii.button,
            background: c.surface,
            color: c.ink,
            '& .MuiOutlinedInput-notchedOutline': { border: `1.5px solid ${c.line}` },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: c.ink },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { border: `3px solid ${c.focus}` },
          },
        },
      },
      MuiSelect: {
        styleOverrides: {
          // `&&` beats MUI's own input height so selects match the 44px buttons.
          select: { '&&': { height: sizes.target, minHeight: 0, boxSizing: 'border-box', display: 'flex', alignItems: 'center', padding: '0 2.2em 0 1em' } },
          icon: { color: c.ink },
        },
      },
      MuiMenuItem: {
        styleOverrides: { root: { minHeight: sizes.target, color: c.ink } },
      },
      MuiListSubheader: {
        styleOverrides: { root: { fontSize: '.74em', fontWeight: 600, letterSpacing: '.08em', textTransform: 'uppercase', color: c.ink2, lineHeight: '36px' } },
      },
      MuiCheckbox: {
        defaultProps: { color: 'primary' },
        styleOverrides: { root: { color: c.ink2, padding: 12 } },
      },
      MuiFormControlLabel: {
        styleOverrides: { root: { minHeight: sizes.target, margin: 0, gap: 4 }, label: { font: 'inherit', fontWeight: 500 } },
      },
      MuiPopover: {
        styleOverrides: { paper: { borderRadius: radii.panel, border: `1.5px solid ${c.line}`, boxShadow: 'none', padding: 14, width: 270 } },
      },
      MuiMenu: {
        styleOverrides: { paper: { borderRadius: radii.large, border: `1.5px solid ${c.line}`, boxShadow: 'none' } },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { height: 4, borderRadius: 4, backgroundColor: c.meterTrack },
          bar: { backgroundColor: c.ink, borderRadius: 4 },
        },
      },
      MuiSnackbarContent: {
        styleOverrides: {
          root: {
            font: 'inherit',
            background: c.ink,
            color: c.onBrand,
            borderRadius: 16,
            padding: '12px 12px 12px 14px',
            flexWrap: 'nowrap',
            boxShadow: 'none',
            ...(hc ? { outline: `3px solid ${c.surface}` } : {}),
          },
          message: { flex: 1, minWidth: 0, padding: 0, display: 'flex', alignItems: 'center', gap: 14 },
          action: { marginRight: 0, paddingLeft: 14 },
        },
      },
      MuiCard: {
        defaultProps: { variant: 'outlined' },
        styleOverrides: { root: { borderRadius: radii.card, border: `1.5px solid ${c.line}`, background: c.surface } },
      },
    },
  })
}
