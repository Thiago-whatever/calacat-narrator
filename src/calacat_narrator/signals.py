"""Configuration-backed signal gates for deterministic match aggregates."""

from functools import lru_cache
from importlib.resources import files
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid5

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .interpreter import EntityAggregate, MatchState, SignalGateState
from .schemas import CardPayload, EntityId, MatchEvent, MatchId, SetPiecePayload, ShotPayload

Metric = Literal[
    "current_pass_streak",
    "goals",
    "penalties",
    "passes_attempted",
    "red_cards",
    "shots",
]
SampleMetric = Literal["event_count", "passes_attempted"]


class SignalRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=64)
    entity: Literal["team", "player"]
    metric: Metric
    sample_metric: SampleMetric
    critical: bool
    event_type: Literal["shot", "card", "set_piece"] | None = None
    event_field: Literal["outcome", "card", "kind"] | None = None
    event_value: str | None = None
    min_sample: int = Field(ge=0)
    min_clock_s: int = Field(ge=0)
    milestones: list[int]
    cooldown_s: int = Field(ge=0)
    hysteresis: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_rule_shape(self) -> "SignalRule":
        if self.critical and (
            self.event_type is None or self.event_field is None or self.event_value is None
        ):
            raise ValueError("critical rules must identify an event type, field, and value")
        if not self.critical and not self.milestones:
            raise ValueError("threshold rules must define at least one milestone")
        if len(self.milestones) != len(set(self.milestones)) or any(
            milestone < 1 for milestone in self.milestones
        ):
            raise ValueError("milestones must be unique positive integers")
        if self.hysteresis >= min(self.milestones, default=1):
            raise ValueError("hysteresis must be smaller than every milestone")
        return self


class SignalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    rules: list[SignalRule] = Field(min_length=1)


class ShotEventContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    event_type: Literal["shot"] = "shot"
    event_id: str = Field(min_length=1, max_length=64)
    period: Literal[1, 2]
    outcome: Literal["goal", "saved", "off", "blocked"]
    speed_kmh: float = Field(ge=0, le=250)
    xg: float = Field(ge=0, le=1)
    body_part: Literal["foot", "head", "other"]


class PenaltyEventContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_type: Literal["set_piece"] = "set_piece"
    event_id: str = Field(min_length=1, max_length=64)
    period: Literal[1, 2]
    kind: Literal["penalty"] = "penalty"
    intent: Literal["pass", "cross", "shot"]


SignalEventContext = Annotated[
    ShotEventContext | PenaltyEventContext,
    Field(discriminator="event_type"),
]


class Signal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1, max_length=64)
    match_id: MatchId
    kind: str = Field(min_length=1, max_length=64)
    match_clock_s: int = Field(ge=0)
    entity: dict[Literal["team_id", "player_id"], EntityId] = Field(min_length=1, max_length=1)
    value: int = Field(ge=0)
    evidence_event_ids: list[str] = Field(min_length=1, max_length=100)
    event_context: SignalEventContext | None = None
    tier: Literal[1, 2]

    @model_validator(mode="after")
    def validate_event_context(self) -> "Signal":
        if self.event_context is None:
            return self
        if self.event_context.event_id not in self.evidence_event_ids:
            raise ValueError("event context ID must be included in signal evidence")
        if isinstance(self.event_context, ShotEventContext):
            if self.kind not in {"goal", "shot"}:
                raise ValueError("shot event context requires a goal or shot signal")
            if self.kind == "goal" and self.event_context.outcome != "goal":
                raise ValueError("goal signal event context must describe a goal")
        elif self.kind != "penalty":
            raise ValueError("set-piece event context requires a penalty signal")
        return self


@lru_cache(maxsize=1)
def load_signal_rules() -> tuple[SignalRule, ...]:
    rules_file = files("calacat_narrator").joinpath("data", "signals.yaml")
    config = SignalConfig.model_validate(yaml.safe_load(rules_file.read_text(encoding="utf-8")))
    return tuple(config.rules)


