import { describe, expect, it } from 'vitest'
import { mergeCards, parseLiveCard, toFeedCard } from './data/live'
import { onAirState, openOnAirChannel, parseOnAirMessage } from './data/onAirChannel'
import { readStartResponse, startMessage } from './data/kickoff'
import { minutes, STRINGS } from './i18n'
import { COUNTDOWN_MS, initialState, reducer, type Action, type ConsoleState } from './state'
import type { FeedCard } from './types'

const text = { h: 'Headline', b: 'Body' }
const feedCard = (id: string, expiresAt?: number): FeedCard => ({
  id, match: 'm1', team: 'rio', clock: 60, topic: 'goal', critical: true, salience: 1, text: { en: text, es: text }, expiresAt,
})
const card = feedCard('c1')
const run = (actions: Action[], start: ConsoleState = initialState('o1')) => actions.reduce(reducer, start)
const onAir = (s: ConsoleState) => run([{ type: 'select', id: 'c1' }, { type: 'send', card, text, now: 0, message: '' }, { type: 'commit', now: 1 }], s)

describe('console reducer', () => {
  it('sends a card through a cancellable countdown, then locks it on air', () => {
    const pending = run([{ type: 'select', id: 'c1' }, { type: 'send', card, text, now: 100, message: 'going' }])
    expect(pending.pending).toMatchObject({ id: 'c1', output: 'o1', until: 100 + COUNTDOWN_MS })

    expect(reducer(pending, { type: 'cancel', message: 'cancelled' }).pending).toBeNull()

    const live = reducer(pending, { type: 'commit', now: 200 })
    // The on-air card keeps its own snapshot, so it still renders if the feed drops the card.
    expect(live.onAir.o1).toMatchObject({ id: 'c1', card, since: 200, h: 'Headline' })
    expect(live.selected).toBeNull()
    expect(live.toast).toBe('o1')
    // A live card can't be selected for editing; only pulled.
    expect(reducer(live, { type: 'select', id: 'c1' }).selected).toBeNull()
  })

  it('blocks output switching and selection during a countdown', () => {
    const pending = run([{ type: 'select', id: 'c1' }, { type: 'send', card, text, now: 0, message: '' }])
    expect(reducer(pending, { type: 'setOutput', output: 'o2' }).output).toBe('o1')
    expect(reducer(pending, { type: 'select', id: 'c2' }).selected).toBe('c1')
  })

  it('refuses to send an expired card', () => {
    const selected = run([{ type: 'select', id: 'old' }])
    const stale = feedCard('old', 1000)
    expect(reducer(selected, { type: 'send', card: stale, text, now: 1000, message: '' })).toBe(selected)
    expect(reducer(selected, { type: 'send', card: stale, text, now: 999, message: '' }).pending?.id).toBe('old')
  })

  it('pulls only the targeted output', () => {
    const live = onAir(initialState('o1'))
    const pulled = reducer(live, { type: 'pull', output: 'o1', message: 'pulled' })
    expect(pulled.onAir.o1).toBeNull()
    expect(pulled.announce).toBe('pulled')
    expect(reducer(live, { type: 'pull', output: 'o2', message: 'x' })).toBe(live)
  })

  it('keeps the card inside the monitor when the size preset changes', () => {
    const s = run([{ type: 'setGeo', geo: { x: 60, height: 30 } }, { type: 'setSize', width: 56 }])
    expect(s.geo).toEqual({ x: 44, y: 62, width: 56, height: null })
  })
})

describe('live cards', () => {
  const valid = {
    card_id: 'card-1', match_id: 'm-0007', headline: 'A second goal', body: 'Twice now.', entity_ids: ['p-nbr-09'],
    topic: 'goal', salience: 1, source: 'specialist', match_clock_s: 4020, expires_at: '2099-01-01T00:00:00Z', metrics: { goal: 2 },
  }

  it('maps a valid card to its player and team from the catalog', () => {
    const card = toFeedCard(parseLiveCard(valid)!, 't-home')
    expect(card).toMatchObject({ id: 'card-1', team: 't-home', critical: true, clock: 4020 })
    expect(card.player?.id).toBe('p-nbr-09')
  })

  it('merges unseen cards and prunes expired ones', () => {
    const live = feedCard('live', 2000)
    const prev = [live, feedCard('old', 1000), feedCard('demo')]
    expect(mergeCards(prev, [live], 500)).toBe(prev)
    expect(mergeCards(prev, [], 1000).map((c) => c.id)).toEqual(['live', 'demo'])
    expect(mergeCards(prev, [feedCard('new', 3000), feedCard('new', 3000)], 500).map((c) => c.id)).toEqual(['live', 'old', 'demo', 'new'])
  })

  it('rejects malformed payloads', () => {
    expect(parseLiveCard(null)).toBeNull()
    expect(parseLiveCard({ ...valid, salience: '1' })).toBeNull()
    expect(parseLiveCard({ ...valid, entity_ids: [1] })).toBeNull()
  })
})

