# Data model

## Coordinates and zones
- The pitch is **105 × 68 m**. The origin is the bottom-left from the home team's view, and the home team attacks +x. Stored as floats (ADR-005).
- **Zones are a view:** 5 lanes (y) × 9 bands (x), with finer cells inside both penalty areas. Binning happens at query time, so the grid can change freely.

## Envelope (every event)
```json
{ "event_id": "uuid", "match_id": "m-0007", "seq": 412, "type": "pass",
  "period": 1, "match_clock_s": 1834, "wall_ts": "2026-10-23T18:30:34Z",
  "team_id": "t-home", "player_id": "p-10", "x": 61.2, "y": 22.4,
  "payload": { } }
```
`seq` is monotonic per match, and consumers use it for ordering and dedupe.

The Python contract is implemented with Pydantic in `src/calacat_narrator/schemas.py`.
It validates event-specific payloads, timezone-aware timestamps, pitch bounds, and
1 Hz position snapshots. The anonymous `POST /ingest` Function accepts one JSON event
envelope per request, enforces a 64 KiB request-body limit, and publishes only validated
events to Event Hubs using the Function App managed identity. Invalid input returns
`400`, oversized input `413`, unsupported content types `415`, and Event Hubs failures
`503`. `src/calacat_narrator/catalog.py` loads and cross-validates the fictional team
and player catalog packaged in `src/calacat_narrator/data/`.

## Event types (MVP)
| type | payload |
|---|---|
| `pass` | `receiver_id, end_x, end_y, speed_kmh, outcome (complete/incomplete/out), height` |
| `shot` | `speed_kmh, outcome (goal/saved/off/blocked), goal_y, goal_z, body_part` |
| `duel` | `opponent_id, kind (tackle/1v1/aerial), won` |
| `pressure` | `target_id, duration_s` |
| `possession_change` | `from_team, to_team, cause (tackle/interception/out/foul)` |
| `foul` / `card` | `card (yellow/red), reason` |
| `set_piece` | `kind (free_kick/corner/penalty/throw), intent (pass/cross/shot), first_contact_x/y, first_contact_player_id` |
| `gk_action` | `kind (save/claim/punch/sweep), shot_event_id` |
| `sub` | `in_id, out_id` |
| `period` | `start/end` |

## Positions
Every 1 s, a `positions` message carries `{match_clock_s, players:[{id,x,y,speed_kmh}], ball:{x,y,z}}`. That's about 125k player rows per match. It's enough for heatmaps, routes, distance, top speed, Voronoi zone control, and the convex hull of defenders ("inside opponent's shape").

## Static metadata (fictional, ADR-006)
- **Player:** `id, name, number, position, club_id, nationality, height_cm, preferred_foot`.
- **Team:** `id, name, short_name, colors, squad[], form, table_position`.
- **Cut from MVP:** market value, contracts, injuries, trophies.

## Simulator
- Seeded (`--seed`), replay speed adjustable (`--speed 10`).
- A possession state machine over zones: each action is chosen by zone and team style (possession, direct, pressing). Players drift toward formation slots plus ball-side shift, and positions are smoothed.
- An optional **scenario director** schedules story beats (early red card, late comeback).
- `sim.baseline` runs about 50 matches and writes expected-at-minute distributions per metric, used by the signal gate.

Events are **facts only** (ADR-037): who, where, when, outcome, speed and body part.
Derived opinions such as xG, pass difficulty or "inside the opponent's shape" are never
emitted; the simulator uses internal probabilities to decide outcomes but keeps them to
itself. Every on-ball event is placed at the ball. Passes can go backwards; incomplete
passes and passes out of play hand the ball to the opponent with a `possession_change`
(`interception`, `out` or `tackle`), followed by the opponent's throw-in or, for a
clearance over a team's own goal line, a corner. Shot chance and conversion depend on
distance to goal. Fouls are committed by the defending team: in the box they become a
`set_piece` of kind `penalty` followed by the shot. A `gk_action` save follows only
`saved` shots, and the conceding team kicks off after a goal. Over 20 seeds the
simulator averages about 2.8 goals, 27 shots and 300+ possession changes per match
(`tests/test_simulator.py` checks the ranges).

Run the deterministic simulator with `python -m calacat_narrator.simulator
--seed 7 --speed 10 --output match.jsonl`. The JSON Lines file contains event and
1 Hz position records, each with a `record_type` discriminator. Repeating a seed
and duration produces identical output; `--speed` affects only pacing when posting
event records to an optional `--ingest-url`. Position samples remain in the output
file because `/ingest` accepts event envelopes.

### Judge-started matches (C16, ADR-044)