def evaluate_signals(
    state: MatchState,
    event: MatchEvent,
    rules: tuple[SignalRule, ...],
) -> list[Signal]:
    """Create critical signals immediately and threshold signals with durable gates."""
    signals: list[Signal] = []
    for rule in rules:
        if rule.critical:
            if _critical_event_matches(rule, event):
                entity_id = event.team_id if rule.entity == "team" else event.player_id
                aggregate = _entity_aggregate(state, rule.entity, entity_id)
                value = _metric_value(state, aggregate, rule.metric)
                if entity_id is not None:
                    signals.append(
                        _create_signal(
                            state,
                            event,
                            rule,
                            entity_id,
                            value,
                            [event.event_id],
                            critical=True,
                        )
                    )
            continue

        aggregates = state.team_stats if rule.entity == "team" else state.player_stats
        for entity_id, aggregate in aggregates.items():
            sample_size = _sample_size(state, aggregate, rule.sample_metric)
            if sample_size < rule.min_sample or state.match_clock_s < rule.min_clock_s:
                continue

            value = _metric_value(state, aggregate, rule.metric)
            gate_key = f"{rule.kind}:{rule.entity}:{entity_id}"
            gate = state.signal_gate_state.setdefault(
                gate_key,
                SignalGateState(armed_milestones=list(rule.milestones)),
            )
            armed = set(gate.armed_milestones)
            for milestone in rule.milestones:
                if value <= milestone - rule.hysteresis:
                    armed.add(milestone)
                elif value >= milestone and milestone in armed:
                    cooldown_complete = (
                        gate.last_emitted_clock_s is None
                        or state.match_clock_s - gate.last_emitted_clock_s >= rule.cooldown_s
                    )
                    if not cooldown_complete:
                        continue
                    evidence = _evidence_ids(aggregate, rule.metric, milestone, event.event_id)
                    signals.append(
                        _create_signal(
                            state,
                            event,
                            rule,
                            entity_id,
                            value,
                            evidence,
                            critical=False,
                            milestone=milestone,
                        )
                    )
                    armed.remove(milestone)
                    gate.last_emitted_clock_s = state.match_clock_s
            gate.armed_milestones = sorted(armed)
    return signals


def _critical_event_matches(rule: SignalRule, event: MatchEvent) -> bool:
    if event.type != rule.event_type:
        return False
    payload = event.payload
    if rule.event_field == "outcome" and isinstance(payload, ShotPayload):
        return payload.outcome == rule.event_value
    if rule.event_field == "card" and isinstance(payload, CardPayload):
        return payload.card == rule.event_value
    if rule.event_field == "kind" and isinstance(payload, SetPiecePayload):
        return payload.kind == rule.event_value
    return False


def _entity_aggregate(
    state: MatchState,
    entity_type: Literal["team", "player"],
    entity_id: str | None,
) -> EntityAggregate | None:
    if entity_id is None:
        return None
    aggregates = state.team_stats if entity_type == "team" else state.player_stats
    return aggregates.get(entity_id)


def _metric_value(state: MatchState, aggregate: EntityAggregate | None, metric: Metric) -> int:
    if metric == "event_count":
        return state.event_count
    if aggregate is None:
        return 0
    return int(getattr(aggregate, metric))


def _sample_size(state: MatchState, aggregate: EntityAggregate, metric: SampleMetric) -> int:
    return state.event_count if metric == "event_count" else aggregate.passes_attempted


def _evidence_ids(
    aggregate: EntityAggregate,
    metric: Metric,
    milestone: int,
    event_id: str,
) -> list[str]:
    if metric == "current_pass_streak":
        return aggregate.current_pass_event_ids[-milestone:]
    if metric == "shots":
        return aggregate.recent_shot_event_ids[-milestone:]
    return [event_id]


def _create_signal(
    state: MatchState,
    event: MatchEvent,
    rule: SignalRule,
    entity_id: str,
    value: int,
    evidence_event_ids: list[str],
    *,
    critical: bool,
    milestone: int | None = None,
) -> Signal:
    entity_key: Literal["team_id", "player_id"] = (
        "team_id" if rule.entity == "team" else "player_id"
    )
    unique_key = f"{state.match_id}:{rule.kind}:{event.event_id}:{entity_id}:{milestone or ''}"
    event_context: SignalEventContext | None = None
    if rule.kind == "goal" and isinstance(event.payload, ShotPayload):
        event_context = ShotEventContext(
            event_id=event.event_id,
            period=event.period,
            outcome=event.payload.outcome,
            speed_kmh=event.payload.speed_kmh,
            xg=event.payload.xg,
            body_part=event.payload.body_part,
        )
    elif rule.kind == "penalty" and isinstance(event.payload, SetPiecePayload):
        event_context = PenaltyEventContext(
            event_id=event.event_id,
            period=event.period,
            kind=event.payload.kind,
            intent=event.payload.intent,
        )
    return Signal(
        signal_id=str(uuid5(NAMESPACE_URL, unique_key)),
        match_id=state.match_id,
        kind=rule.kind,
        match_clock_s=state.match_clock_s,
        entity={entity_key: entity_id},
        value=value,
        evidence_event_ids=evidence_event_ids,
        event_context=event_context,
        tier=1 if critical else 2,
    )
