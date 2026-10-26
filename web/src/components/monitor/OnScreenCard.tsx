import { ButtonBase } from '@mui/material'
import { styled } from '@mui/material/styles'
import { useRef, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import type { Strings } from '../../i18n'
import { clamp, type Geo } from '../../state'
import { blinking } from '../../theme/theme'
import { emit, rise } from '../../theme/motion'
import type { CardText, FeedCard, Team } from '../../types'
import { Silhouette } from '../Silhouette'
import { CloseIcon, MoveIcon } from '../ui/icons'
import { StatusDot } from '../ui/primitives'

const LIMITS = { minW: 22, maxW: 70, minH: 14, maxH: 80, top: 4, snap: 1.5 }
type Mode = 'prev' | 'pend' | 'live'

// ---- Styled parts (all colors from theme tokens)

const Overlay = styled('div', { shouldForwardProp: (p) => !['mode', 'fixedHeight', 'editable', 'moving'].includes(p as string) })<{
  mode: Mode
  fixedHeight: boolean
  editable?: boolean
  moving?: boolean
}>(({ theme, mode, fixedHeight, editable, moving }) => {
  const c = theme.custom.colors
  const hc = theme.custom.prefs.highContrast
  return {
    position: 'absolute',
    display: 'flex',
    flexDirection: 'column',
    borderRadius: '1.4cqw',
    background: mode === 'prev' ? c.preview : c.card,
    color: mode === 'prev' ? c.previewInk : c.cardInk,
    pointerEvents: editable ? 'auto' : 'none',
    cursor: editable ? (moving ? 'grabbing' : 'grab') : undefined,
    touchAction: editable ? 'none' : undefined,
    animation: `${rise} ${theme.custom.motion.overlayIn} both`,
    ...(hc ? { border: `3px solid ${c.ink}` } : {}),
    ...(mode === 'prev' && { outline: `.2cqw dashed ${c.previewOutline}`, outlineOffset: '.45cqw' }),
    ...(mode === 'pend' && { outline: `.3cqw solid ${c.live}`, outlineOffset: '.35cqw' }),
    ...(mode === 'live' && {
      boxShadow: `0 0 0 .3cqw ${c.live}`,
      // Recording-light pulse; removed with every other animation under reduce motion.
      '&::after': {
        content: '""', position: 'absolute', inset: '-.3cqw', borderRadius: '1.7cqw', border: `.3cqw solid ${c.live}`, pointerEvents: 'none',
        animation: `${emit} ${theme.custom.motion.emit} ease-out infinite`,
        ...(theme.custom.prefs.reduceMotion ? { display: 'none' } : {}),
        '@media (prefers-reduced-motion: reduce)': { display: 'none' },
      },
    }),
    '& .ob': fixedHeight ? { flex: 1, minHeight: 0, overflow: 'hidden' } : {},
  }
})

const Badge = styled('span', { shouldForwardProp: (p) => p !== 'live' })<{ live: boolean }>(({ theme, live }) => ({
  position: 'absolute', left: 0, bottom: 'calc(100% + .55em)', display: 'inline-flex', alignItems: 'center', gap: '.45em',
  fontSize: 'max(11px, .78em)', fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', padding: '.3em .75em',
  borderRadius: theme.custom.radii.pill, color: theme.custom.colors.onBrand, whiteSpace: 'nowrap',
  background: live ? theme.custom.colors.live : theme.custom.colors.grey,
  '& .dot': live ? blinking : {},
}))

const Body = styled('div')({ display: 'flex', gap: '1.1em', padding: '1.2em 1.4em 1.3em', alignItems: 'flex-start', flex: 1, minHeight: 0 })
const TextCol = styled('div')({ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', minHeight: 0, height: '100%' })
const Who = styled('span')(({ theme }) => ({ ...theme.typography.display, fontSize: '1.05em', letterSpacing: '.04em', opacity: 0.85 }))
const Headline = styled('p')(({ theme }) => ({ ...theme.typography.display, fontSize: '2.2em', margin: '.2em 0 .25em' }))
const BodyText = styled('p')({ margin: 0, fontSize: '1em', lineHeight: 1.3 })

const Field = styled('textarea')(({ theme }) => ({
  display: 'block', width: 'calc(100% + .4em)', border: 0, background: 'transparent', color: 'inherit', font: 'inherit',
  padding: '.08em .2em', margin: '0 -.2em', resize: 'none', borderRadius: '.4cqw', fieldSizing: 'content', overflow: 'hidden', cursor: 'text',
  '&:hover': { background: theme.custom.colors.textHover },
  '&:focus': { outline: `.18cqw solid ${theme.custom.colors.brand}`, outlineOffset: 0, background: theme.custom.colors.surface },
}))
const HeadlineField = styled(Field)(({ theme }) => ({ ...theme.typography.display, fontSize: '2.2em', margin: '.2em -.2em .25em' }))
const BodyField = styled(Field)({ lineHeight: 1.3 })

const CornerButton = styled(ButtonBase)(({ theme }) => ({
  position: 'absolute', width: 30, height: 30, borderRadius: '50%', zIndex: 3, pointerEvents: 'auto',
  background: theme.custom.colors.handle, color: theme.custom.colors.onHandle, border: `2px solid ${theme.custom.colors.onHandle}`,
  '& svg': { width: 14, height: 14 },
  // Invisible padding brings the 30px button to a 44px touch target.
  '&::before': { content: '""', position: 'absolute', inset: -7 },
}))

const Grip = styled(ButtonBase)(({ theme }) => ({
  position: 'absolute', zIndex: 2, pointerEvents: 'auto', touchAction: 'none',
  background: theme.custom.colors.brand, border: `2px solid ${theme.custom.colors.onHandle}`,
  // Invisible padding brings the thin bars and the corner dot to ≥ 44px touch targets.
  '&::before': { content: '""', position: 'absolute', inset: -16 },
}))
const gripShape = {
  x: { top: '50%', right: -7, width: 12, height: 44, marginTop: '-22px', borderRadius: 6, cursor: 'ew-resize' },
  y: { left: '50%', bottom: -7, width: 44, height: 12, marginLeft: '-22px', borderRadius: 6, cursor: 'ns-resize' },
  xy: { right: -11, bottom: -11, width: 22, height: 22, borderRadius: '50%', cursor: 'nwse-resize' },
} as const

// ---- Shared pieces

function geoStyle(g: Geo): CSSProperties {
  return {
    left: `${g.x.toFixed(2)}%`,
    top: `${g.y.toFixed(2)}%`,
    width: `${g.width}%`,
    // Text scales with the card's width.
    fontSize: `${(g.width * 0.0325).toFixed(3)}cqw`,
    ...(g.height ? { height: `${g.height}%` } : {}),
  }
}

interface FaceProps {
  card: FeedCard
  team: Team
  t: Strings
  /** Decorative duplicate (countdown) hidden from assistive tech. */
  silent?: boolean
  children: ReactNode
}

/** Silhouette or shield, the "who" line, then the text (static or editable). */
function CardFace({ card, team, t, silent, children }: FaceProps) {
  return (
    <Body>
      <Silhouette team={team} player={card.player} t={t} hidden={silent} size="5.2em" radius=".9em" />
      <TextCol>
        <Who>{card.player ? `#${card.player.num} ${card.player.name}` : team.name}</Who>
        {children}
      </TextCol>
    </Body>
  )
}

// ---- Public components

interface StaticProps {
  card: FeedCard
  team: Team
  geo: Geo
  text: CardText
  mode: 'pend' | 'live'
  badge: string
  t: Strings
}

/** The card as viewers see it: during the countdown (silent duplicate) or locked on air. */
export function StaticCard({ card, team, geo, text, mode, badge, t }: StaticProps) {
  const pend = mode === 'pend'
  return (
    <Overlay mode={mode} fixedHeight={!!geo.height} style={{ zIndex: pend ? 3 : 2, ...geoStyle(geo) }} aria-hidden={pend || undefined}>
      <Badge live><StatusDot className="dot" />{badge}</Badge>
      <CardFace card={card} team={team} t={t} silent={pend}>
        <Headline>{text.h}</Headline>
        <BodyText className="ob">{text.b}</BodyText>
      </CardFace>
    </Overlay>
  )
}

interface EditProps {
  card: FeedCard
  team: Team
  geo: Geo
  text: CardText
  t: Strings
  moving: boolean
  onGeo: (geo: Partial<Geo>) => void
  onText: (text: CardText) => void
  onRemove: () => void
  onMoving: (moving: boolean, guide: boolean) => void
}

interface DragStart { x0: number; y0: number; sx: number; sy: number; wp: number; hp: number; sw: number; sh: number; moved: boolean; target: Element }
type GripKind = keyof typeof gripShape
interface GripStart { kind: GripKind; x: number; y: number; w: number; h: number; sw: number; sh: number }

function rects(el: Element) {
  return { card: el.closest('[data-overlay]')!.getBoundingClientRect(), stage: el.closest('[role="region"]')!.getBoundingClientRect() }
}

/** Preview card: drag to place (snaps to center), edit text in place, resize with handles or arrow keys. */
export function EditableCard({ card, team, geo, text, t, moving, onGeo, onText, onRemove, onMoving }: EditProps) {
  const drag = useRef<DragStart | null>(null)
  const grip = useRef<GripStart | null>(null)
  const sizeNow = `${geo.width}% × ${geo.height ? `${geo.height}%` : 'auto'}`

  const down = (e: PointerEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (e.button !== 0 || target.closest('[data-control]')) return
    // A press inside the focused text field selects text instead of dragging.
    if (target.tagName === 'TEXTAREA' && document.activeElement === target) return
    const { card: r, stage: st } = rects(e.currentTarget)
    drag.current = {
      x0: e.clientX, y0: e.clientY, sx: geo.x, sy: geo.y,
      wp: (r.width / st.width) * 100, hp: (r.height / st.height) * 100, sw: st.width, sh: st.height, moved: false, target,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
    e.preventDefault()
  }

  const move = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current
    if (!d) return
    if (!d.moved && Math.hypot(e.clientX - d.x0, e.clientY - d.y0) < 4) return
    d.moved = true
    let x = clamp(d.sx + ((e.clientX - d.x0) / d.sw) * 100, 0, 100 - d.wp)
    const y = clamp(d.sy + ((e.clientY - d.y0) / d.sh) * 100, LIMITS.top, 100 - d.hp)
    const guide = Math.abs(x + d.wp / 2 - 50) < LIMITS.snap
    if (guide) x = 50 - d.wp / 2
    onGeo({ x, y })
    onMoving(true, guide)
  }

  const up = () => {
    const d = drag.current
    if (!d) return
    drag.current = null
    // A press that didn't move on the text means "edit": focus it with the caret at the end.
    if (!d.moved && d.target instanceof HTMLTextAreaElement) {
      d.target.focus()
      d.target.setSelectionRange(d.target.value.length, d.target.value.length)
    }
    onMoving(false, false)
  }

  const moveKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const step = e.shiftKey ? 10 : 2
    const delta = ({ ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] } as Record<string, number[]>)[e.key]
    if (!delta) return
    e.preventDefault()
    e.stopPropagation()
    const { card: r, stage: st } = rects(e.currentTarget)
    onGeo({
      x: clamp(geo.x + delta[0], 0, 100 - (r.width / st.width) * 100),
      y: clamp(geo.y + delta[1], LIMITS.top, 100 - (r.height / st.height) * 100),
    })
  }

  const gripProps = (kind: GripKind, label: string, hint: string) => ({
    'data-control': true,
    'aria-label': `${label}, ${sizeNow}. ${hint}`,
    sx: gripShape[kind],
    onPointerDown: (e: PointerEvent<HTMLButtonElement>) => {
      const { card: r, stage: st } = rects(e.currentTarget)
      grip.current = { kind, x: e.clientX, y: e.clientY, w: r.width, h: r.height, sw: st.width, sh: st.height }
      e.currentTarget.setPointerCapture(e.pointerId)
      e.preventDefault()
      e.stopPropagation()
    },
    onPointerMove: (e: PointerEvent<HTMLButtonElement>) => {
      const g = grip.current
      if (!g) return
      const next: Partial<Geo> = {}
      if (g.kind !== 'y') next.width = Math.round(clamp(((g.w + e.clientX - g.x) / g.sw) * 100, LIMITS.minW, Math.min(LIMITS.maxW, 100 - geo.x)))
      if (g.kind !== 'x') next.height = Math.round(clamp(((g.h + e.clientY - g.y) / g.sh) * 100, LIMITS.minH, Math.min(LIMITS.maxH, 100 - geo.y)))
      onGeo(next)
    },
    onPointerUp: () => { grip.current = null },
    onKeyDown: (e: KeyboardEvent<HTMLButtonElement>) => {
      const { card: r, stage: st } = rects(e.currentTarget)
      const h0 = geo.height ?? Math.round((r.height / st.height) * 100)
      const next: Partial<Geo> = {}
      if (kind !== 'y' && (e.key === 'ArrowRight' || e.key === 'ArrowLeft'))
        next.width = clamp(geo.width + (e.key === 'ArrowRight' ? 2 : -2), LIMITS.minW, Math.min(LIMITS.maxW, 100 - geo.x))
      if (kind !== 'x' && (e.key === 'ArrowUp' || e.key === 'ArrowDown'))
        next.height = clamp(h0 + (e.key === 'ArrowDown' ? 2 : -2), LIMITS.minH, Math.min(LIMITS.maxH, 100 - geo.y))
      if (Object.keys(next).length) {
        e.preventDefault()
        e.stopPropagation()
        onGeo(next)
      }
    },
  })

  return (
    <Overlay
      data-overlay
      mode="prev"
      editable
      moving={moving}
      fixedHeight={!!geo.height}
      style={{ zIndex: 3, ...geoStyle(geo) }}
      role="group"
      aria-label={t.editCard}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
    >
      <Badge live={false}><StatusDot />{t.bPreview}</Badge>
      <CardFace card={card} team={team} t={t}>
        <HeadlineField
          aria-label={t.headline} rows={1} maxLength={60} value={text.h}
          onChange={(e) => onText({ ...text, h: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              e.currentTarget.blur()
            }
          }}
        />
        <BodyField className="ob" aria-label={t.body} rows={2} maxLength={180} value={text.b} onChange={(e) => onText({ ...text, b: e.target.value })} />
      </CardFace>
      <CornerButton data-control aria-label={t.removePrev} onClick={onRemove} sx={(theme) => ({ top: -15, right: -15, '&:hover': { background: theme.custom.colors.live } })}>
        <CloseIcon />
      </CornerButton>
      <CornerButton aria-label={`${t.move}. ${t.arrowsMove}`} onKeyDown={moveKey} sx={(theme) => ({ bottom: -15, left: -15, cursor: 'inherit', '&:hover': { background: theme.custom.colors.brand } })}>
        <MoveIcon />
      </CornerButton>
      <Grip {...gripProps('x', t.resizeW, t.arrowsW)} />
      <Grip {...gripProps('y', t.resizeH, t.arrowsH)} />
      <Grip {...gripProps('xy', t.resizeXY, t.arrowsXY)} />
    </Overlay>
  )
}
