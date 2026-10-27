import type { CardText, FeedCard } from './types'

export const COUNTDOWN_MS = 5000
export const SIZES = [
  { width: 30, label: 'S', key: 'small' },
  { width: 40, label: 'M', key: 'medium' },
  { width: 56, label: 'L', key: 'large' },
] as const

/** Card placement as percentages of the monitor, so it maps to any output resolution. */
export interface Geo {
  x: number
  y: number
  width: number
  height: number | null
}

// Both carry a snapshot of the card, so what's on air still renders after the feed drops it.
// `h`/`b` are the text in the reporter's language; `en` is what viewers get (the output is
// English only), both frozen at send, so nothing reaches air without the countdown.
export interface AirCard extends Geo, CardText {
  id: string
  card: FeedCard
  en: CardText
  since: number
}

export interface Pending extends Geo, CardText {
  id: string
  card: FeedCard
  en: CardText
  output: string
  until: number
}

export interface ConsoleState {
  output: string
  selected: string | null
  geo: Geo
  onAir: Record<string, AirCard | null>
  pending: Pending | null
  toast: string | null
  /** Reporter text edits, keyed `${cardId}:${lang}`. */
  edits: Record<string, CardText>
  matchFilter: string
  focus: string
  announce: string
  polite: string
}

export type Action =
  | { type: 'reset'; output: string }
  | { type: 'setOutput'; output: string }
  | { type: 'select'; id: string; place?: Partial<Geo>; message?: string }
  | { type: 'clearSelection'; message?: string }
  | { type: 'setGeo'; geo: Partial<Geo> }
  | { type: 'setSize'; width: number }
  | { type: 'edit'; key: string; text: CardText }
  | { type: 'send'; card: FeedCard; text: CardText; en: CardText; now: number; message: string }
  | { type: 'cancel'; message: string }
  | { type: 'commit'; now: number }
  | { type: 'pull'; output?: string; message: string }
  | { type: 'dismissToast' }
  | { type: 'setFilter'; match: string }
  | { type: 'setFocus'; focus: string }
  | { type: 'announce'; message: string }

export const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

export function initialState(output: string): ConsoleState {
  return {
    output,
    selected: null,
    geo: { x: 30, y: 62, width: 40, height: null },
    onAir: {},
    pending: null,
    toast: null,
    edits: {},
    matchFilter: 'all',
    focus: '',
    announce: '',
    polite: '',
  }
}

const airOn = (s: ConsoleState, output = s.output) => s.onAir[output] ?? null

export function reducer(s: ConsoleState, a: Action): ConsoleState {
  switch (a.type) {
    case 'reset':
      return { ...initialState(a.output), matchFilter: s.matchFilter, focus: s.focus }
    case 'setOutput': {
      // Switching is disabled during a countdown (ADR-034).
      if (s.pending || a.output === s.output) return s
      const air = airOn(s, a.output)
      return { ...s, output: a.output, selected: air && air.id === s.selected ? null : s.selected }
    }
    case 'select': {
      if (s.pending) return s
      // A card that is live on this output is locked: it can only be pulled (ADR-033).
      if (airOn(s)?.id === a.id) return s
      if (!a.place && s.selected === a.id) return { ...s, selected: null }
      return { ...s, selected: a.id, geo: { ...s.geo, ...a.place }, polite: a.message ?? s.polite }
    }
    case 'clearSelection':
      return { ...s, selected: null, polite: a.message ?? s.polite }
    case 'setGeo':
      return { ...s, geo: { ...s.geo, ...a.geo } }
    case 'setSize':
      return { ...s, geo: { ...s.geo, width: a.width, height: null, x: clamp(s.geo.x, 0, 100 - a.width) } }
    case 'edit':
      return { ...s, edits: { ...s.edits, [a.key]: a.text } }
    case 'send':
      if (!s.selected || s.pending || a.card.id !== s.selected) return s
      // An expired insight may no longer be true, so it can't go to air.
      if (a.card.expiresAt !== undefined && a.card.expiresAt <= a.now) return s
      return {
        ...s,
        pending: { ...s.geo, ...a.text, id: s.selected, card: a.card, en: a.en, output: s.output, until: a.now + COUNTDOWN_MS },
        polite: a.message,
        toast: null,
      }
    case 'cancel':
      return s.pending ? { ...s, pending: null, polite: a.message } : s
    case 'commit': {
      const p = s.pending
      if (!p) return s
      const { output, until: _until, ...card } = p
      return { ...s, onAir: { ...s.onAir, [output]: { ...card, since: a.now } }, pending: null, selected: null, toast: output }
    }
    case 'pull': {
      const output = a.output ?? s.output
      if (!s.onAir[output]) return s
      return { ...s, onAir: { ...s.onAir, [output]: null }, toast: null, announce: a.message }
    }
    case 'dismissToast':
      return { ...s, toast: null }
    case 'setFilter':
      return { ...s, matchFilter: a.match }
    case 'setFocus':
      return { ...s, focus: a.focus }
    case 'announce':
      return { ...s, announce: a.message }
  }
}
