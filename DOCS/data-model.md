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

## Signals (Interpreter → Service Bus)
```json
{ "signal_id": "...", "match_id": "...", "kind": "pass_streak", "match_clock_s": 2210,
  "entity": {"team_id": "t-home"}, "value": 17, "baseline": {"mean": 6.1, "p95": 13},
  "evidence_event_ids": ["..."], "tier": 2 }
```
Gate rules live in `signals.yaml` (ADR-013): `min_sample`, `min_clock_s`, `deviation (sigma | percentile)`, `milestones[]`, `window_s + hysteresis`, `cooldown_s`. Critical kinds (goal, red card, penalty) bypass the gate.
