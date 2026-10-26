"""Deterministic event reduction and idempotent Cosmos DB persistence."""

from collections.abc import Callable

from azure.core import MatchConditions
from azure.cosmos import ContainerProxy
from azure.cosmos.exceptions import CosmosHttpResponseError
from pydantic import BaseModel, ConfigDict, Field

from .schemas import (
    CardPayload,
    DuelPayload,
    FoulPayload,
    GoalkeeperActionPayload,
    MatchEvent,
    PassPayload,
    PossessionChangePayload,
    PressurePayload,
    SetPiecePayload,
    ShotPayload,
    SubstitutionPayload,
)

MAX_COSMOS_WRITE_ATTEMPTS = 5


class EntityAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goals: int = 0
    shots: int = 0
    shots_on_target: int = 0
    passes_attempted: int = 0
    passes_completed: int = 0
    current_pass_streak: int = 0
    current_pass_streak_event_ids: list[str] = Field(default_factory=list)
    longest_pass_streak: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    possession_changes: int = 0
    duels: int = 0
    duels_won: int = 0
    pressures: int = 0
    fouls: int = 0
    set_pieces: int = 0
    goalkeeper_actions: int = 0
    substitutions: int = 0
    penalties: int = 0
    recent_shot_event_ids: list[str] = Field(default_factory=list)


class SignalGateState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    last_emitted_clock_s: int | None = None
    armed_milestones: list[int] = Field(default_factory=list)


class MatchState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    match_id: str
    last_seq: int = 0
    last_event_id: str | None = None
    period: int = 1
    match_clock_s: int = 0
    event_count: int = 0
    sequence_gaps: int = 0
    possession_team_id: str | None = None
    team_pass_streak_players: dict[str, list[str]] = Field(default_factory=dict)
    score: dict[str, int] = Field(default_factory=dict)
    team_stats: dict[str, EntityAggregate] = Field(default_factory=dict)
    player_stats: dict[str, EntityAggregate] = Field(default_factory=dict)
    signal_gate_state: dict[str, SignalGateState] = Field(default_factory=dict)
    updated_at: str


def apply_event(state: MatchState | None, event: MatchEvent) -> tuple[MatchState, bool]:
    """Apply one event in memory; return False for duplicate or stale sequences."""
    if state is None:
        state = MatchState(
            id=event.match_id,
            match_id=event.match_id,
            updated_at=event.wall_ts.isoformat(),
        )
    elif state.match_id != event.match_id:
        raise ValueError("event match_id does not match the stored match state")

    if event.seq <= state.last_seq:
        return state, False
    if state.last_seq and event.seq > state.last_seq + 1:
        state.sequence_gaps += event.seq - state.last_seq - 1

    state.period = event.period
    state.match_clock_s = max(state.match_clock_s, event.match_clock_s)
    state.last_seq = event.seq
    state.last_event_id = event.event_id
    state.event_count += 1
    state.updated_at = event.wall_ts.isoformat()

    team_stats = _get_aggregate(state.team_stats, event.team_id)
    player_stats = _get_aggregate(state.player_stats, event.player_id)
    payload = event.payload

    if isinstance(payload, PassPayload):
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.passes_attempted += 1
        if payload.outcome == "complete":
            if event.team_id is not None:
                _set_possession(state, event.team_id)
            for aggregate in (team_stats, player_stats):
                if aggregate is not None:
                    aggregate.passes_completed += 1
                    aggregate.current_pass_streak += 1
                    aggregate.current_pass_streak_event_ids.append(event.event_id)
                    aggregate.longest_pass_streak = max(
                        aggregate.longest_pass_streak,
                        aggregate.current_pass_streak,
                    )
            if event.team_id is not None and event.player_id is not None:
                players = state.team_pass_streak_players.setdefault(event.team_id, [])
                if event.player_id not in players:
                    players.append(event.player_id)
        else:
            if event.team_id is not None:
                _reset_team_pass_streak(state, event.team_id)
                if state.possession_team_id == event.team_id:
                    state.possession_team_id = None
            _reset_entity_pass_streak(player_stats)
    elif isinstance(payload, ShotPayload):
        if state.possession_team_id is not None:
            _reset_team_pass_streak(state, state.possession_team_id)
        if event.team_id is not None:
            _reset_team_pass_streak(state, event.team_id)
        _reset_entity_pass_streak(player_stats)
        state.possession_team_id = None
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.shots += 1
                aggregate.recent_shot_event_ids.append(event.event_id)
                aggregate.recent_shot_event_ids = aggregate.recent_shot_event_ids[-20:]
                if payload.outcome in {"goal", "saved"}:
                    aggregate.shots_on_target += 1
                if payload.outcome == "goal":
                    aggregate.goals += 1
        if event.team_id and payload.outcome == "goal":
            state.score[event.team_id] = state.score.get(event.team_id, 0) + 1
    elif isinstance(payload, CardPayload):
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                if payload.card == "yellow":
                    aggregate.yellow_cards += 1
                else:
                    aggregate.red_cards += 1
    elif isinstance(payload, PossessionChangePayload):
        _reset_team_pass_streak(state, payload.from_team)
        _reset_team_pass_streak(state, payload.to_team)
        if state.possession_team_id is not None:
            _reset_team_pass_streak(state, state.possession_team_id)
        state.possession_team_id = payload.to_team
        if team_stats is not None:
            team_stats.possession_changes += 1
    elif isinstance(payload, DuelPayload):
        if payload.won and event.team_id is not None:
            _set_possession(state, event.team_id)
        elif not payload.won and event.team_id is not None:
            _reset_team_pass_streak(state, event.team_id)
            if state.possession_team_id == event.team_id:
                state.possession_team_id = None
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.duels += 1
                aggregate.duels_won += int(payload.won)
    elif isinstance(payload, PressurePayload):
        if team_stats is not None:
            team_stats.pressures += 1
        target_stats = _get_aggregate(state.player_stats, payload.target_id)
        if target_stats is not None:
            target_stats.pressures += 1
    elif isinstance(payload, FoulPayload):
        if event.team_id is not None:
            _reset_team_pass_streak(state, event.team_id)
        if state.possession_team_id is not None:
            _reset_team_pass_streak(state, state.possession_team_id)
        state.possession_team_id = None
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.fouls += 1
    elif isinstance(payload, SetPiecePayload):
        if event.team_id is not None:
            _set_possession(state, event.team_id)
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.set_pieces += 1
                if payload.kind == "penalty":
                    aggregate.penalties += 1
    elif isinstance(payload, GoalkeeperActionPayload):
        if event.team_id is not None:
            _set_possession(state, event.team_id)
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.goalkeeper_actions += 1
    elif isinstance(payload, SubstitutionPayload) and team_stats is not None:
        team_stats.substitutions += 1
        for player_id in (payload.in_id, payload.out_id):
            _get_aggregate(state.player_stats, player_id)

    return state, True