`POST /api/matches` starts a match on the server. The body is optional: `{"speed": 10}`
(an integer from 5 to 20; unknown fields are rejected), and the console sends none. The server
picks the seed, so the response is `202 {"match_id": "m-seed-<seed>", "speed": 10, "status":
"starting"}`. At most 2 matches run at once. When both are running, or a match kicked off
less than a minute ago, the request joins that match instead: `202 {"match_id": "m-seed-<seed>",
"status": "joined"}` (the one with the most time left), nothing is queued, and the daily count
doesn't move. 20 matches start per UTC day; after that the response is `429 {"error":
"daily_cap", "retry_after_s": n}` with a matching `Retry-After` header (`"busy"` only when a
request loses an ETag race). An invalid body returns `400`, a body that isn't JSON `415`, and a
Cosmos failure `503`.

The limits are documents in the `match-state` container under the partition `kickoffs`:
`slot-0` and `slot-1` hold `{running, started_at, busy_until}`, and `day-YYYY-MM-DD` holds
`{count}`. All writes are ETag-conditional. The accepted request goes on the `match-kickoffs`
storage queue; the queue-triggered `run_kickoff` function plays that seed into Event Hubs at its
speed, like the CLI's `--ingest-url` mode, and the pipeline narrates it like any other match.
An event that fails to publish is skipped and the match goes on; when the run ends or crashes,
its slot is released right away (`busy_until` set to now).

## Signals (Interpreter → Service Bus)
```json
{ "signal_id": "...", "match_id": "m-0007", "kind": "goal", "match_clock_s": 4020,
  "entity": {"team_id": "t-home"}, "value": 2,
  "event_context": {"event_type": "shot", "event_id": "evt-0042", "period": 2,
    "player_id": "p-nbr-09", "outcome": "goal", "speed_kmh": 104, "body_part": "foot"},
  "score": {"t-home": 2, "t-away": 1},
  "evidence_event_ids": ["evt-0042"], "tier": 1 }
```
Gate rules live in `src/calacat_narrator/data/signals.yaml` (ADR-013): `min_sample`,
`min_clock_s`, `milestones[]`, `hysteresis`, and `cooldown_s`. The current MVP uses
absolute thresholds; critical goal, red-card, and penalty events bypass the gate.
Threshold signals and critical signals are published to the Service Bus `signals`
topic with deterministic message IDs and evidence event IDs.

Goal and penalty signals also carry a bounded, typed `event_context` copied from the
single evidence event: shot outcome, speed, body part, period, or penalty intent.
The Goal & Shot specialist can use these values for its narrative; the application
adds the verified `shot_speed_kmh` to candidate metrics for goal evidence. Passing
signals carry the triggering pass's outcome. Event context IDs must
be included in signal evidence, and signal/candidate evidence IDs remain application-owned.

The Interpreter consumes Event Hubs in match-keyed partitions and stores one Cosmos DB
document per match in the `calacat/match-state` container, partitioned by `match_id`.
Documents include the latest sequence and event ID, clock/period, score, possession,
and team/player counters for passes, shots, goals, cards, duels, fouls, and other events.
Pass streaks are scoped to an uninterrupted possession. The current streak and its
`current_pass_streak_event_ids` contain only completed passes in that possession;
possession changes, failed passes, lost duels, fouls, shots, and changes of control
indicated by set-piece or goalkeeper-action events clear the affected streaks. Cards
alone do not imply a possession change. Repeated or stale sequence numbers are ignored;
Cosmos ETags protect concurrent writes.

## Agent candidates and cards

Every signal also carries `score`, the goals per team after the triggering event (teams
without a goal are omitted), and shot contexts carry the shooter's `player_id`.

The Container Apps agent runtime consumes one configured filtered subscription from
`signals` using Entra ID. The signal is **not** put in the prompt (ADR-038). Instead the
specialist gets one Agent Framework function tool, `get_event_facts`, which returns plain
facts built in code from the catalog and the signal, with no IDs or field names:

```json
{ "minute": "57'", "half": "second half", "team": "Northbridge Comets",
  "opponent": "Southmere Foxes", "player": "Bram Elsen",
  "score": "Northbridge Comets 2, Southmere Foxes 1",
  "event": "Bram Elsen scored for Northbridge Comets", "detail": "a 94 km/h strike" }
