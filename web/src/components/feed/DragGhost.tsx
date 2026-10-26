import { Box, Typography } from '@mui/material'

interface Props {
  x: number
  y: number
  over: boolean
  meta: string
  headline: string
  hint: string
}

/** Follows the pointer while a feed card is dragged; tilts until it is over the monitor. Decorative. */
export function DragGhost({ x, y, over, meta, headline, hint }: Props) {
  return (
    <Box
      aria-hidden
      style={{ left: x, top: y }}
      sx={(theme) => {
        const c = theme.custom.colors
        return {
          position: 'fixed', zIndex: 30, width: 260, pointerEvents: 'none', translate: '-50% -35%', rotate: over ? '0deg' : '-2deg',
          background: c.card, color: c.cardInk, border: `2px ${over ? 'solid' : 'dashed'} ${c.brand}`, borderRadius: '16px',
          p: '12px 14px', display: 'flex', flexDirection: 'column', gap: '6px',
          '& .accent': { fontWeight: 700, color: c.brand },
        }
      }}
    >
      <Typography component="span" className="accent" sx={{ fontSize: '.78em', letterSpacing: '.1em', textTransform: 'uppercase' }}>{meta}</Typography>
      <Typography variant="display" sx={{ fontSize: '1.35em' }}>{headline}</Typography>
      <Typography component="span" className="accent" sx={{ fontSize: '.78em', fontWeight: 600 }}>{hint}</Typography>
    </Box>
  )
}