def _reset_entity_pass_streak(aggregate: EntityAggregate | None) -> None:
    if aggregate is not None:
        aggregate.current_pass_streak = 0
        aggregate.current_pass_streak_event_ids.clear()


def _reset_team_pass_streak(state: MatchState, team_id: str) -> None:
    _reset_entity_pass_streak(state.team_stats.get(team_id))
    for player_id in state.team_pass_streak_players.pop(team_id, []):
        _reset_entity_pass_streak(state.player_stats.get(player_id))


def _set_possession(state: MatchState, team_id: str) -> None:
    if state.possession_team_id != team_id:
        if state.possession_team_id is not None:
            _reset_team_pass_streak(state, state.possession_team_id)
        _reset_team_pass_streak(state, team_id)
    state.possession_team_id = team_id


def _get_aggregate(
    aggregates: dict[str, EntityAggregate],
    entity_id: str | None,
) -> EntityAggregate | None:
    if entity_id is None:
        return None
    if entity_id not in aggregates:
        aggregates[entity_id] = EntityAggregate()
    return aggregates[entity_id]


def update_match_state(
    container: ContainerProxy,
    event: MatchEvent,
    before_persist: Callable[[MatchState, MatchEvent], None] | None = None,
) -> bool:
    """Persist a match update with ETag concurrency control and sequence dedupe."""
    for _ in range(MAX_COSMOS_WRITE_ATTEMPTS):
        try:
            document = container.read_item(item=event.match_id, partition_key=event.match_id)
        except CosmosHttpResponseError as error:
            if error.status_code != 404:
                raise
            document = None

        if document is None:
            state = None
            etag = None
        else:
            etag = document.get("_etag")
            state_values = {
                key: value for key, value in document.items() if not key.startswith("_")
            }
            state = MatchState.model_validate(state_values)

        updated_state, applied = apply_event(state, event)
        if not applied:
            return False
        if before_persist is not None:
            before_persist(updated_state, event)
        body = updated_state.model_dump(mode="json")

        try:
            if document is None:
                container.create_item(body=body)
            else:
                container.replace_item(
                    item=event.match_id,
                    body=body,
                    etag=etag,
                    match_condition=MatchConditions.IfNotModified,
                )
            return True
        except CosmosHttpResponseError as error:
            if error.status_code not in {409, 412}:
                raise

    raise RuntimeError(
        f"Could not persist match {event.match_id} after {MAX_COSMOS_WRITE_ATTEMPTS} attempts"
    )