```

The Foundry `narrator-chat` deployment returns only a broadcast caption (headline ≤60
characters, `why_it_matters` ≤180 characters) and a salience, with low reasoning effort
and a Pydantic structured response. A validator rejects snake_case tokens, catalog,
event and UUID identifiers, raw seconds, and the words signal, evidence, data, metric or
match clock; a rejected draft fails the message, which goes through the existing Service
Bus retry and dead-letter fallback. The application attaches the validated signal's
metric, entity, `team_id`, `player_id`, match clock and evidence IDs; the model cannot
replace that provenance. Editor fallback cards use the same facts and limits in a fixed
caption voice ("Bram Elsen scores for Northbridge Comets" / "57' Bram Elsen scored for
Northbridge Comets with a 94 km/h strike. It's Northbridge Comets 2, Southmere Foxes 1."). Candidate IDs
are deterministic per specialist and signal, so retries use Service Bus duplicate
detection on the `candidates` topic.

```json
{
  "candidate_id": "uuid",
  "signal_id": "uuid",
  "match_id": "m-0007",
  "headline": "A second goal changes the balance",
  "why_it_matters": "The home side has now scored twice.",
  "metrics": { "goal": 2, "shot_speed_kmh": 104 },
  "evidence_event_ids": ["evt-0042"],
  "entity_ids": ["t-home"],
  "team_id": "t-home",
  "player_id": "p-nbr-09",
  "topic": "goal",
  "self_salience": 0.8,
  "ttl_s": 180,
  "match_clock_s": 4020
}
```

The `Card` contract adds a stable `card_id`, display `body`, and UTC `created_at` /
`expires_at` timestamps derived from `ttl_s`. It is defined for the Editor and browser
delivery stages; those stages own ranking, persistence, and publication. The Editor
persists the complete JSON object in the `calacat/cards` Cosmos container, partitioned
by `/match_id`. The Cosmos document `id` duplicates `card_id` for stable idempotency;
the per-item Cosmos `ttl` duplicates `ttl_s`. Cards are append-only: the Editor uses a
create-if-absent write and never rewrites a published card. `source` is `specialist` or
`fallback`; fallback cards keep the original signal, evidence IDs, metrics, topic, and
match clock. Push consumers should filter cards by `expires_at` rather than relying on
Cosmos TTL deletion notifications, use a `match-{match_id}` Web PubSub group, and
deduplicate deliveries by `card_id`.

**Review and Spanish (ADR-039, ADR-040).** After the Editor's budget picks a specialist
card, and before it is stored, a **Reviewer** agent on `narrator-chat` (low reasoning
effort, structured response) gets the same plain facts and the draft, and returns
`{decision: approve|revise|reject, headline, body, es: {headline, body}}`. Both languages
obey the 60/180 limits and the caption validator (which also rejects Spanish words such
as *datos*, *señal* or *segundos*), every number must appear in the facts, and each body
must give the minute. `approve` and `revise` store and push the reviewed card; `reject`
drops a non-critical card and frees the publish slot, but a critical card (`goal`,
`red_card`, `penalty`) is never dropped and publishes the template instead. A timeout
(`review_timeout_s` in `editor.yaml`, or the shorter `critical_review_timeout_s` for
critical topics), an error, or invalid output publishes the templated fallback card
instead. Fallback cards are written from EN and ES templates and are never reviewed.
Every stored card carries `i18n.es`; `score` (goals per team after the event) and, for
shots, `body_part` (`foot` / `head` / `other`) travel from the signal.

```json
{
  "id": "stable-card-uuid",
  "card_id": "stable-card-uuid",
  "candidate_id": "candidate-uuid",
  "signal_id": "signal-uuid",
  "match_id": "m-0007",
  "headline": "Bram Elsen doubles the lead",
  "body": "68' Bram Elsen scores with a 104 km/h strike. It's 2-0 to Northbridge Comets.",
  "i18n": { "es": { "headline": "Bram Elsen amplía la ventaja",
    "body": "68' Bram Elsen marca con un remate a 104 km/h. Northbridge Comets gana 2-0." } },
  "metrics": { "goal": 2, "shot_speed_kmh": 104 },
  "evidence_event_ids": ["evt-0042"],
  "entity_ids": ["t-home"],
  "team_id": "t-home",
  "player_id": "p-nbr-09",
  "score": { "t-home": 2 },
  "body_part": "foot",
  "topic": "goal",
  "salience": 1.0,
  "source": "specialist",
  "match_clock_s": 4020,
  "ttl_s": 180,
  "ttl": 180,
  "created_at": "2026-10-23T18:30:00Z",
  "expires_at": "2026-10-23T18:33:00Z"
}
```

## Browser delivery

The Editor sends each card's JSON to the `match-{match_id}` group of the `cards` Web PubSub
hub right after storing it in Cosmos, using the shared workload identity. A failed push is
logged and not retried (the card is already stored), and Service Bus redelivery can push a
card twice, so a browser must deduplicate by `card_id`.

HTTP routes use the `api` prefix (`host.json`). The GitHub Pages console calls them cross-origin, so the Function App must allow that origin in CORS (ADR-043).
Browsers call `GET /api/negotiate?match_id=m-0007` and connect to the returned WebSocket
`url`. The URL is valid for 60 minutes, joins only that match's group, and grants no
send or join roles. Invalid match IDs return `400`; Web PubSub failures return `503`.

After the socket opens, and every 30 s while it stays open, the console calls
`GET /api/cards?match_id=m-0007`. It returns `{cards, score, match_clock_s}`: unexpired cards
from a single-partition query on `cards`, plus `score` (goals per team ID) and `match_clock_s`
from the interpreter's match state. Subscribing first and fetching second means no card is lost
between the two. Invalid match IDs return `400`; Cosmos failures return `503`.
