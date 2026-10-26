import type { ReactNode, Ref } from 'react'
import type { Strings } from '../i18n'
import type { Team } from '../types'

// Regulation pitch drawn to real proportions (105 × 68 m) inside a 16:9 frame.
function Pitch() {
  const spot = 'rgba(255,255,255,.55)'
  return (
    <svg className="pitch" viewBox="0 0 160 90" preserveAspectRatio="xMidYMid meet" aria-hidden="true" fill="none" stroke="rgba(255,255,255,.4)" strokeWidth="2">
      <rect x="21.5" y="7" width="117" height="76" />
      <line x1="80" y1="7" x2="80" y2="83" />
      <circle cx="80" cy="45" r="10.2" />
      <circle cx="80" cy="45" r=".7" fill={spot} stroke="none" />
      <rect x="21.5" y="22.5" width="18.4" height="45" />
      <rect x="21.5" y="34.78" width="6.15" height="20.45" />
      <circle cx="33.8" cy="45" r=".7" fill={spot} stroke="none" />
      <path d="M39.9 36.83 A10.2 10.2 0 0 1 39.9 53.17" />
      <rect x="19.3" y="40.9" width="2.2" height="8.2" />
      <rect x="120.1" y="22.5" width="18.4" height="45" />
      <rect x="132.35" y="34.78" width="6.15" height="20.45" />
      <circle cx="126.2" cy="45" r=".7" fill={spot} stroke="none" />
      <path d="M120.1 36.83 A10.2 10.2 0 0 0 120.1 53.17" />
      <rect x="138.5" y="40.9" width="2.2" height="8.2" />
      <path d="M22.6 7 A1.1 1.1 0 0 1 21.5 8.1M138.5 8.1 A1.1 1.1 0 0 1 137.4 7M21.5 81.9 A1.1 1.1 0 0 1 22.6 83M137.4 83 A1.1 1.1 0 0 1 138.5 81.9" />
    </svg>
  )
}

interface Props {
  t: Strings
  label: string
  outputName: string
  home: Team
  away: Team
  score: string
  minute: string
  onAir: boolean
  showKickoff: boolean
  kickoffHint: string
  guide: boolean
  /** Feed drag in progress: null, or whether the pointer is over the monitor. */
  drop: { over: boolean } | null
  children: ReactNode
  ref: Ref<HTMLDivElement>
}

export function ProgramMonitor({
  t, label, outputName, home, away, score, minute, onAir, showKickoff, kickoffHint, guide, drop, children, ref,
}: Props) {
  const dropCls = drop ? ` drop${drop.over ? ' over' : ''}` : ''
  return (
    <div ref={ref} className={`stage${dropCls}`} role="region" aria-label={label}>
      <div className="stripes" aria-hidden="true" />
      <Pitch />
      <div className="bug">
        <span style={{ background: home.color, color: home.ink }}>{home.short}</span>
        <span className="sc">{score}</span>
        <span style={{ background: away.color, color: away.ink }}>{away.short}</span>
        <span className="mn">{minute}</span>
      </div>
      <div className={`pgm${onAir ? ' on' : ''}`}>
        <span className={`dot${onAir ? ' blink' : ''}`} />
        {outputName}{onAir ? ` · ${t.onAir}` : ''}
      </div>
      {showKickoff && (
        <div className="kickoff">
          <span className="disp">{t.kickoff}</span>
          <span>{kickoffHint}</span>
        </div>
      )}
      {children}
      {guide && <div className="vguide" aria-hidden="true" />}
      {drop && <div className="drophint" aria-hidden="true">{drop.over ? t.release : t.dragTo}</div>}
    </div>
  )
}
