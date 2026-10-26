import { useRef, type CSSProperties, type KeyboardEvent, type PointerEvent } from 'react'
import type { Strings } from '../i18n'
import { clamp, type Geo } from '../state'
import type { CardText, FeedCard, Team } from '../types'
import { Silhouette } from './Silhouette'

const MIN_W = 22, MAX_W = 70, MIN_H = 14, MAX_H = 80, TOP = 4, SNAP = 1.5

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

const whoLine = (card: FeedCard, team: Team) => (card.player ? `#${card.player.num} ${card.player.name}` : team.name)

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
    <div className={`ov ${geo.height ? 'fixed ' : ''}${mode}`} style={{ zIndex: pend ? 3 : 2, ...geoStyle(geo) }} aria-hidden={pend || undefined}>
      <span className="ovbadge red"><span className="dot" />{badge}</span>
      <div className="ovbd">
        <Silhouette team={team} player={card.player} t={t} className="osil" hidden={pend} />
        <div className="ovtx">
          <span className="opl">{whoLine(card, team)}</span>
          <p className="disp oh">{text.h}</p>
          <p className="ob">{text.b}</p>
        </div>
      </div>
    </div>
  )
}

interface EditProps {
  card: FeedCard
  team: Team
  geo: Geo
  text: CardText
  t: Strings
  onGeo: (geo: Partial<Geo>) => void
  onText: (text: CardText) => void
  onRemove: () => void
  onMoving: (moving: boolean, guide: boolean) => void
  moving: boolean
}

interface DragStart { x0: number; y0: number; sx: number; sy: number; wp: number; hp: number; sw: number; sh: number; moved: boolean; target: Element }
interface GripStart { kind: 'x' | 'y' | 'xy'; x: number; y: number; w: number; h: number; sw: number; sh: number }

function rects(el: Element) {
  const card = el.closest('.ov')!.getBoundingClientRect()
  const stage = el.closest('.stage')!.getBoundingClientRect()
  return { card, stage }
}

/** Preview card: drag to place (snaps to center), edit text in place, resize with handles or arrow keys. */
export function EditableCard({ card, team, geo, text, t, onGeo, onText, onRemove, onMoving, moving }: EditProps) {
  const drag = useRef<DragStart | null>(null)
  const grip = useRef<GripStart | null>(null)
  const sizeNow = `${geo.width}% × ${geo.height ? `${geo.height}%` : 'auto'}`

  const down = (e: PointerEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    if (e.button !== 0 || target.closest('.hd, .ovx')) return
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
    const y = clamp(d.sy + ((e.clientY - d.y0) / d.sh) * 100, TOP, 100 - d.hp)
    const guide = Math.abs(x + d.wp / 2 - 50) < SNAP
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
      y: clamp(geo.y + delta[1], TOP, 100 - (r.height / st.height) * 100),
    })
  }

  const gripDown = (kind: GripStart['kind']) => (e: PointerEvent<HTMLButtonElement>) => {
    const { card: r, stage: st } = rects(e.currentTarget)
    grip.current = { kind, x: e.clientX, y: e.clientY, w: r.width, h: r.height, sw: st.width, sh: st.height }
    e.currentTarget.setPointerCapture(e.pointerId)
    e.preventDefault()
    e.stopPropagation()
  }

  const gripMove = (e: PointerEvent<HTMLButtonElement>) => {
    const g = grip.current
    if (!g) return
    const next: Partial<Geo> = {}
    if (g.kind !== 'y') next.width = Math.round(clamp(((g.w + e.clientX - g.x) / g.sw) * 100, MIN_W, Math.min(MAX_W, 100 - geo.x)))
    if (g.kind !== 'x') next.height = Math.round(clamp(((g.h + e.clientY - g.y) / g.sh) * 100, MIN_H, Math.min(MAX_H, 100 - geo.y)))
    onGeo(next)
  }

  const gripKey = (kind: GripStart['kind']) => (e: KeyboardEvent<HTMLButtonElement>) => {
    const { card: r, stage: st } = rects(e.currentTarget)
    const h0 = geo.height ?? Math.round((r.height / st.height) * 100)
    const next: Partial<Geo> = {}
    if (kind !== 'y' && (e.key === 'ArrowRight' || e.key === 'ArrowLeft'))
      next.width = clamp(geo.width + (e.key === 'ArrowRight' ? 2 : -2), MIN_W, Math.min(MAX_W, 100 - geo.x))
    if (kind !== 'x' && (e.key === 'ArrowUp' || e.key === 'ArrowDown'))
      next.height = clamp(h0 + (e.key === 'ArrowDown' ? 2 : -2), MIN_H, Math.min(MAX_H, 100 - geo.y))
    if (Object.keys(next).length) {
      e.preventDefault()
      e.stopPropagation()
      onGeo(next)
    }
  }

  const gripProps = (kind: GripStart['kind'], label: string, hint: string) => ({
    type: 'button' as const,
    'aria-label': `${label}, ${sizeNow}. ${hint}`,
    onPointerDown: gripDown(kind),
    onPointerMove: gripMove,
    onPointerUp: () => { grip.current = null },
    onKeyDown: gripKey(kind),
  })

  return (
    <div
      className={`ov edit ${geo.height ? 'fixed ' : ''}prev${moving ? ' moving' : ''}`}
      style={{ zIndex: 3, ...geoStyle(geo) }}
      role="group"
      aria-label={t.editCard}
      onPointerDown={down}
      onPointerMove={move}
      onPointerUp={up}
      onPointerCancel={up}
    >
      <span className="ovbadge"><span className="dot" />{t.bPreview}</span>
      <div className="ovbd">
        <Silhouette team={team} player={card.player} t={t} className="osil" />
        <div className="ovtx">
          <span className="opl">{whoLine(card, team)}</span>
          <label className="sr" htmlFor="ov-h">{t.headline}</label>
          <textarea
            id="ov-h" className="ovf disp oh" rows={1} maxLength={60} value={text.h}
            onChange={(e) => onText({ ...text, h: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                e.currentTarget.blur()
              }
            }}
          />
          <label className="sr" htmlFor="ov-b">{t.body}</label>
          <textarea id="ov-b" className="ovf ob" rows={2} maxLength={180} value={text.b} onChange={(e) => onText({ ...text, b: e.target.value })} />
        </div>
      </div>
      <button type="button" className="ovx" aria-label={t.removePrev} onClick={onRemove}>
        <svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M4 4l8 8M12 4l-8 8" /></svg>
      </button>
      <button type="button" className="ovmv" aria-label={`${t.move}. ${t.arrowsMove}`} onKeyDown={moveKey}>
        <svg viewBox="0 0 16 16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M8 1.5v13M1.5 8h13M5.5 4L8 1.5 10.5 4M5.5 12L8 14.5l2.5-2.5M4 5.5L1.5 8 4 10.5M12 5.5L14.5 8 12 10.5" />
        </svg>
      </button>
      <button className="hd hx" {...gripProps('x', t.resizeW, t.arrowsW)} />
      <button className="hd hy" {...gripProps('y', t.resizeH, t.arrowsH)} />
      <button className="hd hxy" {...gripProps('xy', t.resizeXY, t.arrowsXY)} />
    </div>
  )
}
