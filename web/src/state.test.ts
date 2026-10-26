import { describe, expect, it } from 'vitest'
import { parseLiveCard, toFeedCard } from './data/live'
import { COUNTDOWN_MS, initialState, reducer, type Action, type ConsoleState } from './state'

const text = { h: 'Headline', b: 'Body' }
const run = (actions: Action[], start: ConsoleState = initialState('o1')) => actions.reduce(reducer, start)
const onAir = (s: ConsoleState) => run([{ type: 'select', id: 'c1' }, { type: 'send', text, now: 0, message: '' }, { type: 'commit', now: 1 }], s)

describe('console reducer', () => {
  it('sends a card through a cancellable countdown, then locks it on air', () => {
    const pending = run([{ type: 'select', id: 'c1' }, { type: 'send', text, now: 100, message: 'going' }])
    expect(pending.pending).toMatchObject({ id: 'c1', output: 'o1', until: 100 + COUNTDOWN_MS })

    expect(reducer(pending, { type: 'cancel', message: 'cancelled' }).pending).toBeNull()

    const live = reducer(pending, { type: 'commit', now: 200 })
    expect(live.onAir.o1).toMatchObject({ id: 'c1', since: 200, h: 'Headline' })
    expect(live.selected).toBeNull()
    expect(live.toast).toBe('o1')
    // A live card can't be selected for editing; only pulled.
    expect(reducer(live, { type: 'select', id: 'c1' }).selected).toBeNull()
  })

  it('blocks output switching and selection during a countdown', () => {
    const pending = run([{ type: 'select', id: 'c1' }, { type: 'send', text, now: 0, message: '' }])
    expect(reducer(pending, { type: 'setOutput', output: 'o2' }).output).toBe('o1')
    expect(reducer(pending, { type: 'select', id: 'c2' }).selected).toBe('c1')
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

  it('rejects malformed payloads', () => {
    expect(parseLiveCard(null)).toBeNull()
    expect(parseLiveCard({ ...valid, salience: '1' })).toBeNull()
    expect(parseLiveCard({ ...valid, entity_ids: [1] })).toBeNull()
  })
})
