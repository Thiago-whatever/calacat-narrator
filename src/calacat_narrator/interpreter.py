"""Deterministic event reduction and idempotent Cosmos DB persistence."""

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
    score: dict[str, int] = Field(default_factory=dict)
    team_stats: dict[str, EntityAggregate] = Field(default_factory=dict)
    player_stats: dict[str, EntityAggregate] = Field(default_factory=dict)
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
                    aggregate.passes_completed += 1
                    aggregate.current_pass_streak += 1
                    aggregate.longest_pass_streak = max(
                        aggregate.longest_pass_streak,
                        aggregate.current_pass_streak,
                    )
                else:
                    aggregate.current_pass_streak = 0
    elif isinstance(payload, ShotPayload):
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.shots += 1
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
        state.possession_team_id = payload.to_team
        if team_stats is not None:
            team_stats.possession_changes += 1
    elif isinstance(payload, DuelPayload):
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
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.fouls += 1
    elif isinstance(payload, SetPiecePayload):
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.set_pieces += 1
    elif isinstance(payload, GoalkeeperActionPayload):
        for aggregate in (team_stats, player_stats):
            if aggregate is not None:
                aggregate.goalkeeper_actions += 1
    elif isinstance(payload, SubstitutionPayload) and team_stats is not None:
        team_stats.substitutions += 1
        for player_id in (payload.in_id, payload.out_id):
            _get_aggregate(state.player_stats, player_id)

    return state, True


def _get_aggregate(
    aggregates: dict[str, EntityAggregate],
    entity_id: str | None,
) -> EntityAggregate | None:
    if entity_id is None:
        return None
    if entity_id not in aggregates:
        aggregates[entity_id] = EntityAggregate()
    return aggregates[entity_id]


def update_match_state(container: ContainerProxy, event: MatchEvent) -> bool:
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
