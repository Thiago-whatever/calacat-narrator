import { Button } from '@mui/material'
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, type KeyboardEvent } from 'react'
import { ControlBar, type BarMode } from './components/control/ControlBar'
import { DragGhost } from './components/feed/DragGhost'
import type { FeedItem } from './components/feed/FeedCard'
import type { MatchChip } from './components/feed/FeedFilters'
import { InsightFeed } from './components/feed/InsightFeed'
import { OverlayView } from './components/overlay/OverlayView'
import { Header } from './components/header/Header'
import { ConsoleMain, ConsoleRoot, MonitorColumn, MonitorFit } from './components/layout/ConsoleLayout'
import { EditableCard, StaticCard } from './components/monitor/OnScreenCard'
import { ProgramMonitor } from './components/monitor/ProgramMonitor'
import { LiveRegion } from './components/ui/primitives'
import { Toast } from './components/ui/Toast'
import { startMessage, useMatchStarter } from './data/kickoff'
import { MATCH_ID_PATTERN, useLiveSource, type LiveStatus } from './data/live'
import { onAirState, openOnAirChannel } from './data/onAirChannel'
import { useDemoSource, type DemoRun } from './data/useDemoSource'
import { useFeedDrag, useNow, usePrefs } from './hooks'
import { fill, minutes, STRINGS, topicLabel } from './i18n'
import { clamp, COUNTDOWN_MS, initialState, reducer, SIZES } from './state'
import { AppThemeProvider } from './theme/AppThemeProvider'
import type { ThemePrefs } from './theme/theme'
import type { CardText, FeedCard, Lang, Source } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')
const TOAST_MS = 4000

/** `?match=m-0007` switches to the live feed when an API base URL was configured at build time. */
function liveMatchFromUrl(): string | null {
  const match = new URLSearchParams(window.location.search).get('match')
  return API_BASE && match && MATCH_ID_PATTERN.test(match) ? match : null
}

const OUTPUT_ID_PATTERN = /^o[0-9]{1,2}$/

/** `?overlay=o1` shows only the card on air for that output (C14), fed by the console in another tab. */
function overlayFromUrl(): string | null {
  const id = new URLSearchParams(window.location.search).get('overlay')
  return id && OUTPUT_ID_PATTERN.test(id) ? id : null
}

/** Same page with `overlay` set (or removed), keeping `?match=`. */
function viewHref(overlay: string | null): string {
  const params = new URLSearchParams(window.location.search)
  if (overlay) params.set('overlay', overlay)
  else params.delete('overlay')
  const query = params.toString()
  return query ? `?${query}` : window.location.pathname
}

/** The on-air output is what viewers get, so it is always in English, whatever the console's language. */
function Overlay({ prefs, setPrefs }: Pick<PrefsProps, 'prefs' | 'setPrefs'>) {
  const [output, setOutput] = useState(() => overlayFromUrl() ?? 'o1')
  useEffect(() => {
    document.documentElement.lang = 'en'
    document.title = `Calacat Narrator · ${STRINGS.en.overlay}`
  }, [])
  const choose = (id: string) => {
    window.history.replaceState(null, '', viewHref(id))
    setOutput(id)
  }
  return (
    <OverlayView
      t={STRINGS.en}
      prefs={prefs}
      onPrefs={setPrefs}
      output={output}
      onOutput={choose}
      consoleHref={viewHref(null)}
    />
  )
}

interface Starter {
  busy: boolean
  message: string
  onStart: () => void
}

interface PrefsProps {
  lang: Lang
  setLang: (lang: Lang) => void
  prefs: ThemePrefs
  setPrefs: (prefs: ThemePrefs) => void
  starter?: Starter
}

