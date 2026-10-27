"""Deterministic seeded match simulation and CLI transports."""

import argparse
import json
import math
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
    CardPayload,
    DuelPayload,
    FoulPayload,
    GoalkeeperActionPayload,
    MatchEvent,
    PassPayload,
    PeriodPayload,
    PlayerPosition,
    PositionSnapshot,
    PossessionChangePayload,
    PressurePayload,
    SetPiecePayload,
    ShotPayload,
)

MATCH_DURATION_S = 90 * 60
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
BOX_DEPTH = 16.5
BOX_HALF_WIDTH = 20.16
PENALTY_SPOT = 11.0
# Internal model parameters: they decide outcomes but are never emitted (ADR-037).
SHOT_RANGE = 32.0
PENALTY_CONVERSION = 0.76
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

    # ---- Geometry. Home attacks +x; every on-ball event happens where the ball is.

    def _opponent(self, team_id: str) -> str:
        return self.away_team_id if team_id == self.home_team_id else self.home_team_id

    def _direction(self, team_id: str) -> int:
        return 1 if team_id == self.home_team_id else -1

    def _goal_distance(self, team_id: str) -> float:
        goal_x = PITCH_LENGTH if team_id == self.home_team_id else 0.0
        return math.hypot(goal_x - self.ball_x, PITCH_WIDTH / 2 - self.ball_y)

    def _in_attacking_box(self, team_id: str) -> bool:
        depth = PITCH_LENGTH - self.ball_x if team_id == self.home_team_id else self.ball_x
        return depth <= BOX_DEPTH and abs(self.ball_y - PITCH_WIDTH / 2) <= BOX_HALF_WIDTH

    def _in_own_third(self, team_id: str) -> bool:
        return self.ball_x < 35 if team_id == self.home_team_id else self.ball_x > 70

    def _ball(self) -> tuple[float, float]:
        return round(self.ball_x, 2), round(self.ball_y, 2)

    def _near_ball(
        self,
        team_id: str,
        locations: dict[str, tuple[float, float, float]],
        count: int,
    ) -> Player:
        """Pick one of the `count` outfield players closest to the ball, so play stays local."""
        outfield = sorted(
            self.rosters[team_id][1:],
            key=lambda p: math.hypot(
                locations[p.id][0] - self.ball_x, locations[p.id][1] - self.ball_y
            ),
        )
        return self.rng.choice(outfield[:count])

    def _turnover(self, clock_s: int, player: Player, team_id: str, cause: str) -> MatchEvent:
        """Hand the ball to the opponent and record it as an observed possession change."""
        opponent_id = self._opponent(team_id)
        self.possession_team_id = opponent_id
        return self._event(
            event_type="possession_change",
            clock_s=clock_s,
            team_id=team_id,
            player=player,
            position=self._ball(),
            payload=PossessionChangePayload(from_team=team_id, to_team=opponent_id, cause=cause),
        )

    def _restart(
        self,
        clock_s: int,
        team_id: str,
        kind: str,
        intent: str,
        taker: Player,
    ) -> MatchEvent:
        self.possession_team_id = team_id
        return self._event(
            event_type="set_piece",
            clock_s=clock_s,
            team_id=team_id,
            player=taker,
            position=self._ball(),
            payload=SetPiecePayload(
                kind=kind,
                intent=intent,
                first_contact_x=round(self.ball_x, 2),
                first_contact_y=round(self.ball_y, 2),
            ),
        )

    def _corner(
        self, clock_s: int, team_id: str, locations: dict[str, tuple[float, float, float]]
    ) -> MatchEvent:
        self.ball_x = PITCH_LENGTH - 0.5 if team_id == self.home_team_id else 0.5
        self.ball_y = 0.5 if self.ball_y < PITCH_WIDTH / 2 else PITCH_WIDTH - 0.5
        event = self._restart(
            clock_s, team_id, "corner", "cross", self._near_ball(team_id, locations, 4)
        )
        # The delivery drops around the penalty spot.
        self.ball_x = PITCH_LENGTH - 10 if team_id == self.home_team_id else 10.0
        self.ball_y = PITCH_WIDTH / 2 + self.rng.uniform(-8, 8)
        return event

    # ---- Actions

    def _shot(
        self,
        clock_s: int,
        team_id: str,
        shooter: Player,
        locations: dict[str, tuple[float, float, float]],
        *,
        penalty: bool = False,
    ) -> list[MatchEvent]:
        """Shoot from the ball's position. Conversion depends on distance and is never emitted."""
        opponent_id = self._opponent(team_id)
        distance = self._goal_distance(team_id)
        header = not penalty and distance < 14 and self.rng.random() < 0.25
        if penalty:
            goal_chance = PENALTY_CONVERSION
        else:
            goal_chance = _clamp(0.48 * math.exp(-distance / 7.5), 0.01, 0.5)
            if header:
                goal_chance *= 0.6
        if self.rng.random() < goal_chance:
            outcome = "goal"
        else:
            outcome = self.rng.choices(["saved", "off", "blocked"], weights=[35, 40, 25], k=1)[0]
        speed = self.rng.uniform(30, 60) if header else self.rng.uniform(55, 120)
        shot = self._event(
            event_type="shot",
            clock_s=clock_s,
            team_id=team_id,
            player=shooter,
            position=self._ball(),
            payload=ShotPayload(
                speed_kmh=round(speed, 1),
                outcome=outcome,
                goal_y=round(self.rng.uniform(0.1, 7.22), 2),
                goal_z=round(self.rng.uniform(0.1, 2.4), 2),
                body_part="head" if header else "foot",
            ),
        )
        events = [shot]
        goal_line_x = PITCH_LENGTH - 3 if team_id == self.home_team_id else 3.0
        if outcome == "goal":
            # The conceding team kicks off from the centre spot.
            self.possession_team_id = opponent_id
            self.ball_x, self.ball_y = PITCH_LENGTH / 2, PITCH_WIDTH / 2
        elif outcome == "saved":
            self.ball_x, self.ball_y = goal_line_x, PITCH_WIDTH / 2
            events.append(
                self._event(
                    event_type="gk_action",
                    clock_s=clock_s,
                    team_id=opponent_id,
                    player=self.rosters[opponent_id][0],
                    position=self._ball(),
                    payload=GoalkeeperActionPayload(kind="save", shot_event_id=shot.event_id),
                )
            )
            if self.rng.random() < 0.3:
                events.append(self._corner(clock_s, team_id, locations))  # parried behind
            else:
                self.possession_team_id = opponent_id
        elif outcome == "blocked" and self.rng.random() < 0.35:
            events.append(self._corner(clock_s, team_id, locations))  # deflected behind
        else:
            # Off target (goal kick) or a block cleared by the defence.
            self.ball_x, self.ball_y = goal_line_x, PITCH_WIDTH / 2
            cause = "out" if outcome == "off" else "tackle"
            events.append(self._turnover(clock_s, shooter, team_id, cause))
        return events

    def _pass(
        self,
        clock_s: int,
        team_id: str,
        passer: Player,
        locations: dict[str, tuple[float, float, float]],
    ) -> list[MatchEvent]:
        direction = self._direction(team_id)
        forward = self.rng.uniform(-12, 20)  # negative: back or square passes
        raw_x = self.ball_x + direction * forward
        raw_y = self.ball_y + self.rng.uniform(-16, 16)
        out_side = not 0 <= raw_y <= PITCH_WIDTH
        out_end = not 0 <= raw_x <= PITCH_LENGTH
        end_x, end_y = _clamp(raw_x, 0, PITCH_LENGTH), _clamp(raw_y, 0, PITCH_WIDTH)
        completion = 0.97 - 0.007 * max(0.0, forward)
        if self._goal_distance(team_id) < 35:
            completion -= 0.08
        if out_side or out_end:
            outcome = "out"
        elif self.rng.random() < _clamp(completion, 0.45, 0.95):
            outcome = "complete"
        else:
            outcome = "incomplete"
        receiver = min(
            self.rng.sample([p for p in self.rosters[team_id] if p.id != passer.id], 4),
            key=lambda p: math.hypot(locations[p.id][0] - end_x, locations[p.id][1] - end_y),
        )
        height = self.rng.choices(["ground", "low", "high"], weights=[75, 15, 10], k=1)[0]
        events = [
            self._event(
                event_type="pass",
                clock_s=clock_s,
                team_id=team_id,
                player=passer,
                position=self._ball(),
                payload=PassPayload(
                    receiver_id=receiver.id,
                    end_x=round(end_x, 2),
                    end_y=round(end_y, 2),
                    speed_kmh=round(self.rng.uniform(18, 82), 1),
                    outcome=outcome,
                    height=height,
                ),
            )
        ]
        cleared_own_line = out_end and self._in_own_third(team_id)
        self.ball_x, self.ball_y = end_x, end_y
        opponent_id = self._opponent(team_id)
        if outcome == "incomplete":
            events.append(self._turnover(clock_s, passer, team_id, "interception"))
        elif outcome == "out":
            events.append(self._turnover(clock_s, passer, team_id, "out"))
            if out_side:
                taker = self._near_ball(opponent_id, locations, 3)
                events.append(self._restart(clock_s, opponent_id, "throw", "pass", taker))
            elif cleared_own_line:
                events.append(self._corner(clock_s, opponent_id, locations))
            # Otherwise over the opponent's goal line: a goal kick for the opponent.
        return events

    def _foul(
        self,
        clock_s: int,
        team_id: str,
        locations: dict[str, tuple[float, float, float]],
    ) -> list[MatchEvent]:
        """A defender fouls the team in possession; in the box it is a penalty."""
        defending_id = self._opponent(team_id)
        fouler = self._near_ball(defending_id, locations, 3)
        reason = self.rng.choice(["late challenge", "holding", "trip"])
        events = [
            self._event(
                event_type="foul",
                clock_s=clock_s,
                team_id=defending_id,
                player=fouler,
                position=self._ball(),
                payload=FoulPayload(reason=reason),
            )
        ]
        card_roll = self.rng.random()
        if card_roll < 0.14:
            events.append(
                self._event(
                    event_type="card",
                    clock_s=clock_s,
                    team_id=defending_id,
                    player=fouler,
                    position=self._ball(),
                    payload=CardPayload(
                        card="red" if card_roll < 0.004 else "yellow", reason=reason
                    ),
                )
            )
        taker = self._near_ball(team_id, locations, 2)
        if self._in_attacking_box(team_id):
            home = team_id == self.home_team_id
            self.ball_x = PITCH_LENGTH - PENALTY_SPOT if home else PENALTY_SPOT
            self.ball_y = PITCH_WIDTH / 2
            events.append(self._restart(clock_s, team_id, "penalty", "shot", taker))
            events.extend(self._shot(clock_s, team_id, taker, locations, penalty=True))
            return events
        intent = (
            "shot" if self._goal_distance(team_id) < 30 and self.rng.random() < 0.35 else "pass"
        )
        events.append(self._restart(clock_s, team_id, "free_kick", intent, taker))
        if intent == "shot":
            events.extend(self._shot(clock_s, team_id, taker, locations))
        return events

    def _action_events(
        self,
        clock_s: int,
        locations: dict[str, tuple[float, float, float]],
    ) -> list[MatchEvent]:
        team_id = self.possession_team_id
        opponent_id = self._opponent(team_id)
        actor = self._near_ball(team_id, locations, 3)
        distance = self._goal_distance(team_id)
        shot_chance = 0.0 if distance > SHOT_RANGE else 0.42 * (1 - distance / SHOT_RANGE) ** 1.6
        if self.rng.random() < shot_chance:
            return self._shot(clock_s, team_id, actor, locations)

        # Defenders rarely risk a foul inside their own box: that is a penalty.
        foul_weight = 0.25 if self._in_attacking_box(team_id) else 4
        action = self.rng.choices(
            ["pass", "duel", "pressure", "foul"], weights=[78, 10, 8, foul_weight]
        )[0]
        if action == "pass":
            return self._pass(clock_s, team_id, actor, locations)
        if action == "foul":
            return self._foul(clock_s, team_id, locations)
        opponent = self._near_ball(opponent_id, locations, 3)
        if action == "pressure":
            return [
                self._event(
                    event_type="pressure",
                    clock_s=clock_s,
                    team_id=opponent_id,
                    player=opponent,
                    position=self._ball(),
                    payload=PressurePayload(
                        target_id=actor.id, duration_s=round(self.rng.uniform(1, 8), 1)
                    ),
                )
            ]
        won = self.rng.random() < 0.55
        events = [
            self._event(
                event_type="duel",
                clock_s=clock_s,
                team_id=team_id,
                player=actor,
                position=self._ball(),
                payload=DuelPayload(opponent_id=opponent.id, kind="1v1", won=won),
            )
        ]
        if won:
            # Beating a man carries the ball forward a few metres.
            self.ball_x = _clamp(
                self.ball_x + self._direction(team_id) * self.rng.uniform(0, 6), 0, PITCH_LENGTH
            )
        else:
            events.append(self._turnover(clock_s, actor, team_id, "tackle"))
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
                self.possession_team_id = self.away_team_id
                self.ball_x, self.ball_y = PITCH_LENGTH / 2, PITCH_WIDTH / 2
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


def _post_event(url: str, event: MatchEvent) -> None:
    body = json.dumps(event.model_dump(mode="json", exclude_none=True)).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=10):
            pass
    except (HTTPError, URLError) as error:
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
        help="optional HTTP(S) /ingest URL; event envelopes are POSTed as JSON",
    )
    args = parser.parse_args(argv)

    ingest_url = _validate_ingest_url(args.ingest_url) if args.ingest_url else None
    output, should_close = _open_output(args.output)
    previous_snapshot_s: int | None = None
    try:
        for record in simulate_match(args.seed, args.duration_s):
            output.write(serialize_record(record))
            output.write("\n")
            if isinstance(record, MatchEvent) and ingest_url:
                _post_event(ingest_url, record)
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
