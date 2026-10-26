// Design tokens from DOCS/design.md (ADR-031). The only place raw colors and sizes are defined.

export interface ColorTokens {
  bg: string
  surface: string
  tint: string
  ink: string
  ink2: string
  line: string
  brand: string
  onBrand: string
  live: string
  liveSoft: string
  grey: string
  stage: string
  focus: string
  /** Decoration only (drop targets, guides, kick-off title). Never text on light. */
  bubblegum: string
  /** On-screen card faces: what viewers see, independent of the console theme. */
  card: string
  cardInk: string
  preview: string
  previewInk: string
  previewOutline: string
  handle: string
  onHandle: string
  bugDark: string
  bugLight: string
  grassA: string
  grassB: string
  pitchLine: string
  pitchSpot: string
  lampOff: string
  meterTrack: string
  dropFill: string
  tallyOff: string
  textHover: string
}

const light: ColorTokens = {
  bg: '#fff8f6',
  surface: '#ffffff',
  tint: '#fce5df',
  ink: '#00522d',
  ink2: '#3d6b55',
  line: '#efd9d3',
  brand: '#c0256f',
  onBrand: '#ffffff',
  live: '#d7261e',
  liveSoft: '#fff1f0',
  grey: '#6b6b6b',
  stage: '#0f2a1c',
  focus: '#c0256f',
  bubblegum: '#f29ebd',
  card: '#fff8f6',
  cardInk: '#00522d',
  preview: '#ececec',
  previewInk: '#3a3a3a',
  previewOutline: '#a3a3a3',
  handle: '#1a1a1a',
  onHandle: '#ffffff',
  bugDark: '#0d1712',
  bugLight: '#fff8f6',
  grassA: '#14351f',
  grassB: '#173c24',
  pitchLine: 'rgba(255,255,255,.4)',
  pitchSpot: 'rgba(255,255,255,.55)',
  lampOff: '#bdbdbd',
  meterTrack: '#efd9d3',
  dropFill: 'rgba(242,158,189,.1)',
  tallyOff: 'rgba(0,0,0,.5)',
  textHover: 'rgba(0,0,0,.05)',
}

// High contrast: black on white, darker brand and live (design.md).
const highContrast: ColorTokens = {
  ...light,
  bg: '#ffffff',
  surface: '#ffffff',
  tint: '#ffffff',
  ink: '#000000',
  ink2: '#000000',
  line: '#000000',
  brand: '#7d0a43',
  live: '#b00000',
  liveSoft: '#ffffff',
  grey: '#333333',
  stage: '#000000',
  focus: '#000000',
  card: '#ffffff',
  cardInk: '#000000',
  preview: '#ffffff',
  previewInk: '#000000',
  grassA: '#000000',
  grassB: '#000000',
  meterTrack: '#cccccc',
}

export const palettes = { light, highContrast }

export const fonts = {
  display: "'Antonio', sans-serif",
  body: "'Instrument Sans', system-ui, sans-serif",
}

/** Base font size; everything else is in em so the whole console scales with "Larger text". */
export const baseFontSize = { normal: 15, large: 17 }

export const radii = { button: 10, large: 14, card: 18, panel: 20, pill: 999 }

/** Touch targets: ≥ 44px everywhere, 56px in the control bar. */
export const sizes = { target: 44, targetLarge: 56, xlMinWidth: 196 }

export const motion = {
  cardIn: '.45s cubic-bezier(.2,.8,.2,1)',
  overlayIn: '.4s cubic-bezier(.2,.8,.2,1)',
  blink: '1.2s',
  emit: '1.6s',
  countdownMs: 5000,
}

/** MUI breakpoints: `sm` starts just above the phone layout, `lg` where the console stops stacking. */
export const breakpoints = { xs: 0, sm: 641, md: 768, lg: 1100, xl: 1536 }

/** Below ~1100px wide or ~560px tall the console stacks into one scrolling column (ADR-032). */
export const media = {
  stacked: '@media (max-width: 1099.95px), (max-height: 560px)',
  phone: '@media (max-width: 640px)',
}

/** Vertical space taken by header, control bar and gaps; the monitor's width is capped by what's left. */
export const chrome = { normal: 284, large: 326 }