describe('bilingual live cards (ADR-040, ADR-041)', () => {
  const base = {
    card_id: 'card-2', match_id: 'm-0007', headline: 'Bram Elsen doubles the lead', body: "68' Bram Elsen scores. It's 2-0.",
    entity_ids: ['t-home'], topic: 'goal', salience: 1, source: 'specialist', match_clock_s: 4020, expires_at: '2099-01-01T00:00:00Z',
  }

  it('uses team_id, player_id and the Spanish text when present', () => {
    const card = toFeedCard(
      parseLiveCard({ ...base, team_id: 't-home', player_id: 'p-nbr-09', i18n: { es: { headline: 'Bram Elsen amplía la ventaja', body: "68' Bram Elsen marca. Va 2-0." } } })!,
      't-away',
    )
    expect(card.team).toBe('t-home')
    expect(card.player?.name).toBe('Bram Elsen')
    expect(card.text.es).toEqual({ h: 'Bram Elsen amplía la ventaja', b: "68' Bram Elsen marca. Va 2-0." })
    expect(card.text.en.h).toBe('Bram Elsen doubles the lead')
  })

  it('falls back to English and ignores malformed translations', () => {
    const card = toFeedCard(parseLiveCard({ ...base, i18n: { es: { headline: 42 } } })!, 't-home')
    expect(card.text.es).toEqual(card.text.en)
    expect(parseLiveCard({ ...base, team_id: 7 })).toBeNull()
  })
})

describe('on-air minute', () => {
  it.each([
    [0, '1’'],
    [59, '1’'],
    [2699, '45’'],
    [2700, '46’'],
    [5400, '90’'],
  ])('%i s is %s', (seconds, minute) => {
    expect(minutes(seconds)).toBe(minute)
  })
})

describe('overlay view (C14)', () => {
  const team = { id: 'rio', name: 'Ríos FC', short: 'RIO', color: '#123456', ink: '#ffffff', soft: '#eeeeee' }
  const outputs = [{ id: 'o1', name: 'TV 1', match: 'm1' }, { id: 'o2', name: 'TV 2', match: 'm1' }]

  it('snapshots each output: go live shows the card, pull from air clears it', () => {
    const live = onAirState(outputs, onAir(initialState('o1')).onAir, { rio: team })
    expect(live).toMatchObject({ type: 'state', outputs: [{ id: 'o1', name: 'TV 1' }, { id: 'o2', name: 'TV 2' }] })
    expect(live.type === 'state' && live.onAir).toEqual({
      o1: { id: 'c1', card, team, geo: expect.objectContaining({ width: expect.any(Number) }), text },
      o2: null,
    })
    const pulled = reducer(onAir(initialState('o1')), { type: 'pull', output: 'o1', message: '' })
    expect(onAirState(outputs, pulled.onAir, { rio: team })).toMatchObject({ onAir: { o1: null, o2: null } })
  })

  it('drops malformed cards and unknown messages', () => {
    expect(parseOnAirMessage({ type: 'state', outputs: [], onAir: { o1: { id: 'x' } } })).toEqual({ type: 'state', outputs: [], onAir: { o1: null } })
    expect(parseOnAirMessage({ type: 'go-live' })).toBeNull()
    expect(parseOnAirMessage('hello')).toBeNull()
  })

  it('answers a new overlay tab over BroadcastChannel', async () => {
    const state = onAirState(outputs, onAir(initialState('o1')).onAir, { rio: team })
    const consoleTab = openOnAirChannel((m) => m.type === 'hello' && consoleTab.post(state))
    const received = new Promise((resolve) => {
      const overlay = openOnAirChannel((m) => {
        overlay.close()
        resolve(m)
      })
      overlay.post({ type: 'hello' })
    })
    expect(await received).toEqual(state)
    consoleTab.close()
  })
})

describe('start a match (C16)', () => {
  it('follows a started match and reads both caps', () => {
    expect(readStartResponse(202, { match_id: 'm-seed-42', speed: 10 })).toEqual({ status: 'started', matchId: 'm-seed-42' })
    expect(readStartResponse(202, { match_id: 'm-seed-7', status: 'joined' })).toEqual({ status: 'joined', matchId: 'm-seed-7' })
    expect(readStartResponse(429, { error: 'busy', retry_after_s: 301 })).toEqual({ status: 'busy', retryMin: 6 })
    expect(readStartResponse(429, { error: 'daily_cap', retry_after_s: 9000 })).toEqual({ status: 'daily_cap' })
  })

  it('treats a bad match ID or any other status as an error', () => {
    expect(readStartResponse(202, { match_id: '../x' }).status).toBe('error')
    expect(readStartResponse(503, null).status).toBe('error')
  })

  it('shows the busy message with minutes', () => {
    expect(startMessage(STRINGS.en, { status: 'busy', retryMin: 6 })).toBe('Two matches are already running. Try again in 6 min.')
    expect(startMessage(STRINGS.es, { status: 'idle' })).toBe('')
  })
})

describe('translations', () => {
  it('keep the same placeholders in English and Spanish', () => {
    const slots = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort()
    const { en, es } = STRINGS
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      const value = en[key]
      if (typeof value === 'string') expect(slots(es[key] as string), key).toEqual(slots(value))
    }
  })

  it('name the go-live button from its live label, not a hardcoded fragment', () => {
    // Filled with e.g. "Go live on TV 1" / "Enviar a TV 1" in HelpDialog.
    expect(STRINGS.en.helpStep3).toContain('{golive}')
  })
})
