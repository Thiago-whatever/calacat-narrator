import { useEffect, useMemo, useState } from 'react'
import teamsJson from '../../../src/calacat_narrator/data/teams.json'
import playersJson from '../../../src/calacat_narrator/data/players.json'
import type { FeedCard, Match, Output, Phase, Player, Source, Team } from '../types'

// Same pattern as the backend's EntityId (schemas.py); also guards what we put in the URL.
export const MATCH_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/
const CRITICAL_TOPICS = new Set(['goal', 'red_card', 'penalty'])
const MAX_CARDS = 200
const MAX_RETRY_MS = 30_000

export type LiveStatus = 'connecting' | 'open' | 'error'

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}

// WCAG relative luminance decides whether the shield number is white or near-black.
function inkFor(hex: string): string {
  const [r, g, b] = hexToRgb(hex).map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.4 ? '#1a1a1a' : '#ffffff'
}

function softFor(hex: string): string {
  const mix = hexToRgb(hex).map((v) => Math.round(v * 0.2 + 255 * 0.8))
  return `rgb(${mix.join(' ')})`
}

const catalogTeams: Record<string, Team> = Object.fromEntries(
  teamsJson.teams.map((t) => [
    t.id,
    { id: t.id, name: t.name, short: t.short_name, color: t.colors[0], ink: inkFor(t.colors[0]), soft: softFor(t.colors[0]) },
  ]),
)

const catalogPlayers: Player[] = playersJson.players.map((p) => ({ id: p.id, name: p.name, num: p.number, team: p.club_id }))
const playerById = new Map(catalogPlayers.map((p) => [p.id, p]))

/** The subset of the backend `Card` contract (data-model.md) the console reads. */
interface LiveCard {
  card_id: string
  match_id: string
  headline: string
  body: string
  entity_ids: string[]
  topic: string
  salience: number
  source: string
  match_clock_s: number
  expires_at: string
}

const isString = (v: unknown): v is string => typeof v === 'string'
const isNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function parseLiveCard(data: unknown): LiveCard | null {
  if (typeof data !== 'object' || data === null) return null
  const c = data as Record<string, unknown>
  const ok =
    isString(c.card_id) && isString(c.match_id) && isString(c.headline) && isString(c.body) &&
    isString(c.topic) && isString(c.source) && isString(c.expires_at) &&
    isNumber(c.salience) && isNumber(c.match_clock_s) &&
    Array.isArray(c.entity_ids) && c.entity_ids.every(isString)
  return ok ? (c as unknown as LiveCard) : null
}

export function toFeedCard(card: LiveCard, homeTeam: string): FeedCard {
  const player = card.entity_ids.map((id) => playerById.get(id)).find(Boolean)
  const team = player?.team ?? card.entity_ids.find((id) => id in catalogTeams) ?? homeTeam
  // Cards are written per language upstream; until the Personalizer lands both slots carry the same text.
  const text = { h: card.headline, b: card.body }
  return {
    id: card.card_id,
    match: card.match_id,
    team,
    player,
    clock: card.match_clock_s,
    topic: card.topic,
    critical: CRITICAL_TOPICS.has(card.topic),
    salience: card.salience,
    specialist: card.source === 'fallback' ? { en: 'Editor fallback', es: 'Respaldo del editor' } : undefined,
    text: { en: text, es: text },
  }
}

/** Negotiates a receive-only Web PubSub URL for one match and keeps the socket alive with backoff. */
export function useLiveCards(apiBase: string, matchId: string): { cards: FeedCard[]; status: LiveStatus } {
  const [cards, setCards] = useState<FeedCard[]>([])
  const [status, setStatus] = useState<LiveStatus>('connecting')

  useEffect(() => {
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let attempt = 0
    let stopped = false

    const receive = (event: MessageEvent) => {
      if (typeof event.data !== 'string') return
      let parsed: LiveCard | null = null
      try {
        parsed = parseLiveCard(JSON.parse(event.data))
      } catch {
        return
      }
      if (!parsed || parsed.match_id !== matchId || Date.parse(parsed.expires_at) <= Date.now()) return
      const card = toFeedCard(parsed, 't-home')
      // Delivery is at-least-once: deduplicate on card_id.
      setCards((prev) => (prev.some((c) => c.id === card.id) ? prev : [...prev, card].slice(-MAX_CARDS)))
    }

    const retry = () => {
      if (stopped) return
      setStatus('error')
      const delay = Math.min(MAX_RETRY_MS, 1000 * 2 ** attempt++)
      retryTimer = window.setTimeout(connect, delay)
    }

    async function connect() {
      setStatus('connecting')
      try {
        const res = await fetch(`${apiBase}/negotiate?match_id=${encodeURIComponent(matchId)}`, { cache: 'no-store' })
        if (!res.ok) throw new Error(`negotiate ${res.status}`)
        const { url } = (await res.json()) as { url?: unknown }
        if (!isString(url) || !url.startsWith('wss://')) throw new Error('invalid negotiate url')
        if (stopped) return
        socket = new WebSocket(url)
        socket.onopen = () => {
          attempt = 0
          setStatus('open')
        }
        socket.onmessage = receive
        socket.onclose = retry
      } catch {
        retry()
      }
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      socket?.close()
    }
  }, [apiBase, matchId])

  return { cards, status }
}

function phaseFor(clock: number, started: boolean): Phase {
  if (!started) return 'pre'
  return clock <= 2700 ? 'h1' : 'h2'
}

/** Live mode covers one match from the packaged catalog (home `t-home` vs away `t-away`). */
export function useLiveSource(apiBase: string, matchId: string): { source: Source; status: LiveStatus } {
  const { cards, status } = useLiveCards(apiBase, matchId)
  const source = useMemo<Source>(() => {
    const match: Match = { id: matchId, home: 't-home', away: 't-away' }
    const outputs: Output[] = [
      { id: 'o1', name: 'TV 1', match: matchId },
      { id: 'o3', name: 'Stream', match: matchId },
    ]
    const clock = cards.reduce((max, c) => Math.max(max, c.clock), 0)
    return {
      teams: catalogTeams,
      players: catalogPlayers,
      matches: { [matchId]: match },
      outputs,
      cards,
      clock,
      phase: phaseFor(clock, cards.length > 0),
    }
  }, [cards, matchId])
  return { source, status }
}
