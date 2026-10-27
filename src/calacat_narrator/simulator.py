"""Deterministic seeded match simulation and CLI transports."""

import argparse
import json
import math
import os
import random
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .catalog import FootballCatalog, Player, load_catalog
from .schemas import (
    MatchEvent,
    PeriodPayload,
    PlayerPosition,
    PositionSnapshot,
    ShotPayload,
)

MATCH_DURATION_S = 90 * 60
KICKOFF = datetime(2026, 1, 1, tzinfo=UTC)
HOME_FORMATION = (
    (6, 34),
    (24, 9),
    (24, 25),
    (24, 43),
    (24, 59),
    (43, 15),
    (46, 34),
    (43, 53),
    (69, 10),
    (71, 34),
    (69, 58),
)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


class SeededMatch:
    """Stateful deterministic simulation for one synthetic match."""

    def __init__(self, seed: int, duration_s: int, catalog: FootballCatalog) -> None:
        if duration_s < 2:
            raise ValueError("duration_s must be at least 2 seconds")
        self.seed = seed
        self.duration_s = duration_s
        self.halfway_s = duration_s // 2
        self.rng = random.Random(seed)
        self.catalog = catalog
        self.match_id = f"m-seed-{seed}"
        self.home_team_id = catalog.teams[0].id
        self.away_team_id = catalog.teams[1].id
        self.players = {player.id: player for player in catalog.players}
        self.rosters = {
            team.id: [self.players[player_id] for player_id in team.squad] for team in catalog.teams
        }
        self.possession_team_id = self.home_team_id
        self.ball_x = 52.5
        self.ball_y = 34.0
        self.sequence = 0
        self.next_action_s = self.rng.randint(2, 5)
        self.previous_positions: dict[str, tuple[float, float]] = {}

    def _period(self, clock_s: int) -> int:
        return 1 if clock_s <= self.halfway_s else 2

    def _event(
        self,
        *,
        event_type: str,
        clock_s: int,
        payload: object,
        player: Player | None = None,
        team_id: str | None = None,
        position: tuple[float, float] | None = None,
    ) -> MatchEvent:
        self.sequence += 1
        x, y = position or (None, None)
        return MatchEvent.model_validate(
            {
                "event_id": f"{self.match_id}-e{self.sequence:06d}",
                "match_id": self.match_id,
                "seq": self.sequence,
                "type": event_type,
                "period": self._period(clock_s),
                "match_clock_s": clock_s,
                "wall_ts": KICKOFF + timedelta(seconds=clock_s),
                "team_id": team_id,
                "player_id": player.id if player else None,
                "x": x,
                "y": y,
                "payload": payload,
            }
        )

    def _locations(self) -> dict[str, tuple[float, float, float]]:
        locations = {}
        attacking_shift = _clamp((self.ball_x - 52.5) * 0.12, -7, 7)
        for team_id, roster in self.rosters.items():
            is_home = team_id == self.home_team_id
            for index, player in enumerate(roster):
                home_x, base_y = HOME_FORMATION[index]
                base_x = home_x if is_home else 105 - home_x
                base_y = base_y if is_home else 68 - base_y
                target_x = _clamp(base_x + attacking_shift, 1, 104)
                target_y = _clamp(base_y + (self.ball_y - 34) * 0.1, 1, 67)
                previous_x, previous_y = self.previous_positions.get(
                    player.id, (target_x, target_y)
                )
                x = _clamp(
                    previous_x + (target_x - previous_x) * 0.12 + self.rng.uniform(-0.45, 0.45),
                    0,
                    105,
                )
                y = _clamp(
                    previous_y + (target_y - previous_y) * 0.12 + self.rng.uniform(-0.45, 0.45),
                    0,
                    68,
                )
                speed_kmh = min(30.0, math.hypot(x - previous_x, y - previous_y) * 3.6)
                self.previous_positions[player.id] = (x, y)
                locations[player.id] = (round(x, 2), round(y, 2), round(speed_kmh, 2))
        return locations

    def _position_snapshot(self, clock_s: int) -> PositionSnapshot:
        locations = self._locations()
        return PositionSnapshot(
            match_id=self.match_id,
            period=self._period(clock_s),
            match_clock_s=clock_s,
            players=[
                PlayerPosition(
                    id=player.id,
                    x=locations[player.id][0],
                    y=locations[player.id][1],
                    speed_kmh=locations[player.id][2],
                )
                for player in self.catalog.players
            ],
            ball={"x": round(self.ball_x, 2), "y": round(self.ball_y, 2), "z": 0},
        )

    def _actor_location(
        self, player: Player, locations: dict[str, tuple[float, float, float]]
    ) -> tuple[float, float]:
        x, y, _ = locations[player.id]
        return x, y

    def _advance_ball(self, team_id: str) -> None:
        direction = 1 if team_id == self.home_team_id else -1
        self.ball_x = _clamp(self.ball_x + direction * self.rng.uniform(2, 10), 1, 104)
        self.ball_y = _clamp(self.ball_y + self.rng.uniform(-8, 8), 1, 67)

    def _action_events(
        self,
        clock_s: int,
        locations: dict[str, tuple[float, float, float]],
    ) -> list[MatchEvent]:
        team_id = self.possession_team_id
        opponent_id = self.away_team_id if team_id == self.home_team_id else self.home_team_id
        roster = self.rosters[team_id]
        opponents = self.rosters[opponent_id]
        actor = self.rng.choice(roster[1:])
        actor_position = self._actor_location(actor, locations)
        direction = 1 if team_id == self.home_team_id else -1
        is_attacking_third = self.ball_x >= 76 if direction == 1 else self.ball_x <= 29
        events: list[MatchEvent] = []

        if is_attacking_third and self.rng.random() < 0.18:
            distance_to_goal = self.ball_x if direction < 0 else 105 - self.ball_x
            xg = round(
                _clamp(0.42 - distance_to_goal * 0.004 + self.rng.uniform(-0.08, 0.08), 0.02, 0.5),
                3,
            )
            outcome = (
                "goal"
                if self.rng.random() < xg * 0.65
                else self.rng.choices(["saved", "off", "blocked"], weights=[0.42, 0.38, 0.20], k=1)[
                    0
                ]
            )
            shot = self._event(
                event_type="shot",
                clock_s=clock_s,
                team_id=team_id,
                player=actor,
                position=actor_position,
                payload=ShotPayload(
                    speed_kmh=round(self.rng.uniform(48, 122), 1),
                    outcome=outcome,
                    goal_y=round(self.rng.uniform(0.1, 7.22), 2),
                    goal_z=round(self.rng.uniform(0.1, 2.4), 2),
                    xg=xg,
                    body_part=self.rng.choice(["foot", "head", "other"]),
                ),
            )
            events.append(shot)
            if outcome != "goal":
                goalkeeper = opponents[0]
                events.append(
                    self._event(
                        event_type="gk_action",
                        clock_s=clock_s,
                        team_id=opponent_id,
                        player=goalkeeper,
                        position=self._actor_location(goalkeeper, locations),
                        payload={
                            "kind": self.rng.choice(["save", "claim", "punch"]),
                            "shot_event_id": shot.event_id,
                        },
                    )
                )
                self.possession_team_id = opponent_id
            self.ball_x, self.ball_y = 52.5, 34.0
            return events

        action = self.rng.choices(
            ["pass", "duel", "pressure", "turnover", "foul", "set_piece"],
            weights=[72, 8, 8, 8, 3, 1],
            k=1,
        )[0]
        if action == "pass":
            receiver = self.rng.choice([player for player in roster if player.id != actor.id])
            outcome = self.rng.choices(["complete", "incomplete", "out"], weights=[86, 10, 4], k=1)[
                0
            ]
            end_x = _clamp(self.ball_x + direction * self.rng.uniform(1, 16), 0, 105)
            end_y = _clamp(self.ball_y + self.rng.uniform(-12, 12), 0, 68)
            events.append(
                self._event(
                    event_type="pass",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={
                        "receiver_id": receiver.id,
                        "end_x": round(end_x, 2),
                        "end_y": round(end_y, 2),
                        "speed_kmh": round(self.rng.uniform(18, 82), 1),
                        "outcome": outcome,
                        "height": self.rng.choices(
                            ["ground", "low", "high"], weights=[75, 15, 10], k=1
                        )[0],
                        "difficulty": round(self.rng.uniform(0.05, 0.95), 2),
                        "inside_opp_shape": self.ball_x > 60
                        if team_id == self.home_team_id
                        else self.ball_x < 45,
                    },
                )
            )
            if outcome == "complete":
                self.ball_x, self.ball_y = end_x, end_y
            else:
                self.possession_team_id = opponent_id
                self.ball_x, self.ball_y = end_x, end_y
        elif action == "duel":
            opponent = self.rng.choice(opponents[1:])
            won = self.rng.random() < 0.52
            events.append(
                self._event(
                    event_type="duel",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={"opponent_id": opponent.id, "kind": "1v1", "won": won},
                )
            )
            if not won:
                self.possession_team_id = opponent_id
        elif action == "pressure":
            target = self.rng.choice(opponents[1:])
            events.append(
                self._event(
                    event_type="pressure",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={
                        "target_id": target.id,
                        "duration_s": round(self.rng.uniform(1, 8), 1),
                    },
                )
            )
        elif action == "turnover":
            cause = self.rng.choice(["tackle", "interception", "out", "foul"])
            events.append(
                self._event(
                    event_type="possession_change",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={"from_team": team_id, "to_team": opponent_id, "cause": cause},
                )
            )
            self.possession_team_id = opponent_id
            if cause == "out":
                events.append(
                    self._event(
                        event_type="set_piece",
                        clock_s=clock_s,
                        team_id=opponent_id,
                        player=None,
                        position=(self.ball_x, self.ball_y),
                        payload={
                            "kind": self.rng.choice(["corner", "throw"]),
                            "intent": self.rng.choice(["pass", "cross"]),
                            "first_contact_x": round(self.ball_x, 2),
                            "first_contact_y": round(self.ball_y, 2),
                            "first_contact_player_id": None,
                        },
                    )
                )
        elif action == "foul":
            events.append(
                self._event(
                    event_type="foul",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={"reason": self.rng.choice(["late challenge", "holding", "trip"])},
                )
            )
            if self.rng.random() < 0.08:
                events.append(
                    self._event(
                        event_type="card",
                        clock_s=clock_s,
                        team_id=team_id,
                        player=actor,
                        position=actor_position,
                        payload={
                            "card": self.rng.choices(["yellow", "red"], weights=[97, 3], k=1)[0],
                            "reason": "unsporting conduct",
                        },
                    )
                )
            self.possession_team_id = opponent_id
        else:
            kind = "corner" if self.rng.random() < 0.6 else "free_kick"
            events.append(
                self._event(
                    event_type="set_piece",
                    clock_s=clock_s,
                    team_id=team_id,
                    player=actor,
                    position=actor_position,
                    payload={
                        "kind": kind,
                        "intent": self.rng.choice(["pass", "cross", "shot"]),
                        "first_contact_x": round(self.ball_x, 2),
                        "first_contact_y": round(self.ball_y, 2),
                        "first_contact_player_id": self.rng.choice(roster).id,
                    },
                )
            )

        self._advance_ball(self.possession_team_id)
        return events

    def records(self) -> Iterator[MatchEvent | PositionSnapshot]:
        for clock_s in range(self.duration_s + 1):
            if clock_s == 0:
                yield self._event(
                    event_type="period",
                    clock_s=clock_s,
                    payload=PeriodPayload(action="start"),
                )
            if clock_s == self.halfway_s:
                yield self._event(
                    event_type="period",
                    clock_s=clock_s,
                    payload=PeriodPayload(action="end"),
                )
            if clock_s == self.halfway_s + 1:
                yield self._event(
                    event_type="period",
                    clock_s=clock_s,
                    payload=PeriodPayload(action="start"),
                )

            snapshot = self._position_snapshot(clock_s)
            yield snapshot
            locations = {
                player.id: (player.x, player.y, player.speed_kmh) for player in snapshot.players
            }
            if clock_s >= self.next_action_s:
                yield from self._action_events(clock_s, locations)
                self.next_action_s = clock_s + self.rng.randint(2, 7)

            if clock_s == self.duration_s:
                yield self._event(
                    event_type="period",
                    clock_s=clock_s,
                    payload=PeriodPayload(action="end"),
                )


