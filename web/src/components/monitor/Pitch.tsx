import { styled } from '@mui/material/styles'

const Svg = styled('svg')(({ theme }) => ({
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
  display: 'block',
  fill: 'none',
  stroke: theme.custom.colors.pitchLine,
  strokeWidth: 2,
  '& *': { vectorEffect: 'non-scaling-stroke' },
  '& .spot': { fill: theme.custom.colors.pitchSpot, stroke: 'none' },
}))

/** Regulation pitch drawn to real proportions (105 × 68 m) inside a 16:9 frame. Decorative. */
export function Pitch() {
  return (
    <Svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <rect x="21.5" y="7" width="117" height="76" />
      <line x1="80" y1="7" x2="80" y2="83" />
      <circle cx="80" cy="45" r="10.2" />
      <circle className="spot" cx="80" cy="45" r=".7" />
      <rect x="21.5" y="22.5" width="18.4" height="45" />
      <rect x="21.5" y="34.78" width="6.15" height="20.45" />
      <circle className="spot" cx="33.8" cy="45" r=".7" />
      <path d="M39.9 36.83 A10.2 10.2 0 0 1 39.9 53.17" />
      <rect x="19.3" y="40.9" width="2.2" height="8.2" />
      <rect x="120.1" y="22.5" width="18.4" height="45" />
      <rect x="132.35" y="34.78" width="6.15" height="20.45" />
      <circle className="spot" cx="126.2" cy="45" r=".7" />
      <path d="M120.1 36.83 A10.2 10.2 0 0 0 120.1 53.17" />
      <rect x="138.5" y="40.9" width="2.2" height="8.2" />
      <path d="M22.6 7 A1.1 1.1 0 0 1 21.5 8.1M138.5 8.1 A1.1 1.1 0 0 1 137.4 7M21.5 81.9 A1.1 1.1 0 0 1 22.6 83M137.4 83 A1.1 1.1 0 0 1 138.5 81.9" />
    </Svg>
  )
}
