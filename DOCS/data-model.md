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
| `pass` | `receiver_id, end_x, end_y, speed_kmh, outcome (complete/incomplete/out), height, difficulty (0–1), inside_opp_shape` |
| `shot` | `speed_kmh, outcome (goal/saved/off/blocked), goal_y, goal_z, xg, body_part` |
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

Run the deterministic simulator with `python -m calacat_narrator.simulator
--seed 7 --speed 10 --output match.jsonl`. The JSON Lines file contains event and
1 Hz position records, each with a `record_type` discriminator. Repeating a seed
and duration produces identical output; `--speed` affects only pacing when posting
event records to an optional `--ingest-url`. Position samples remain in the output
file because `/ingest` accepts event envelopes.

## Signals (Interpreter → Service Bus)
```json
{ "signal_id": "...", "match_id": "m-0007", "kind": "goal", "match_clock_s": 4020,
  "entity": {"team_id": "t-home"}, "value": 2,
  "event_context": {"event_type": "shot", "event_id": "evt-0042", "period": 2,
    "outcome": "goal", "speed_kmh": 104, "xg": 0.74, "body_part": "foot"},
  "evidence_event_ids": ["evt-0042"], "tier": 1 }
```
Gate rules live in `src/calacat_narrator/data/signals.yaml` (ADR-013): `min_sample`,
`min_clock_s`, `milestones[]`, `hysteresis`, and `cooldown_s`. The current MVP uses
absolute thresholds; critical goal, red-card, and penalty events bypass the gate.
Threshold signals and critical signals are published to the Service Bus `signals`
topic with deterministic message IDs and evidence event IDs.

Goal and penalty signals also carry a bounded, typed `event_context` copied from the
single evidence event: shot outcome, xG, speed, body part, period, or penalty intent.
The Goal & Shot specialist can use these values for its narrative; the application
adds verified `xg` and `shot_speed_kmh` to candidate metrics for goal evidence.
Passing signals may carry the triggering pass's outcome, difficulty, and whether its
reception was inside the opponent's shape. The Build-up & Passing specialist can use
those details only for that evidenced pass; the application adds `pass_difficulty` and
`reception_inside_opponent_shape` (0 or 1) to candidate metrics. Event context IDs must
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

The Container Apps agent runtime consumes one configured filtered subscription from
`signals` using Entra ID. It asks the Foundry `narrator-chat` deployment for only the
candidate headline, explanation, and salience, with low reasoning effort and a Pydantic
structured response. The application attaches the validated signal's metric, entity,
match clock, and evidence IDs; the model cannot replace that provenance. Candidate IDs
are deterministic per specialist and signal, so retries use Service Bus duplicate
detection on the `candidates` topic.

```json
{
  "candidate_id": "uuid",
  "signal_id": "uuid",
  "match_id": "m-0007",
  "headline": "A second goal changes the balance",
  "why_it_matters": "The home side has now scored twice.",
  "metrics": { "goal": 2, "shot_speed_kmh": 104, "xg": 0.74 },
  "evidence_event_ids": ["evt-0042"],
  "entity_ids": ["t-home"],
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

```json
{
  "id": "stable-card-uuid",
  "card_id": "stable-card-uuid",
  "candidate_id": "candidate-uuid",
  "signal_id": "signal-uuid",
  "match_id": "m-0007",
  "headline": "A second goal changes the balance",
  "body": "The home side has now scored twice.",
  "metrics": { "goal": 2 },
  "evidence_event_ids": ["evt-0042"],
  "entity_ids": ["t-home"],
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
