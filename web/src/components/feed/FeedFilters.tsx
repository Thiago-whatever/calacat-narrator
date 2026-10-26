import { Box, ToggleButton, ToggleButtonGroup } from '@mui/material'
import type { Strings } from '../../i18n'
import type { Player, Team } from '../../types'
import { SelectField } from '../ui/SelectField'

export interface MatchChip {
  id: string
  label: string
  count: number
  program: boolean
}

interface Props {
  t: Strings
  chips: MatchChip[]
  matchFilter: string
  onFilter: (id: string) => void
  focus: string
  onFocus: (focus: string) => void
  teams: Team[]
  players: Player[]
  teamById: Record<string, Team>
}

/** Game filter chips (with the PGM tag on the selected output's match) and the exclusive focus select (ADR-034). */
export function FeedFilters({ t, chips, matchFilter, onFilter, focus, onFocus, teams, players, teamById }: Props) {
  return (
    <>
      <ToggleButtonGroup exclusive value={matchFilter} onChange={(_, id: string | null) => id && onFilter(id)} aria-label={t.games}>
        {chips.map((m) => (
          <ToggleButton
            key={m.id}
            value={m.id}
            sx={(theme) => ({ '&&': { borderRadius: `${theme.custom.radii.pill}px` }, fontSize: '.82em', fontWeight: 600, gap: '.5em', px: '.85em' })}
          >
            <span>{m.label}</span>
            {m.program && (
              <Box component="span" sx={(theme) => ({ fontSize: '.72em', fontWeight: 700, letterSpacing: '.08em', p: '.1em .45em', borderRadius: '4px', background: theme.custom.colors.brand, color: theme.custom.colors.onBrand })}>
                PGM
              </Box>
            )}
            <Box component="span" sx={{ fontSize: '.85em', opacity: 0.75 }}>{m.count}</Box>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      <SelectField
        label={t.focus}
        pill
        sx={{ width: '100%' }}
        value={focus}
        onChange={onFocus}
        groups={[
          { options: [{ value: '', label: t.focusNone }] },
          { label: t.teams, options: teams.map((tm) => ({ value: `team:${tm.id}`, label: tm.name })) },
          { label: t.players, options: players.map((p) => ({ value: `player:${p.id}`, label: `#${p.num} ${p.name} · ${teamById[p.team]?.short ?? ''}` })) },
        ]}
      />
    </>
  )
}
