import { Box, Stack, Typography } from '@mui/material'
import type { ComponentProps } from 'react'
import type { Strings } from '../../i18n'
import { EmptyState } from '../ui/primitives'
import { FeedCard, type CardDragHandlers, type FeedItem } from './FeedCard'
import { FeedFilters } from './FeedFilters'

interface Props {
  t: Strings
  items: FeedItem[]
  emptyText: string
  filters: Omit<ComponentProps<typeof FeedFilters>, 't'>
  onPick: (id: string) => void
  drag: CardDragHandlers
}

/** Ranked insight feed; it scrolls inside its own column on desktop. New cards are announced politely. */
export function InsightFeed({ t, items, emptyText, filters, onPick, drag }: Props) {
  return (
    <Stack
      component="aside"
      aria-labelledby="feed-h"
      spacing="10px"
      sx={(theme) => ({ minHeight: 0, height: '100%', minWidth: 0, [theme.custom.media.stacked]: { height: 'auto' } })}
    >
      <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '12px' }}>
        <Typography variant="label" component="h2" id="feed-h" sx={{ m: 0 }}>{t.feed}</Typography>
        <Typography variant="hint" component="span">{items.length} {t.cards}</Typography>
      </Box>
      <FeedFilters t={t} {...filters} />
      {items.length === 0 && <EmptyState title={t.waiting} message={emptyText} />}
      <Box
        component="ol"
        aria-live="polite"
        aria-relevant="additions"
        sx={(theme) => ({
          listStyle: 'none', m: 0, p: '2px 6px 16px 2px', display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', flex: 1, minHeight: 0,
          [theme.custom.media.stacked]: { overflow: 'visible' },
        })}
      >
        {items.map((item) => <FeedCard key={item.card.id} item={item} t={t} onPick={onPick} drag={drag} />)}
      </Box>
      <Typography variant="hint" id="feed-tip">{t.feedTip}</Typography>
    </Stack>
  )
}
