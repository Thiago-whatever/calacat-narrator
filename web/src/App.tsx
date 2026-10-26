import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { ControlBar } from './components/ControlBar'
import { Header, type Prefs } from './components/Header'
import { InsightFeed, type FeedItem, type MatchChip } from './components/InsightFeed'
import { EditableCard, StaticCard } from './components/OnScreenCard'
import { ProgramMonitor } from './components/ProgramMonitor'
import { useDemoSource, type DemoRun } from './data/useDemoSource'
import { MATCH_ID_PATTERN, useLiveSource, type LiveStatus } from './data/live'
import { minutes, STRINGS, topicLabel } from './i18n'
import { clamp, COUNTDOWN_MS, initialState, reducer } from './state'
import type { CardText, FeedCard, Lang, Source } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const PREFS_KEY = 'calacat.reporter.prefs'
const TOAST_MS = 4000

/** `?match=m-0007` switches to the live feed when an API base URL was configured at build time. */
function liveMatchFromUrl(): string | null {
  const match = new URLSearchParams(window.location.search).get('match')
  return API_BASE && match && MATCH_ID_PATTERN.test(match) ? match : null
}

export default function App() {
  const liveMatch = liveMatchFromUrl()
  return liveMatch ? <LiveConsole matchId={liveMatch} /> : <DemoConsole />
}

function DemoConsole() {
  const { source, run, toggle } = useDemoSource()
  return <Console source={source} demo={{ run, toggle }} />
}

function LiveConsole({ matchId }: { matchId: string }) {
  const { source, status } = useLiveSource(API_BASE, matchId)
  return <Console source={source} liveStatus={status} />
}

interface Stored {
  lang: Lang
  prefs: Prefs
}

// Per-viewer conveniences only; storage can be unavailable (private mode), so every access is guarded.
function loadStored(): Stored {
  const fallback: Stored = { lang: navigator.language.startsWith('es') ? 'es' : 'en', prefs: { hc: false, lg: false, rm: false } }
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) ?? 'null') as Partial<Stored> | null
    return {
      lang: raw?.lang === 'es' || raw?.lang === 'en' ? raw.lang : fallback.lang,
      prefs: { ...fallback.prefs, ...(raw?.prefs ?? {}) },
    }
  } catch {
    return fallback
  }
}

/** Re-renders every `ms` while `active`, for the countdown and the on-air timer. */
function useNow(ms: number, active: boolean) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const id = window.setInterval(() => setNow(Date.now()), ms)
    return () => window.clearInterval(id)
  }, [ms, active])
  return now
}

interface FeedDrag {
  id: string
  cx: number
  cy: number
  over: boolean
}

interface ConsoleProps {
  source: Source
  demo?: { run: DemoRun; toggle: () => void }
  liveStatus?: LiveStatus
}

