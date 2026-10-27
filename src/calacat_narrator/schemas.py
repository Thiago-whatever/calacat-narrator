"""Pydantic contracts for synthetic match events and position snapshots."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

EntityId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    ),
]
TeamId = EntityId
PlayerId = EntityId
MatchId = EntityId
CoordinateX = Annotated[float, Field(ge=0, le=105)]
CoordinateY = Annotated[float, Field(ge=0, le=68)]
SpeedKmh = Annotated[float, Field(ge=0, le=250)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PassPayload(ContractModel):
    receiver_id: PlayerId
    end_x: CoordinateX
    end_y: CoordinateY
    speed_kmh: SpeedKmh
    outcome: Literal["complete", "incomplete", "out"]
    height: Literal["ground", "low", "high"]


class ShotPayload(ContractModel):
    speed_kmh: SpeedKmh
    outcome: Literal["goal", "saved", "off", "blocked"]
    goal_y: Annotated[float, Field(ge=0, le=7.32)]
    goal_z: Annotated[float, Field(ge=0, le=2.44)]
    body_part: Literal["foot", "head", "other"]


class DuelPayload(ContractModel):
    opponent_id: PlayerId
    kind: Literal["tackle", "1v1", "aerial"]
    won: bool


class PressurePayload(ContractModel):
    target_id: PlayerId
    duration_s: Annotated[float, Field(gt=0, le=120)]


class PossessionChangePayload(ContractModel):
    from_team: TeamId
    to_team: TeamId
    cause: Literal["tackle", "interception", "out", "foul"]


class FoulPayload(ContractModel):
    reason: str = Field(min_length=1, max_length=120)


class CardPayload(ContractModel):
    card: Literal["yellow", "red"]
    reason: str = Field(min_length=1, max_length=120)


class SetPiecePayload(ContractModel):
    kind: Literal["free_kick", "corner", "penalty", "throw"]
    intent: Literal["pass", "cross", "shot"]
    first_contact_x: CoordinateX
    first_contact_y: CoordinateY
    first_contact_player_id: PlayerId | None = None


class GoalkeeperActionPayload(ContractModel):
    kind: Literal["save", "claim", "punch", "sweep"]
    shot_event_id: str | None = Field(default=None, min_length=1, max_length=64)


class SubstitutionPayload(ContractModel):
    in_id: PlayerId
    out_id: PlayerId


class PeriodPayload(ContractModel):
    action: Literal["start", "end"]


EventPayload = (
    PassPayload
    | ShotPayload
    | DuelPayload
    | PressurePayload
    | PossessionChangePayload
    | FoulPayload
    | CardPayload
    | SetPiecePayload
    | GoalkeeperActionPayload
    | SubstitutionPayload
    | PeriodPayload
)

PAYLOAD_MODELS: dict[str, type[ContractModel]] = {
    "pass": PassPayload,
    "shot": ShotPayload,
    "duel": DuelPayload,
    "pressure": PressurePayload,
    "possession_change": PossessionChangePayload,
    "foul": FoulPayload,
    "card": CardPayload,
    "set_piece": SetPiecePayload,
    "gk_action": GoalkeeperActionPayload,
    "sub": SubstitutionPayload,
    "period": PeriodPayload,
}


class MatchEvent(ContractModel):
    event_id: str = Field(min_length=1, max_length=64)
    match_id: MatchId
    seq: Annotated[int, Field(ge=1)]
    type: Literal[
        "pass",
        "shot",
        "duel",
        "pressure",
        "possession_change",
        "foul",
        "card",
        "set_piece",
        "gk_action",
        "sub",
        "period",
    ]
    period: Literal[1, 2]
    match_clock_s: Annotated[int, Field(ge=0)]
    wall_ts: datetime
    team_id: TeamId | None = None
    player_id: PlayerId | None = None
    x: CoordinateX | None = None
    y: CoordinateY | None = None
    payload: EventPayload

    @model_validator(mode="before")
    @classmethod
    def parse_event_payload(cls, values: object) -> object:
        if not isinstance(values, dict):
            return values
        event_type = values.get("type")
        if not isinstance(event_type, str):
            return values
        payload_model = PAYLOAD_MODELS.get(event_type)
        if payload_model is None:
            return values
        payload = values.get("payload")
        if isinstance(payload, dict):
            values = {**values, "payload": payload_model.model_validate(payload)}
        return values

    @model_validator(mode="after")
    def ensure_payload_matches_type(self) -> "MatchEvent":
        expected_model = PAYLOAD_MODELS[self.type]
        if not isinstance(self.payload, expected_model):
            raise ValueError(f"payload must match event type '{self.type}'")  # noqa: TRY004
        if self.wall_ts.tzinfo is None or self.wall_ts.utcoffset() is None:
            raise ValueError("wall_ts must include a timezone")
        return self


class PlayerPosition(ContractModel):
    id: PlayerId
    x: CoordinateX
    y: CoordinateY
    speed_kmh: SpeedKmh


class BallPosition(ContractModel):
    x: CoordinateX
    y: CoordinateY
    z: Annotated[float, Field(ge=0, le=40)]


class PositionSnapshot(ContractModel):
    match_id: MatchId
    period: Literal[1, 2]
    match_clock_s: Annotated[int, Field(ge=0)]
    players: list[PlayerPosition] = Field(min_length=1)
    ball: BallPosition

    @model_validator(mode="after")
    def ensure_unique_players(self) -> "PositionSnapshot":
        player_ids = [player.id for player in self.players]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("players must have unique ids within a position snapshot")
        return self
