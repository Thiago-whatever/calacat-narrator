import { useEffect, useMemo, useState } from 'react'
import teamsJson from '../../../src/calacat_narrator/data/teams.json'
import playersJson from '../../../src/calacat_narrator/data/players.json'
import type { FeedCard, Match, Output, Phase, Player, Source, Team } from '../types'

// Same pattern as the backend's EntityId (schemas.py); also guards what we put in the URL.
export const MATCH_ID_PATTERN = /^[a-z0-9][a-z0-9_-]{0,63}$/
const CRITICAL_TOPICS = new Set(['goal', 'red_card', 'penalty'])
const MAX_CARDS = 200
const MAX_RETRY_MS = 30_000
// Catch-up also refreshes the authoritative score; pruning keeps stale insights off the feed.
const CATCH_UP_MS = 30_000
const PRUNE_MS = 5_000

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
  team_id?: string
  player_id?: string
  /** Spanish caption from the Reviewer (ADR-040). */
  i18n?: { es?: { headline: string; body: string } }
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
    Array.isArray(c.entity_ids) && c.entity_ids.every(isString) &&
    (c.team_id === undefined || isString(c.team_id)) &&
    (c.player_id === undefined || c.player_id === null || isString(c.player_id))
  if (!ok) return null
  const es = (c.i18n as { es?: Record<string, unknown> } | undefined)?.es
  const validEs = es && isString(es.headline) && isString(es.body) ? { headline: es.headline, body: es.body } : undefined
  return { ...(c as unknown as LiveCard), player_id: isString(c.player_id) ? c.player_id : undefined, i18n: validEs && { es: validEs } }
}

export function toFeedCard(card: LiveCard, homeTeam: string): FeedCard {
  // Cards name their player and team (ADR-041); older cards only list entity IDs.
  const player = (card.player_id && playerById.get(card.player_id)) || card.entity_ids.map((id) => playerById.get(id)).find(Boolean)
  const team =
    (card.team_id && card.team_id in catalogTeams ? card.team_id : undefined) ??
    player?.team ??
    card.entity_ids.find((id) => id in catalogTeams) ??
    homeTeam
  const en = { h: card.headline, b: card.body }
  // English is canonical; the Reviewer's Spanish rides along in i18n.es (ADR-040).
  const es = card.i18n?.es ? { h: card.i18n.es.headline, b: card.i18n.es.body } : en
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
    text: { en, es },
    expiresAt: Date.parse(card.expires_at),
  }
}

/** Adds unseen cards (delivery is at-least-once) and drops expired ones; returns `prev` when nothing changed. */
export function mergeCards(prev: FeedCard[], incoming: FeedCard[], now: number): FeedCard[] {
  const seen = new Set(prev.map((c) => c.id))
  const fresh = incoming.filter((c) => !seen.has(c.id) && seen.add(c.id))
  const next = [...prev, ...fresh].filter((c) => c.expiresAt === undefined || c.expiresAt > now)
  return fresh.length === 0 && next.length === prev.length ? prev : next.slice(-MAX_CARDS)
}

const isScore = (v: unknown): v is Record<string, number> =>
  typeof v === 'object' && v !== null && !Array.isArray(v) && Object.values(v).every(isNumber)

interface LiveFeed {
  cards: FeedCard[]
  score: Record<string, number> | undefined
  clock: number
  status: LiveStatus
}

/**
 * Negotiates a receive-only Web PubSub URL for one match and keeps the socket alive with backoff.
 * After each open it loads `GET /cards` (subscribe first, then fetch, so nothing falls in the gap)
 * and polls it for the interpreter's score.
 */
export function useLiveCards(apiBase: string, matchId: string): LiveFeed {
  const [cards, setCards] = useState<FeedCard[]>([])
  const [score, setScore] = useState<Record<string, number>>()
  const [clock, setClock] = useState(0)
  const [status, setStatus] = useState<LiveStatus>('connecting')

  useEffect(() => {
    let socket: WebSocket | null = null
    let retryTimer: number | undefined
    let pollTimer: number | undefined
    let attempt = 0
    let stopped = false

    const accept = (raw: unknown[]) => {
      const incoming = raw
        .map(parseLiveCard)
        .filter((c): c is LiveCard => c !== null && c.match_id === matchId)
        .map((c) => toFeedCard(c, 't-home'))
      const now = Date.now()
      setCards((prev) => mergeCards(prev, incoming, now))
    }

    const receive = (event: MessageEvent) => {
      if (typeof event.data !== 'string') return
      try {
        accept([JSON.parse(event.data)])
      } catch {
        // Not JSON: ignore.
      }
    }

    const catchUp = async () => {
      try {
        const res = await fetch(`${apiBase}/cards?match_id=${encodeURIComponent(matchId)}`, { cache: 'no-store' })
        if (!res.ok || stopped) return
        const body = (await res.json()) as { cards?: unknown; score?: unknown; match_clock_s?: unknown }
        if (stopped) return
        if (Array.isArray(body.cards)) accept(body.cards)
        if (isScore(body.score)) setScore(body.score)
        if (isNumber(body.match_clock_s)) setClock(body.match_clock_s)
      } catch {
        // The next poll or reconnect tries again.
      }
    }

    const retry = () => {
      window.clearInterval(pollTimer)
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
          catchUp()
          window.clearInterval(pollTimer)
          pollTimer = window.setInterval(catchUp, CATCH_UP_MS)
        }
        socket.onmessage = receive
        socket.onclose = retry
      } catch {
        retry()
      }
    }

    const pruneTimer = window.setInterval(() => setCards((prev) => mergeCards(prev, [], Date.now())), PRUNE_MS)
    connect()
    return () => {
      stopped = true
      window.clearTimeout(retryTimer)
      window.clearInterval(pollTimer)
      window.clearInterval(pruneTimer)
      socket?.close()
    }
  }, [apiBase, matchId])

  return { cards, score, clock, status }
}

function phaseFor(clock: number, started: boolean): Phase {
  if (!started) return 'pre'
  return clock <= 2700 ? 'h1' : 'h2'
}

/** Live mode covers one match from the packaged catalog (home `t-home` vs away `t-away`). */
export function useLiveSource(apiBase: string, matchId: string): { source: Source; status: LiveStatus } {
  const { cards, score, clock: stateClock, status } = useLiveCards(apiBase, matchId)
  const source = useMemo<Source>(() => {
    const match: Match = { id: matchId, home: 't-home', away: 't-away' }
    const outputs: Output[] = [
      { id: 'o1', name: 'TV 1', match: matchId },
      { id: 'o3', name: 'Stream', match: matchId },
    ]
    const clock = cards.reduce((max, c) => Math.max(max, c.clock), stateClock)
    return {
      teams: catalogTeams,
      players: catalogPlayers,
      matches: { [matchId]: match },
      outputs,
      cards,
      score,
      clock,
      phase: phaseFor(clock, clock > 0 || cards.length > 0),
    }
  }, [cards, score, stateClock, matchId])
  return { source, status }
}