export default function App() {
  const prefs = usePrefs()
  const [liveMatch, setLiveMatch] = useState(liveMatchFromUrl)
  // "Start live match" (C16) follows the new match in place, so its status message stays on screen.
  const { state, start } = useMatchStarter(API_BASE, (id) => {
    window.history.pushState(null, '', `?match=${encodeURIComponent(id)}`)
    setLiveMatch(id)
  })
  useEffect(() => {
    const onPop = () => setLiveMatch(liveMatchFromUrl())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  const starter: Starter | undefined = API_BASE
    ? { busy: state.status === 'starting', message: startMessage(STRINGS[prefs.lang], state), onStart: start }
    : undefined
  if (overlayFromUrl()) {
    return (
      <AppThemeProvider prefs={prefs.prefs}>
        <Overlay {...prefs} />
      </AppThemeProvider>
    )
  }
  return (
    <AppThemeProvider prefs={prefs.prefs}>
      {liveMatch ? <LiveConsole key={liveMatch} matchId={liveMatch} starter={starter} {...prefs} /> : <DemoConsole starter={starter} {...prefs} />}
    </AppThemeProvider>
  )
}

function DemoConsole(props: PrefsProps) {
  const { source, run, toggle } = useDemoSource()
  return <Console source={source} demo={{ run, toggle }} {...props} />
}

function LiveConsole({ matchId, ...props }: PrefsProps & { matchId: string }) {
  const { source, status } = useLiveSource(API_BASE, matchId)
  return <Console source={source} liveStatus={status} {...props} />
}

interface ConsoleProps extends PrefsProps {
  source: Source
  demo?: { run: DemoRun; toggle: () => void }
  liveStatus?: LiveStatus
}

function Console({ source, demo, liveStatus, lang, setLang, prefs, setPrefs, starter }: ConsoleProps) {
  const [s, dispatch] = useReducer(reducer, source.outputs[0].id, initialState)
  const [moving, setMoving] = useState({ moving: false, guide: false })
  const stageRef = useRef<HTMLDivElement>(null)
  const seenCards = useRef<Set<string> | null>(null)

  const t = STRINGS[lang]
  const { teams, matches, outputs, cards } = source
  const output = outputs.find((o) => o.id === s.output) ?? outputs[0]
  const air = s.onAir[output.id] ?? null
  const now = useNow(200, !!s.pending || !!air)

  useEffect(() => {
    document.documentElement.lang = lang
    document.title = `Calacat Narrator · ${t.sub}`
  }, [lang, t.sub])

  // The countdown commits itself; Go live now commits early (ADR-033).
  useEffect(() => {
    if (s.pending && now >= s.pending.until) dispatch({ type: 'commit', now: Date.now() })
  }, [now, s.pending])

  // The overlay view in another tab of this browser mirrors what's on air (C14); nothing leaves the browser.
  const channel = useRef<ReturnType<typeof openOnAirChannel> | null>(null)
  const latestState = useRef(() => onAirState(outputs, s.onAir, teams))
  useEffect(() => {
    // Only go-live, replace and pull change the output: edits after send never reach viewers.
    latestState.current = () => onAirState(outputs, s.onAir, teams)
    channel.current?.post(latestState.current())
  }, [outputs, s.onAir, teams])
  useEffect(() => {
    const open = openOnAirChannel((message) => {
      if (message.type === 'hello') open.post(latestState.current())
    })
    channel.current = open
    return () => {
      channel.current = null
      open.close()
    }
  }, [])

  // Goals and other critical cards interrupt screen readers; ordinary additions use the feed's polite region.
  useEffect(() => {
    const seen = seenCards.current
    seenCards.current = new Set(cards.map((c) => c.id))
    if (!seen) return
    const critical = cards.find((c) => c.critical && !seen.has(c.id))
    if (critical) {
      dispatch({ type: 'announce', message: `${topicLabel(t, critical.topic)}, ${teams[critical.team]?.name ?? ''}: ${critical.text[lang].h}` })
    }
  }, [cards, teams, t, lang])

  const cardById = useMemo(() => new Map(cards.map((c) => [c.id, c])), [cards])
  const textOf = (card: FeedCard): CardText => s.edits[`${card.id}:${lang}`] ?? card.text[lang]
  const teamOf = (card: FeedCard) => teams[card.team]

  const goals = (matchId: string, team: string) =>
    source.score ? (source.score[team] ?? 0) : cards.filter((c) => c.match === matchId && c.team === team && c.topic === 'goal').length
  const scoreLine = (matchId: string) => {
    const m = matches[matchId]
    return `${teams[m.home].short} ${goals(matchId, m.home)}–${goals(matchId, m.away)} ${teams[m.away].short}`
  }

  const inFocus = (c: FeedCard) => {
    if (!s.focus) return true
    const [kind, id] = s.focus.split(':')
    return kind === 'team' ? c.team === id : c.player?.id === id
  }
  const shown = cards.filter((c) => (s.matchFilter === 'all' || c.match === s.matchFilter) && inFocus(c)).sort((a, b) => b.salience - a.salience)
  const latest = cards.at(-1)?.id
  const liveOn = (id: string) => outputs.filter((o) => s.onAir[o.id]?.id === id).map((o) => o.name)
  const matchIds = Object.keys(matches)

  const { drag, handlers: dragHandlers, isClickSuppressed } = useFeedDrag({
    target: stageRef,
    canDrag: (id) => !s.pending && air?.id !== id,
    onDrop: (id, px, py) => {
      const w = s.geo.width
      dispatch({ type: 'select', id, place: { x: clamp(px - w / 2, 0, 100 - w), y: clamp(py - 6, 4, 80) }, message: t.placed })
    },
  })

  const items: FeedItem[] = shown.map((card) => {
    const on = liveOn(card.id)
    return {
      card,
      team: teamOf(card),
      text: textOf(card),
      meta: (card.specialist?.[lang] ?? '') + (s.matchFilter === 'all' && matchIds.length > 1 ? ` · ${scoreLine(card.match)}` : ''),
      isNew: card.id === latest && on.length === 0,
      liveOn: on,
      selected: s.selected === card.id,
      locked: air?.id === card.id,
      lifted: drag?.id === card.id,
    }
  })

  const chips: MatchChip[] = [
    { id: 'all', label: t.allGames, count: cards.filter(inFocus).length, program: false },
    ...matchIds.map((id) => ({ id, label: scoreLine(id), count: cards.filter((c) => c.match === id && inFocus(c)).length, program: id === output.match })),
  ]
  const focusTeams = [...new Set(matchIds.flatMap((id) => [matches[id].home, matches[id].away]))].map((id) => teams[id])

  const selected = s.selected ? cardById.get(s.selected) ?? null : null
  const editing = !!selected && !s.pending
  const countdown = s.pending ? clamp(Math.ceil((s.pending.until - now) / 1000), 1, COUNTDOWN_MS / 1000) : 0
  const airSecs = air ? Math.max(0, Math.floor((now - air.since) / 1000)) : 0

  // Outside English, say what viewers actually get, since the output is English only.
  const viewersGet = (c: CardText & { en: CardText }) => (lang === 'en' ? c.h : `${t.viewersGet} “${c.en.h}”`)
  let mode: BarMode = 'idle'
  let title = `${t.offAir} · ${output.name}`
  let sub = t.selectHint
  if (s.pending) {
    mode = 'pending'
    title = `${t.goingLive} ${output.name} · ${countdown}${t.secs}`
    sub = viewersGet(s.pending)
  } else if (air) {
    mode = 'air'
    title = `${t.onAir} · ${output.name} · ${Math.floor(airSecs / 60)}:${String(airSecs % 60).padStart(2, '0')}`
    sub = selected ? t.nextReady : viewersGet(air)
  } else if (selected) {
    mode = 'ready'
    title = t.ready
    sub = t.editHint
  }

  const match = matches[output.match]
  const sizePreset = !s.geo.height && SIZES.some((z) => z.width === s.geo.width) ? s.geo.width : null

  // ---- Actions (event handlers only; never called during render)
  const send = () => {
    // The output is English only: freeze the reporter's English edit (or the English card) now.
    const en = selected && (s.edits[`${selected.id}:en`] ?? selected.text.en)
    // oxlint-disable-next-line react/purity
    if (selected && en) dispatch({ type: 'send', card: selected, text: textOf(selected), en, now: Date.now(), message: t.sendMsg })
  }
  const pull = (out?: string) => {
    const target = outputs.find((o) => o.id === (out ?? s.output))
    if (target) dispatch({ type: 'pull', output: target.id, message: `${t.pulled} · ${target.name}` })
  }
  const toggleRun = () => {
    if (demo?.run === 'finished') dispatch({ type: 'reset', output: s.output })
    demo?.toggle()
  }
  const onMoving = useCallback((isMoving: boolean, guide: boolean) => setMoving({ moving: isMoving, guide }), [])

  // ---- Keyboard: J/K move through the feed, Enter on the selected card goes live, Esc in the documented order.
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement
    const inField = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.getAttribute('role') === 'combobox'
    if (e.key === 'Escape') {
      if (s.pending) dispatch({ type: 'cancel', message: t.cancelMsg })
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
      document.querySelector<HTMLElement>(`[data-card-id="${CSS.escape(next)}"]`)?.focus()
    } else if (e.key === 'Enter' && s.selected && target.dataset.cardId === s.selected) {
      e.preventDefault()
      send()
    }
  }

  const dragCard = drag ? cardById.get(drag.id) : undefined
  const toastOut = s.toast ? outputs.find((o) => o.id === s.toast) : undefined
  const liveText = liveStatus === 'connecting' ? t.feedConnecting : liveStatus === 'error' ? t.feedError : undefined
  const emptyText = cards.length === 0 ? (liveText ?? t.empty) : s.focus ? t.emptyFocus : t.emptyFilter
  const programLabel = `${t.program} · ${output.name}`

  return (
    <ConsoleRoot lang={lang} onKeyDown={onKey} dragging={!!drag || moving.moving}>
      <LiveRegion politeness="assertive">{s.announce}</LiveRegion>
      <LiveRegion politeness="polite">{s.polite}</LiveRegion>

      <Header
        t={t}
        lang={lang}
        onLang={setLang}
        prefs={prefs}
        onPrefs={setPrefs}
        run={demo && {
          label: demo.run === 'running' ? t.pause : demo.run === 'finished' ? t.restart : demo.run === 'paused' ? t.resume : t.start,
          running: demo.run === 'running',
          onToggle: toggleRun,
        }}
        liveStatus={liveText}
        overlay={{ label: t.openOverlay, href: viewHref(s.output) }}
        start={starter && { label: t.startMatch, ...starter }}
        outputs={outputs.map((o) => ({ id: o.id, name: o.name, score: scoreLine(o.match), live: !!s.onAir[o.id], disabled: !!s.pending && o.id !== s.output }))}
        output={s.output}
        onOutput={(id) => dispatch({ type: 'setOutput', output: id })}
        period={{ pre: t.preMatch, h1: t.h1, h2: t.h2, ft: t.ft }[source.phase]}
      />

      <ConsoleMain>
        <MonitorColumn aria-label={programLabel}>
          <MonitorFit>
            <ProgramMonitor
              ref={stageRef}
              label={programLabel}
              tally={output.name + (air ? ` · ${t.onAir}` : '')}
              onAir={!!air}
              home={teams[match.home]}
              away={teams[match.away]}
              score={`${goals(match.id, match.home)}–${goals(match.id, match.away)}`}
              minute={minutes(source.clock)}
              kickoff={source.phase === 'pre' ? { title: t.kickoff, hint: demo ? fill(starter ? t.preHintLive : t.preHint, { demo: t.start, live: t.startMatch }) : t.liveHint } : undefined}
              guide={moving.guide}
              drop={drag && { over: drag.over, hint: drag.over ? t.release : t.dragTo }}
            >
              {air && <StaticCard card={air.card} team={teamOf(air.card)} geo={air} text={air} mode="live" badge={t.bLive} t={t} />}
              {s.pending && (
                <StaticCard
                  card={s.pending.card}
                  team={teamOf(s.pending.card)}
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
          </MonitorFit>

          <ControlBar
            t={t}
            title={title}
            sub={sub}
            mode={mode}
            countdown={countdown}
            sizePreset={sizePreset}
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
        </MonitorColumn>

        <InsightFeed
          t={t}
          items={items}
          emptyText={emptyText}
          filters={{
            chips,
            matchFilter: s.matchFilter,
            onFilter: (id) => dispatch({ type: 'setFilter', match: id }),
            focus: s.focus,
            onFocus: (focus) => dispatch({ type: 'setFocus', focus }),
            teams: focusTeams,
            players: source.players,
            teamById: teams,
          }}
          onPick={(id) => !isClickSuppressed() && dispatch({ type: 'select', id })}
          drag={dragHandlers}
        />
      </ConsoleMain>

      {drag && dragCard && (
        <DragGhost
          x={drag.x}
          y={drag.y}
          over={drag.over}
          meta={`${teamOf(dragCard).short} · ${topicLabel(t, dragCard.topic)} · ${minutes(dragCard.clock)}`}
          headline={textOf(dragCard).h}
          hint={drag.over ? t.release : t.dragTo}
        />
      )}

      <Toast
        open={!!toastOut && !!s.onAir[toastOut.id]}
        title={toastOut ? `${t.toastTitle} ${toastOut.name}` : ''}
        detail={toastOut ? s.onAir[toastOut.id]?.h : undefined}
        duration={TOAST_MS}
        onClose={() => dispatch({ type: 'dismissToast' })}
        action={
          <Button onClick={() => toastOut && pull(toastOut.id)}>{t.pull}</Button>
        }
      />
    </ConsoleRoot>
  )
}