function Console({ source, demo, liveStatus }: ConsoleProps) {
  const [stored] = useState(loadStored)
  const [lang, setLang] = useState<Lang>(stored.lang)
  const [prefs, setPrefs] = useState<Prefs>(stored.prefs)
  const [a11yOpen, setA11yOpen] = useState(false)
  const [s, dispatch] = useReducer(reducer, source.outputs[0].id, initialState)
  const [fdrag, setFdrag] = useState<FeedDrag | null>(null)
  const [moving, setMoving] = useState({ moving: false, guide: false })
  const stageRef = useRef<HTMLDivElement>(null)
  const feedPress = useRef<{ id: string; x0: number; y0: number; moved: boolean } | null>(null)
  const suppressClick = useRef(false)
  const seenCards = useRef<Set<string> | null>(null)

  const t = STRINGS[lang]
  const { teams, matches, outputs, cards } = source
  const output = outputs.find((o) => o.id === s.output) ?? outputs[0]
  const air = s.onAir[output.id] ?? null
  const now = useNow(200, !!s.pending || !!air)

  useEffect(() => {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({ lang, prefs }))
    } catch {
      // Storage unavailable: preferences just won't persist.
    }
    document.documentElement.lang = lang
    document.title = `Calacat Narrator · ${t.sub}`
  }, [lang, prefs, t.sub])

  // The countdown commits itself; Go live now commits early (ADR-033).
  useEffect(() => {
    if (s.pending && now >= s.pending.until) dispatch({ type: 'commit', now: Date.now() })
  }, [now, s.pending])

  useEffect(() => {
    if (!s.toast) return
    const id = window.setTimeout(() => dispatch({ type: 'dismissToast' }), TOAST_MS)
    return () => window.clearTimeout(id)
  }, [s.toast])

  // Goals and other critical cards interrupt screen readers; ordinary additions use the feed's polite region.
  useEffect(() => {
    const seen = seenCards.current
    seenCards.current = new Set(cards.map((c) => c.id))
    if (!seen) return
    const critical = cards.find((c) => c.critical && !seen.has(c.id))
    if (critical) {
      const team = teams[critical.team]
      dispatch({ type: 'announce', message: `${topicLabel(t, critical.topic)}, ${team?.name ?? ''}: ${critical.text[lang].h}` })
    }
  }, [cards, teams, t, lang])

  const cardById = useMemo(() => new Map(cards.map((c) => [c.id, c])), [cards])
  const textOf = (card: FeedCard): CardText => s.edits[`${card.id}:${lang}`] ?? card.text[lang]
  const teamOf = (card: FeedCard) => teams[card.team]

  const goals = (matchId: string, team: string) =>
    cards.filter((c) => c.match === matchId && c.team === team && c.topic === 'goal').length
  const scoreLine = (matchId: string) => {
    const m = matches[matchId]
    return `${teams[m.home].short} ${goals(matchId, m.home)}–${goals(matchId, m.away)} ${teams[m.away].short}`
  }

  const inFocus = (c: FeedCard) => {
    if (!s.focus) return true
    const [kind, id] = s.focus.split(':')
    return kind === 'team' ? c.team === id : c.player?.id === id
  }
  const inGame = (c: FeedCard) => (s.matchFilter === 'all' || c.match === s.matchFilter) && inFocus(c)
  const shown = cards.filter(inGame).sort((a, b) => b.salience - a.salience)
  const latest = cards.at(-1)?.id
  const liveOn = (id: string) => outputs.filter((o) => s.onAir[o.id]?.id === id).map((o) => o.name)

  const items: FeedItem[] = shown.map((card) => {
    const on = liveOn(card.id)
    return {
      card,
      team: teamOf(card),
      text: textOf(card),
      meta: (card.specialist?.[lang] ?? '') + (s.matchFilter === 'all' && Object.keys(matches).length > 1 ? ` · ${scoreLine(card.match)}` : ''),
      isNew: card.id === latest && on.length === 0,
      liveOn: on,
      selected: s.selected === card.id,
      locked: air?.id === card.id,
      lifted: fdrag?.id === card.id,
    }
  })

  const matchIds = Object.keys(matches)
  const chips: MatchChip[] = [
    { id: 'all', label: t.allGames, count: cards.filter(inFocus).length, program: false },
    ...matchIds.map((id) => ({ id, label: scoreLine(id), count: cards.filter((c) => c.match === id && inFocus(c)).length, program: id === output.match })),
  ]
  const focusTeams = [...new Set(matchIds.flatMap((id) => [matches[id].home, matches[id].away]))].map((id) => teams[id])

  const selected = s.selected ? cardById.get(s.selected) ?? null : null
  const editing = !!selected && !s.pending
  const countdown = s.pending ? clamp(Math.ceil((s.pending.until - now) / 1000), 1, COUNTDOWN_MS / 1000) : 0
  const airSecs = air ? Math.max(0, Math.floor((now - air.since) / 1000)) : 0

  let mode: 'idle' | 'ready' | 'pending' | 'air' = 'idle'
  let title = `${t.offAir} · ${output.name}`
  let sub = t.selectHint
  if (s.pending) {
    mode = 'pending'
    title = `${t.goingLive} ${output.name} · ${countdown}${t.secs}`
    sub = s.pending.h
  } else if (air) {
    mode = 'air'
    title = `${t.onAir} · ${output.name} · ${Math.floor(airSecs / 60)}:${String(airSecs % 60).padStart(2, '0')}`
    sub = selected ? t.nextReady : air.h
  } else if (selected) {
    mode = 'ready'
    title = t.ready
    sub = t.editHint
  }

  const period = { pre: t.preMatch, h1: t.h1, h2: t.h2, ft: t.ft }[source.phase]
  const match = matches[output.match]

  // ---- Actions
  const send = () => {
    // Only called from event handlers, never during render.
    // oxlint-disable-next-line react/purity
    if (selected) dispatch({ type: 'send', text: textOf(selected), now: Date.now(), message: t.sendMsg })
  }
  const pull = (out?: string) => {
    const target = outputs.find((o) => o.id === (out ?? s.output))
    if (target) dispatch({ type: 'pull', output: target.id, message: `${t.pulled} · ${target.name}` })
  }
  const pick = (id: string) => {
    if (!suppressClick.current) dispatch({ type: 'select', id })
  }
  const toggleRun = () => {
    if (demo?.run === 'finished') dispatch({ type: 'reset', output: s.output })
    demo?.toggle()
  }

  // ---- Drag from the feed: a ghost follows the pointer; releasing over the monitor places the card there.
  const overStage = (x: number, y: number) => {
    const r = stageRef.current?.getBoundingClientRect()
    return !!r && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom
  }
  const feedDrag = {
    down: (e: PointerEvent<HTMLButtonElement>, id: string) => {
      if (e.button !== 0 || s.pending || air?.id === id) return
      feedPress.current = { id, x0: e.clientX, y0: e.clientY, moved: false }
      e.currentTarget.setPointerCapture(e.pointerId)
    },
    move: (e: PointerEvent<HTMLButtonElement>) => {
      const f = feedPress.current
      if (!f) return
      if (!f.moved && Math.hypot(e.clientX - f.x0, e.clientY - f.y0) < 6) return
      f.moved = true
      setFdrag({ id: f.id, cx: e.clientX, cy: e.clientY, over: overStage(e.clientX, e.clientY) })
    },
    up: (e: PointerEvent<HTMLButtonElement>) => {
      const f = feedPress.current
      feedPress.current = null
      setFdrag(null)
      if (!f?.moved) return
      suppressClick.current = true
      window.setTimeout(() => { suppressClick.current = false }, 0)
      const r = stageRef.current?.getBoundingClientRect()
      if (!r || !overStage(e.clientX, e.clientY)) return
      const px = ((e.clientX - r.left) / r.width) * 100
      const py = ((e.clientY - r.top) / r.height) * 100
      const w = s.geo.width
      dispatch({ type: 'select', id: f.id, place: { x: clamp(px - w / 2, 0, 100 - w), y: clamp(py - 6, 4, 80) }, message: t.placed })
    },
    cancel: () => {
      feedPress.current = null
      setFdrag(null)
    },
  }

  const onMoving = useCallback((isMoving: boolean, guide: boolean) => setMoving({ moving: isMoving, guide }), [])

  // ---- Keyboard: J/K move through the feed, Enter on the selected card goes live, Esc in the documented order.
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
    if (e.key === 'Escape') {
      if (s.pending) dispatch({ type: 'cancel', message: t.cancelMsg })
      else if (a11yOpen) setA11yOpen(false)
      else if (inField) target.blur()
      else if (air) pull()
      else dispatch({ type: 'clearSelection' })
      return
    }
    if (inField || e.altKey || e.ctrlKey || e.metaKey) return
    // The card live on this output is locked, so J/K skip it.
    const ids = shown.filter((c) => c.id !== air?.id).map((c) => c.id)
    if ((e.key === 'j' || e.key === 'k') && ids.length) {
      const i = ids.indexOf(s.selected ?? '')
      const next = ids[e.key === 'j' ? Math.min(ids.length - 1, i + 1) : Math.max(0, i - 1)]
      if (next !== s.selected) dispatch({ type: 'select', id: next })
      document.querySelector<HTMLButtonElement>(`[data-card-id="${CSS.escape(next)}"]`)?.focus()
    } else if (e.key === 'Enter' && s.selected && target.dataset.cardId === s.selected) {
      e.preventDefault()
      send()
    }
  }

  const rootCls = ['root', prefs.hc && 'hc', prefs.lg && 'lg', prefs.rm && 'rm', (fdrag || moving.moving) && 'dragging'].filter(Boolean).join(' ')
  const fdCard = fdrag ? cardById.get(fdrag.id) : undefined
  const toastOut = s.toast ? outputs.find((o) => o.id === s.toast) : undefined
  const liveText = liveStatus === 'connecting' ? t.feedConnecting : liveStatus === 'error' ? t.feedError : undefined
  const emptyText = cards.length === 0 ? (liveText ?? t.empty) : s.focus ? t.emptyFocus : t.emptyFilter

  return (
    <div className={rootCls} lang={lang} onKeyDown={onKey}>
      <div className="sr" aria-live="assertive">{s.announce}</div>
      <div className="sr" aria-live="polite">{s.polite}</div>

      <Header
        t={t}
        lang={lang}
        onLang={setLang}
        prefs={prefs}
        onPrefs={setPrefs}
        a11yOpen={a11yOpen}
        onA11yOpen={setA11yOpen}
        run={demo && {
          label: demo.run === 'running' ? t.pause : demo.run === 'finished' ? t.restart : demo.run === 'paused' ? t.resume : t.start,
          running: demo.run === 'running',
          onToggle: toggleRun,
        }}
        liveStatus={liveText}
        outputs={outputs.map((o) => ({
          id: o.id,
          name: o.name,
          score: scoreLine(o.match),
          live: !!s.onAir[o.id],
          pressed: o.id === s.output,
          disabled: !!s.pending && o.id !== s.output,
        }))}
        onOutput={(id) => dispatch({ type: 'setOutput', output: id })}
        period={period}
      />

      <main className="main">
        <section className="left" aria-label={`${t.program} · ${output.name}`}>
          <ProgramMonitor
            ref={stageRef}
            t={t}
            label={`${t.program} · ${output.name}`}
            outputName={output.name}
            home={teams[match.home]}
            away={teams[match.away]}
            score={`${goals(match.id, match.home)}–${goals(match.id, match.away)}`}
            minute={minutes(source.clock)}
            onAir={!!air}
            showKickoff={source.phase === 'pre'}
            kickoffHint={demo ? t.preHint : t.liveHint}
            guide={moving.guide}
            drop={fdrag && { over: fdrag.over }}
          >
            {air && cardById.has(air.id) && (
              <StaticCard card={cardById.get(air.id)!} team={teamOf(cardById.get(air.id)!)} geo={air} text={air} mode="live" badge={t.bLive} t={t} />
            )}
            {s.pending && cardById.has(s.pending.id) && (
              <StaticCard
                card={cardById.get(s.pending.id)!}
                team={teamOf(cardById.get(s.pending.id)!)}
                geo={s.pending}
                text={s.pending}
                mode="pend"
                badge={`${t.liveIn} ${countdown}`}
                t={t}
              />
            )}
            {editing && selected && (
              <EditableCard
                card={selected}
                team={teamOf(selected)}
                geo={s.geo}
                text={textOf(selected)}
                t={t}
                moving={moving.moving}
                onMoving={onMoving}
                onGeo={(geo) => dispatch({ type: 'setGeo', geo })}
                onText={(text) => dispatch({ type: 'edit', key: `${selected.id}:${lang}`, text })}
                onRemove={() => dispatch({ type: 'clearSelection', message: t.removed })}
              />
            )}
          </ProgramMonitor>

          <ControlBar
            t={t}
            title={title}
            sub={sub}
            mode={mode}
            countdown={countdown}
            width={s.geo.width}
            fixedHeight={s.geo.height !== null}
            canEdit={editing}
            canSend={!!selected}
            canPull={!!air}
            liveLabel={`${air ? t.replace : t.goLive} ${output.name}`}
            onSize={(width) => dispatch({ type: 'setSize', width })}
            onSend={send}
            onPull={() => pull()}
            onGoNow={() => dispatch({ type: 'commit', now: Date.now() })}
            onCancel={() => dispatch({ type: 'cancel', message: t.cancelMsg })}
          />
        </section>

        <InsightFeed
          t={t}
          items={items}
          emptyText={emptyText}
          chips={chips}
          matchFilter={s.matchFilter}
          onFilter={(id) => dispatch({ type: 'setFilter', match: id })}
          focus={s.focus}
          onFocus={(focus) => dispatch({ type: 'setFocus', focus })}
          teams={focusTeams}
          players={source.players}
          teamById={teams}
          onPick={pick}
          drag={feedDrag}
        />
      </main>

      {fdrag && fdCard && (
        <div className={`ghost${fdrag.over ? ' over' : ''}`} style={{ left: fdrag.cx, top: fdrag.cy }} aria-hidden="true">
          <span className="gtopic">{teamOf(fdCard).short} · {topicLabel(t, fdCard.topic)} · {minutes(fdCard.clock)}</span>
          <span className="disp gh">{textOf(fdCard).h}</span>
          <span className="gs">{fdrag.over ? t.release : t.dragTo}</span>
        </div>
      )}

      {toastOut && s.onAir[toastOut.id] && (
        <div className="toast" role="status">
          <span className="tick" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          <div className="toast-text">
            <div className="toast-title">{t.toastTitle} {toastOut.name}</div>
            <div className="toast-h">{s.onAir[toastOut.id]?.h}</div>
          </div>
          <button type="button" className="btn" onClick={() => pull(toastOut.id)}>{t.pull}</button>
        </div>
      )}
    </div>
  )
}
