import type { AirCard, Geo } from '../state'
import type { CardText, FeedCard, Team } from '../types'

/** What the overlay view needs to draw one output's on-air card; a snapshot, so it never looks anything up. */
export interface OverlayCard {
  id: string
  card: FeedCard
  team: Team
  geo: Geo
  text: CardText
}

export interface OverlayOutput {
  id: string
  name: string
}

/**
 * Console ⇄ overlay messages between tabs of the same browser (ADR-043): go-live never leaves the browser.
 * A new overlay says `hello`; the console answers with `state`, and sends it again after every change.
 */
export type OnAirMessage =
  | { type: 'hello' }
  | { type: 'state'; outputs: OverlayOutput[]; onAir: Record<string, OverlayCard | null> }

const CHANNEL = 'calacat-on-air'

export function onAirState(outputs: OverlayOutput[], onAir: Record<string, AirCard | null>, teams: Record<string, Team>): OnAirMessage {
  const cards: Record<string, OverlayCard | null> = {}
  for (const { id } of outputs) {
    const air = onAir[id]
    const team = air && teams[air.card.team]
    cards[id] = air && team
      ? { id: air.id, card: air.card, team, geo: { x: air.x, y: air.y, width: air.width, height: air.height }, text: { h: air.h, b: air.b } }
      : null
  }
  return { type: 'state', outputs: outputs.map(({ id, name }) => ({ id, name })), onAir: cards }
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null
const isString = (v: unknown): v is string => typeof v === 'string'
const isNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

function isOverlayCard(v: unknown): v is OverlayCard {
  if (!isObject(v) || !isString(v.id) || !isObject(v.card) || !isObject(v.team) || !isObject(v.geo) || !isObject(v.text)) return false
  const { card, team, geo, text } = v
  return (
    isString(card.id) && isString(card.topic) && isNumber(card.clock) &&
    isString(team.name) && isString(team.color) && isString(team.ink) && isString(team.soft) && isString(team.short) &&
    isNumber(geo.x) && isNumber(geo.y) && isNumber(geo.width) && (geo.height === null || isNumber(geo.height)) &&
    isString(text.h) && isString(text.b)
  )
}

/** Same-origin only, but still checked: another tab of this site could run a different build. */
export function parseOnAirMessage(data: unknown): OnAirMessage | null {
  if (!isObject(data)) return null
  if (data.type === 'hello') return { type: 'hello' }
  if (data.type !== 'state' || !Array.isArray(data.outputs) || !isObject(data.onAir)) return null
  const outputs = data.outputs.filter((o): o is OverlayOutput => isObject(o) && isString(o.id) && isString(o.name))
  const onAir: Record<string, OverlayCard | null> = {}
  for (const [id, card] of Object.entries(data.onAir)) onAir[id] = isOverlayCard(card) ? card : null
  return { type: 'state', outputs, onAir }
}

export interface OnAirChannel {
  post: (message: OnAirMessage) => void
  close: () => void
}

/** BroadcastChannel, or the `storage` event where it's missing; both stay inside this browser. */
export function openOnAirChannel(onMessage: (message: OnAirMessage) => void): OnAirChannel {
  const deliver = (data: unknown) => {
    const message = parseOnAirMessage(data)
    if (message) onMessage(message)
  }
  if (typeof BroadcastChannel !== 'undefined') {
    const channel = new BroadcastChannel(CHANNEL)
    channel.onmessage = (event) => deliver(event.data)
    return { post: (message) => channel.postMessage(message), close: () => channel.close() }
  }
  const onStorage = (event: StorageEvent) => {
    if (event.key !== CHANNEL || !event.newValue) return
    try {
      deliver((JSON.parse(event.newValue) as { message?: unknown }).message)
    } catch {
      // Not ours: ignore.
    }
  }
  window.addEventListener('storage', onStorage)
  return {
    post: (message) => {
      try {
        // A changing nonce makes every post a change, so other tabs always get the event.
        localStorage.setItem(CHANNEL, JSON.stringify({ message, nonce: `${Date.now()}-${Math.random()}` }))
      } catch {
        // Storage blocked: the overlay tab stays empty, the console is unaffected.
      }
    },
    close: () => window.removeEventListener('storage', onStorage),
  }
}