def simulate_match(
    seed: int,
    duration_s: int = MATCH_DURATION_S,
    catalog: FootballCatalog | None = None,
) -> Iterator[MatchEvent | PositionSnapshot]:
    """Yield a deterministic 1 Hz position stream interleaved with match events."""
    match_catalog = catalog if catalog is not None else load_catalog()
    yield from SeededMatch(seed, duration_s, match_catalog).records()


def serialize_record(record: MatchEvent | PositionSnapshot) -> str:
    """Encode one output JSONL record with an explicit event/position discriminator."""
    record_type = "event" if isinstance(record, MatchEvent) else "positions"
    return json.dumps(
        {
            "record_type": record_type,
            "data": record.model_dump(mode="json", exclude_none=True),
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _duration_seconds(value: str) -> int:
    parsed = int(value)
    if parsed < 2:
        raise argparse.ArgumentTypeError("must be at least 2 seconds")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


INGEST_KEY_ENV = "INGEST_FUNCTION_KEY"


def _post_event(url: str, event: MatchEvent, function_key: str | None = None) -> None:
    body = json.dumps(event.model_dump(mode="json", exclude_none=True)).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if function_key:
        headers["x-functions-key"] = function_key
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10):
            pass
    except HTTPError as error:
        hint = f"; set {INGEST_KEY_ENV} to the Function key" if error.code == 401 else ""
        raise RuntimeError(
            f"Failed to POST event {event.event_id} to {url}: {error}{hint}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Failed to POST event {event.event_id} to {url}: {error}") from error


def _validate_ingest_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--ingest-url must be an absolute HTTP(S) URL")
    return url


def _open_output(path: str) -> tuple[TextIO, bool]:
    if path == "-":
        return sys.stdout, False
    return Path(path).open("w", encoding="utf-8", newline="\n"), True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a seeded synthetic football match.")
    parser.add_argument("--seed", type=int, default=7, help="deterministic match seed")
    parser.add_argument(
        "--duration-s",
        type=_duration_seconds,
        default=MATCH_DURATION_S,
        help="match duration in simulated seconds (default: 5400)",
    )
    parser.add_argument(
        "--speed",
        type=_positive_float,
        default=10,
        help="playback multiplier for ingest requests; does not change match output",
    )
    parser.add_argument(
        "--output",
        default="match.jsonl",
        help="JSON Lines output path, or '-' for stdout (default: match.jsonl)",
    )
    parser.add_argument(
        "--ingest-url",
        help=f"optional HTTP(S) /ingest URL; event envelopes are POSTed as JSON with the "
        f"Function key from {INGEST_KEY_ENV} (unset is fine for a local `func start`)",
    )
    args = parser.parse_args(argv)

    ingest_url = _validate_ingest_url(args.ingest_url) if args.ingest_url else None
    # From the environment only, so the key never lands in shell history or process lists.
    function_key = os.environ.get(INGEST_KEY_ENV) or None
    output, should_close = _open_output(args.output)
    previous_snapshot_s: int | None = None
    try:
        for record in simulate_match(args.seed, args.duration_s):
            output.write(serialize_record(record))
            output.write("\n")
            if isinstance(record, MatchEvent) and ingest_url:
                _post_event(ingest_url, record, function_key)
            elif isinstance(record, PositionSnapshot) and ingest_url:
                if previous_snapshot_s is not None:
                    elapsed_s = record.match_clock_s - previous_snapshot_s
                    time.sleep(elapsed_s / args.speed)
                previous_snapshot_s = record.match_clock_s
    finally:
        if should_close:
            output.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
