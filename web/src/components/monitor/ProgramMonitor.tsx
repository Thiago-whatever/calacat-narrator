import { Box, Typography } from '@mui/material'
import { styled } from '@mui/material/styles'
import type { ReactNode, Ref } from 'react'
import type { Team } from '../../types'
import { StatusDot } from '../ui/primitives'
import { Pitch } from './Pitch'

const Stage = styled('div', { shouldForwardProp: (p) => p !== 'drop' })<{ drop: 'none' | 'armed' | 'over' }>(({ theme, drop }) => {
  const c = theme.custom.colors
  return {
    position: 'relative',
    aspectRatio: '16 / 9',
    width: '100%',
    borderRadius: theme.custom.radii.card,
    overflow: 'hidden',
    background: c.stage,
    // Everything inside scales with the monitor's width (cqw).
    containerType: 'inline-size',
    color: c.onBrand,
    '&::after': {
      content: '""', position: 'absolute', inset: 0, borderRadius: theme.custom.radii.card, pointerEvents: 'none', zIndex: 6,
      border: `3px ${drop === 'over' ? 'solid' : 'dashed'} ${drop === 'none' ? 'transparent' : c.bubblegum}`,
      background: drop === 'over' ? c.dropFill : 'transparent',
      transition: 'border-color .15s, background .15s',
    },
  }
})

const Grass = styled('div')(({ theme }) => ({
  position: 'absolute',
  inset: 0,
  background: `repeating-linear-gradient(90deg, ${theme.custom.colors.grassA} 0 8.33%, ${theme.custom.colors.grassB} 8.33% 16.66%)`,
}))

const corner = { position: 'absolute', top: '4%', zIndex: 1, display: 'flex', fontWeight: 700 } as const

function ScoreBug({ home, away, score, minute }: { home: Team; away: Team; score: string; minute: string }) {
  const cell = { padding: '.45em .8em' }
  return (
    <Box sx={(theme) => ({ ...corner, left: '3%', fontSize: '1.45cqw', borderRadius: '.6cqw', overflow: 'hidden', letterSpacing: '.04em', '& > span': cell, '& .sc': { background: theme.custom.colors.bugLight, color: theme.custom.colors.bugDark }, '& .mn': { background: theme.custom.colors.bugDark, color: theme.custom.colors.onBrand } })}>
      <span style={{ background: home.color, color: home.ink }}>{home.short}</span>
      <span className="sc">{score}</span>
      <span style={{ background: away.color, color: away.ink }}>{away.short}</span>
      <span className="mn">{minute}</span>
    </Box>
  )
}

function Tally({ label, onAir }: { label: string; onAir: boolean }) {
  return (
    <Box
      sx={(theme) => ({
        ...corner, right: '3%', alignItems: 'center', gap: '.6em', fontSize: '1.1cqw', letterSpacing: '.12em', padding: '.5em .9em',
        borderRadius: `${theme.custom.radii.pill}px`, textTransform: 'uppercase', background: onAir ? theme.custom.colors.live : theme.custom.colors.tallyOff,
      })}
    >
      <StatusDot blink={onAir} />
      {label}
    </Box>
  )
}

interface Props {
  label: string
  tally: string
  onAir: boolean
  home: Team
  away: Team
  score: string
  minute: string
  /** Before kick-off: big title and a hint. */
  kickoff?: { title: string; hint: string }
  guide: boolean
  /** Feed drag in progress: null, or whether the pointer is over the monitor. */
  drop: { over: boolean; hint: string } | null
  children: ReactNode
  ref: Ref<HTMLDivElement>
}

/** Stand-in for the selected output's video: pitch, score bug, tally, and the on-screen cards as children. */
export function ProgramMonitor({ label, tally, onAir, home, away, score, minute, kickoff, guide, drop, children, ref }: Props) {
  return (
    <Stage ref={ref} role="region" aria-label={label} drop={drop ? (drop.over ? 'over' : 'armed') : 'none'}>
      <Grass aria-hidden />
      <Pitch />
      <ScoreBug home={home} away={away} score={score} minute={minute} />
      <Tally label={tally} onAir={onAir} />
      {kickoff && (
        <Box sx={(theme) => ({ position: 'absolute', left: '5%', bottom: '11%', display: 'flex', flexDirection: 'column', gap: '1.4cqw', maxWidth: '60%', fontSize: '1.6cqw', color: theme.custom.colors.bugLight })}>
          <Typography variant="display" sx={(theme) => ({ fontSize: '5em', color: theme.custom.colors.bubblegum })}>{kickoff.title}</Typography>
          <span>{kickoff.hint}</span>
        </Box>
      )}
      {children}
      {guide && (
        <Box aria-hidden sx={(theme) => ({ position: 'absolute', left: '50%', top: 0, bottom: 0, borderLeft: `1.5px dashed ${theme.custom.colors.bubblegum}`, zIndex: 4, pointerEvents: 'none' })} />
      )}
      {drop && (
        <Box
          aria-hidden
          sx={(theme) => ({
            position: 'absolute', left: '50%', top: '50%', translate: '-50% -50%', zIndex: 5, pointerEvents: 'none', fontSize: '1.6cqw', fontWeight: 700,
            padding: '.6em 1.1em', borderRadius: `${theme.custom.radii.pill}px`, background: theme.custom.colors.brand, color: theme.custom.colors.onBrand,
          })}
        >
          {drop.hint}
        </Box>
      )}
    </Stage>
  )
}
