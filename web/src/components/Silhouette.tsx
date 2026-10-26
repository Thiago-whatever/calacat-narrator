import type { Strings } from '../i18n'
import type { Player, Team } from '../types'

interface Props {
  team: Team
  player?: Player
  t: Strings
  className: string
  /** Decorative copies (e.g. the countdown overlay) are hidden from assistive tech. */
  hidden?: boolean
}

function silhouetteLabel(t: Strings, team: Team, player?: Player) {
  return player ? `${t.player} ${player.name}, ${team.name}, ${t.jersey} ${player.num}` : `${t.team} ${team.name}`
}

/** Team color appears only here: a player silhouette with jersey number, or a team shield (ADR-035). */
export function Silhouette({ team, player, t, className, hidden }: Props) {
  const a11y = hidden ? { 'aria-hidden': true } : { role: 'img', 'aria-label': silhouetteLabel(t, team, player) }
  if (player) {
    return (
      <svg className={className} viewBox="0 0 48 48" {...a11y}>
        <rect width="48" height="48" fill={team.soft} />
        <circle cx="24" cy="15.5" r="7.5" fill={team.color} />
        <path d="M7 48c0-11 7.5-18.5 17-18.5S41 37 41 48z" fill={team.color} />
        <text x="24" y="44.5" textAnchor="middle" fontSize="11" fontWeight="700" fontFamily="Antonio, sans-serif" fill={team.ink}>
          {player.num}
        </text>
      </svg>
    )
  }
  return (
    <svg className={className} viewBox="0 0 48 48" {...a11y}>
      <path d="M24 3l18 6.5v13.5c0 11.5-8 19.5-18 22-10-2.5-18-10.5-18-22V9.5z" fill={team.color} />
      <text x="24" y="29" textAnchor="middle" fontSize="10.5" fontWeight="700" fontFamily="Antonio, sans-serif" fill={team.ink}>
        {team.short}
      </text>
    </svg>
  )
}
