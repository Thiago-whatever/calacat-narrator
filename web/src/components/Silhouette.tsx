import { useState } from 'react'
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

const initials = (name: string) =>
  name
    .split(/\s+/)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

// Players without a generated avatar 404 once; remember them so cards don't request again.
const missingAvatars = new Set<string>()
const avatarUrl = (playerId: string) => `${import.meta.env.BASE_URL}players/${encodeURIComponent(playerId)}.png`

/**
 * Player avatar (ADR-041): `public/players/{player_id}.png` when it exists, otherwise the team-colored
 * silhouette with the jersey number (ADR-035), or initials when there is no number. Team cards get the shield.
 * Team color appears only here (ADR-035).
 */
export function Silhouette({ team, player, t, size, radius, hidden }: Props) {
  // Keyed by player so a reused component (the on-screen card) re-checks when the card changes.
  const [failedFor, setFailedFor] = useState<string | null>(null)
  const failed = !player || failedFor === player.id || missingAvatars.has(player.id)
  const a11y = hidden ? { 'aria-hidden': true } : { role: 'img', 'aria-label': label(t, team, player) }
  const style = { width: size, height: size, flex: 'none', display: 'block', borderRadius: radius }

  if (player && !failed) {
    return (
      <img
        src={avatarUrl(player.id)}
        alt={hidden ? '' : label(t, team, player)}
        aria-hidden={hidden || undefined}
        style={{ ...style, objectFit: 'cover', background: team.soft }}
        onError={() => {
          missingAvatars.add(player.id)
          setFailedFor(player.id)
        }}
      />
    )
  }

  const text = { textAnchor: 'middle', fontWeight: 700, fontFamily: fonts.display, fill: team.ink } as const
  return (
    <svg viewBox="0 0 48 48" style={style} {...a11y}>
      {player ? (
        <>
          <rect width="48" height="48" fill={team.soft} />
          <circle cx="24" cy="15.5" r="7.5" fill={team.color} />
          <path d="M7 48c0-11 7.5-18.5 17-18.5S41 37 41 48z" fill={team.color} />
          <text x="24" y="44.5" fontSize="11" {...text}>{player.num || initials(player.name)}</text>
        </>
      ) : (
        <>
          <path d="M24 3l18 6.5v13.5c0 11.5-8 19.5-18 22-10-2.5-18-10.5-18-22V9.5z" fill={team.color} />
          <text x="24" y="29" fontSize="10.5" {...text}>{team.short}</text>
        </>
      )}
    </svg>
  )
}
