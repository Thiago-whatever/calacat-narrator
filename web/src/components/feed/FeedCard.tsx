import { Box, Card, CardActionArea, Typography } from '@mui/material'
import type { PointerEvent } from 'react'
import { minutes, topicLabel, type Strings } from '../../i18n'
import { pop } from '../../theme/motion'
import type { CardText, FeedCard as FeedCardData, Team } from '../../types'
import { Silhouette } from '../Silhouette'
import { Pill, SalienceMeter } from '../ui/primitives'

export interface FeedItem {
  card: FeedCardData
  team: Team
  text: CardText
  meta: string
  isNew: boolean
  liveOn: string[]
  selected: boolean
  /** Live on the selected output: locked, only Pull from air acts on it. */
  locked: boolean
  lifted: boolean
}

export interface CardDragHandlers {
  down: (e: PointerEvent<HTMLButtonElement>, id: string) => void
  move: (e: PointerEvent<HTMLButtonElement>) => void
  up: (e: PointerEvent<HTMLButtonElement>) => void
  cancel: () => void
}

interface Props {
  item: FeedItem
  t: Strings
  onPick: (id: string) => void
  drag: CardDragHandlers
}

/** One insight: click to preview it on the monitor, or drag it onto a spot. */
export function FeedCard({ item, t, onPick, drag }: Props) {
  const { card, team, text, meta, isNew, liveOn, selected, locked, lifted } = item
  return (
    <Card
      component="li"
      sx={(theme) => {
        const c = theme.custom.colors
        return {
          flex: 'none',
          animation: `${pop} ${theme.custom.motion.cardIn} both`,
          transition: 'opacity .15s',
          opacity: lifted ? 0.45 : 1,
          ...(selected && { borderColor: c.brand, boxShadow: `inset 0 0 0 1.5px ${c.brand}` }),
          ...(locked && { background: c.liveSoft }),
          '&:hover': { borderColor: selected ? c.brand : locked ? c.line : c.ink2 },
        }
      }}
    >
      <CardActionArea
        data-card-id={card.id}
        aria-pressed={selected}
        aria-disabled={locked}
        aria-describedby="feed-tip"
        onClick={() => !locked && onPick(card.id)}
        onPointerDown={(e) => drag.down(e, card.id)}
        onPointerMove={drag.move}
        onPointerUp={drag.up}
        onPointerCancel={drag.cancel}
        sx={{ p: '.9em 1.1em 1em', cursor: locked ? 'default' : 'grab', touchAction: 'pan-y', display: 'block', '& .MuiCardActionArea-focusHighlight': { display: 'none' } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '7px', flexWrap: 'wrap' }}>
          <Pill tone="team" label={team.short} />
          <Pill tone={card.critical ? 'hot' : 'soft'} label={topicLabel(t, card.topic)} />
          <Typography component="span" sx={{ fontSize: '.8em', fontWeight: 600, color: 'text.secondary' }}>{minutes(card.clock)}</Typography>
          <Box sx={{ flex: 1 }} />
          {isNew && <Pill tone="new" label={t.new} />}
          {liveOn.length > 0 && <Pill tone="live" dot label={`${t.live} · ${liveOn.join(', ')}`} />}
        </Box>
        <Box sx={{ display: 'flex', gap: '12px', alignItems: 'flex-start', mt: '.6em' }}>
          <Silhouette team={team} player={card.player} t={t} size="46px" radius="10px" />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography component="span" sx={{ display: 'block', fontSize: '.78em', fontWeight: 700, letterSpacing: '.04em' }}>
              {card.player ? `#${card.player.num} ${card.player.name} · ${team.name}` : team.name}
            </Typography>
            <Typography variant="display" sx={{ display: 'block', fontSize: '1.45em', m: '.15em 0 .35em' }}>{text.h}</Typography>
            <Typography component="span" sx={{ display: 'block', fontSize: '.9em', color: 'text.secondary' }}>{text.b}</Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: { xs: 'wrap', sm: 'nowrap' }, mt: '.8em', fontSize: '.75em', color: 'text.secondary' }}>
          <Box component="span" sx={{ flex: { xs: '1 1 100%', sm: 'none' } }}>{meta}</Box>
          <SalienceMeter value={card.salience} label={t.salience} />
        </Box>
      </CardActionArea>
    </Card>
  )
}
