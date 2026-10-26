import type { Strings } from '../i18n'
import { fonts } from '../theme/tokens'
import type { Player, Team } from '../types'

interface Props {
  team: Team
  player?: Player
  t: Strings
  /** CSS length, e.g. "46px" in the feed or "5.2em" on the monitor. */
  size: string
  radius: string
  /** Decorative copies (e.g. the countdown overlay) are hidden from assistive tech. */
  hidden?: boolean
}

function label(t: Strings, team: Team, player?: Player) {
  return player ? `${t.player} ${player.name}, ${team.name}, ${t.jersey} ${player.num}` : `${t.team} ${team.name}`
}

/** Team color appears only here: a player silhouette with jersey number, or a team shield (ADR-035). */
export function Silhouette({ team, player, t, size, radius, hidden }: Props) {
  const a11y = hidden ? { 'aria-hidden': true } : { role: 'img', 'aria-label': label(t, team, player) }
  const style = { width: size, height: size, flex: 'none', display: 'block', borderRadius: radius }
  const number = { textAnchor: 'middle', fontWeight: 700, fontFamily: fonts.display, fill: team.ink } as const
  return (
    <svg viewBox="0 0 48 48" style={style} {...a11y}>
      {player ? (
        <>
          <rect width="48" height="48" fill={team.soft} />
          <circle cx="24" cy="15.5" r="7.5" fill={team.color} />
          <path d="M7 48c0-11 7.5-18.5 17-18.5S41 37 41 48z" fill={team.color} />
          <text x="24" y="44.5" fontSize="11" {...number}>{player.num}</text>
        </>
      ) : (
        <>
          <path d="M24 3l18 6.5v13.5c0 11.5-8 19.5-18 22-10-2.5-18-10.5-18-22V9.5z" fill={team.color} />
          <text x="24" y="29" fontSize="10.5" {...number}>{team.short}</text>
        </>
      )}
    </svg>
  )
}
