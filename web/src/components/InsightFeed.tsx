import type { PointerEvent } from 'react'
import { minutes, topicLabel, type Strings } from '../i18n'
import type { FeedCard, Player, Team } from '../types'
import { Chevron } from './Header'
import { Silhouette } from './Silhouette'

export interface FeedItem {
  card: FeedCard
  team: Team
  text: { h: string; b: string }
  meta: string
  isNew: boolean
  liveOn: string[]
  selected: boolean
  /** Live on the selected output: locked, only Pull from air acts on it. */
  locked: boolean
  lifted: boolean
}

export interface MatchChip {
  id: string
  label: string
  count: number
  program: boolean
}

interface Props {
  t: Strings
  items: FeedItem[]
  emptyText: string
  chips: MatchChip[]
  matchFilter: string
  onFilter: (id: string) => void
  focus: string
  onFocus: (focus: string) => void
  teams: Team[]
  players: Player[]
  teamById: Record<string, Team>
  onPick: (id: string) => void
  drag: {
    down: (e: PointerEvent<HTMLButtonElement>, id: string) => void
    move: (e: PointerEvent<HTMLButtonElement>) => void
    up: (e: PointerEvent<HTMLButtonElement>) => void
    cancel: () => void
  }
}

export function InsightFeed({ t, items, emptyText, chips, matchFilter, onFilter, focus, onFocus, teams, players, teamById, onPick, drag }: Props) {
  return (
    <aside className="feedcol" aria-labelledby="feed-h">
      <div className="feedhead">
        <h2 id="feed-h" className="lbl">{t.feed}</h2>
        <span className="kbd">{items.length} {t.cards}</span>
      </div>
      <div className="chips" role="group" aria-label={t.games}>
        {chips.map((m) => (
          <button key={m.id} type="button" className="chip" aria-pressed={matchFilter === m.id} onClick={() => onFilter(m.id)}>
            <span>{m.label}</span>
            {m.program && <span className="pg">PGM</span>}
            <span className="cnt">{m.count}</span>
          </button>
        ))}
      </div>
      <div className="focusrow">
        <label className="lbl" htmlFor="focus-select">{t.focus}</label>
        <span className="selwrap grow">
          <select id="focus-select" className="btn" value={focus} onChange={(e) => onFocus(e.target.value)}>
            <option value="">{t.focusNone}</option>
            <optgroup label={t.teams}>
              {teams.map((tm) => <option key={tm.id} value={`team:${tm.id}`}>{tm.name}</option>)}
            </optgroup>
            <optgroup label={t.players}>
              {players.map((p) => (
                <option key={p.id} value={`player:${p.id}`}>#{p.num} {p.name} · {teamById[p.team]?.short ?? ''}</option>
              ))}
            </optgroup>
          </select>
          <Chevron />
        </span>
      </div>
      {items.length === 0 && (
        <div className="panel empty">
          <span className="disp" aria-hidden="true">{t.waiting}</span>
          <p>{emptyText}</p>
        </div>
      )}
      <ol className="feedlist" aria-live="polite" aria-relevant="additions">
        {items.map(({ card, team, text, meta, isNew, liveOn, selected, locked, lifted }) => (
          <li key={card.id}>
            <button
              type="button"
              data-card-id={card.id}
              className={`card${selected ? ' sel' : ''}${locked ? ' air' : ''}${lifted ? ' lifted' : ''}`}
              aria-pressed={selected}
              aria-disabled={locked}
              aria-describedby="feed-tip"
              onClick={() => !locked && onPick(card.id)}
              onPointerDown={(e) => drag.down(e, card.id)}
              onPointerMove={drag.move}
              onPointerUp={drag.up}
              onPointerCancel={drag.cancel}
            >
              <span className="crow">
                <span className="tchip">{team.short}</span>
                <span className={`pill${card.critical ? ' hot' : ''}`}>{topicLabel(t, card.topic)}</span>
                <span className="cmin">{minutes(card.clock)}</span>
                <span className="grow" />
                {isNew && <span className="pill new">{t.new}</span>}
                {liveOn.length > 0 && <span className="pill red"><span className="dot blink" />{t.live} · {liveOn.join(', ')}</span>}
              </span>
              <span className="cmain">
                <Silhouette team={team} player={card.player} t={t} className="sil" />
                <span className="ctext">
                  {card.player && <span className="cpl">#{card.player.num} {card.player.name}</span>}
                  <span className="disp chead">{text.h}</span>
                  <span className="cbody">{text.b}</span>
                </span>
              </span>
              <span className="cfoot">
                <span className="cmeta">{meta}</span>
                <span className="meter"><span style={{ width: `${Math.round(card.salience * 100)}%` }} /></span>
                <span className="csal">{t.salience} {card.salience.toFixed(2)}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
      <p id="feed-tip" className="kbd">{t.feedTip}</p>
    </aside>
  )
}
