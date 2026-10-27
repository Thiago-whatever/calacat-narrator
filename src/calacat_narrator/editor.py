"""Deterministic card ranking, queueing, and dead-letter recovery contracts."""

from datetime import UTC, datetime, timedelta
from importlib.resources import files
from math import exp, log
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .agent_runtime import Candidate, Card
from .signals import PassEventContext, PenaltyEventContext, ShotEventContext, Signal


class EditorConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1]
    publish_interval_s: int = Field(ge=20, le=30)
    queue_capacity: int = Field(ge=6, le=8)
    default_ttl_s: int = Field(ge=120, le=180)
    max_ttl_s: int = Field(ge=120, le=300)
    recency_half_life_s: int = Field(ge=1)
    critical_topics: list[str] = Field(min_length=1)
    topic_weights: dict[str, float]
    topic_rarity: dict[str, float]
    focus_match_relevance: float = Field(ge=0, le=1)
    focus_other_relevance: float = Field(ge=0, le=1)

    @field_validator("topic_weights", "topic_rarity")
    @classmethod
    def validate_unit_factors(cls, factors: dict[str, float]) -> dict[str, float]:
        if any(not 0 <= value <= 1 for value in factors.values()):
            raise ValueError("topic weights and rarity factors must be between 0 and 1")
        return factors

    @model_validator(mode="after")
    def validate_ttl_bounds(self) -> "EditorConfig":
        if self.max_ttl_s < self.default_ttl_s:
            raise ValueError("max_ttl_s must be at least default_ttl_s")
        return self

    @classmethod
    def load(cls) -> "EditorConfig":
        config_file = files("calacat_narrator").joinpath("data", "editor.yaml")
        return cls.model_validate(yaml.safe_load(config_file.read_text(encoding="utf-8")))


class Submission(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    immediate_card: Card | None = None
    dropped_candidate_ids: tuple[str, ...] = ()


class _QueuedCandidate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    candidate: Candidate
    source: Literal["specialist", "fallback"]
    queued_at: datetime


class Editor:
    """Keeps a bounded, ranked queue and applies one shared broadcast budget."""

    def __init__(self, config: EditorConfig, *, focus: str | None = None) -> None:
        self.config = config
        self._focus = focus.strip().lower() if focus and focus.strip() else None
        self._queue: list[_QueuedCandidate] = []
        self._latest_match_clock: dict[str, int] = {}
        self._topic_expiry: dict[tuple[str, str], datetime] = {}
        self._next_publish_at: datetime | None = None

    def submit(
        self,
        candidate: Candidate,
        *,
        now: datetime | None = None,
        source: Literal["specialist", "fallback"] = "specialist",
    ) -> Submission:
        submitted_at = _aware_now(now)
        self.expire_queue(now=submitted_at)
        self._latest_match_clock[candidate.match_id] = max(
            candidate.match_clock_s,
            self._latest_match_clock.get(candidate.match_id, 0),
        )
        self._expire_topic_deduplication(submitted_at)

        if self._is_critical(candidate.topic):
            return Submission(
                accepted=True,
                immediate_card=self._make_card(candidate, 1.0, submitted_at, source),
            )

        topic_key = (candidate.match_id, candidate.topic)
        if topic_key in self._topic_expiry or any(
            queued.candidate.candidate_id == candidate.candidate_id
            or (
                queued.candidate.match_id == candidate.match_id
                and queued.candidate.topic == candidate.topic
            )
            for queued in self._queue
        ):
            return Submission(accepted=False)

        queued_candidate = _QueuedCandidate(
            candidate=candidate,
            source=source,
            queued_at=submitted_at,
        )
        if len(self._queue) < self.config.queue_capacity:
            self._queue.append(queued_candidate)
            return Submission(accepted=True)

        ranked = sorted(
            [*self._queue, queued_candidate],
            key=lambda queued: (
                -self.score(queued.candidate),
                queued.queued_at,
                queued.candidate.candidate_id,
            ),
        )
        keep_ids = {queued.candidate.candidate_id for queued in ranked[: self.config.queue_capacity]}
        dropped = tuple(
            queued.candidate.candidate_id
            for queued in self._queue
            if queued.candidate.candidate_id not in keep_ids
        )
        self._queue = [queued for queued in self._queue if queued.candidate.candidate_id in keep_ids]
        if candidate.candidate_id not in keep_ids:
            return Submission(accepted=False)
        self._queue.append(queued_candidate)
        return Submission(accepted=True, dropped_candidate_ids=dropped)

    def score(self, candidate: Candidate) -> float:
        weight = self.config.topic_weights.get(candidate.topic, 0.5)
        rarity = self.config.topic_rarity.get(candidate.topic, 0.5)
        clock_age = max(
            0,
            self._latest_match_clock.get(candidate.match_id, candidate.match_clock_s)
            - candidate.match_clock_s,
        )
        recency = exp(-log(2) * clock_age / self.config.recency_half_life_s)
        relevance = self._focus_relevance(candidate)
        return max(0.0, min(1.0, weight * rarity * recency * relevance))

    def expire_queue(self, *, now: datetime | None = None) -> tuple[str, ...]:
        current = _aware_now(now)
        expired = tuple(
            queued.candidate.candidate_id
            for queued in self._queue
            if current >= queued.queued_at + timedelta(seconds=queued.candidate.ttl_s)
        )
        expired_ids = set(expired)
        self._queue = [
            queued for queued in self._queue if queued.candidate.candidate_id not in expired_ids
        ]
        return expired

    def peek_due(self, *, now: datetime | None = None) -> Card | None:
        current = _aware_now(now)
        self.expire_queue(now=current)
        if not self._queue or (
            self._next_publish_at is not None and current < self._next_publish_at
        ):
            return None
        best = min(
            self._queue,
            key=lambda queued: (
                -self.score(queued.candidate),
                queued.queued_at,
                queued.candidate.candidate_id,
            ),
        )
        return self._make_card(
            best.candidate,
            self.score(best.candidate),
            current,
            best.source,
        )

    def mark_published(self, candidate_id: str, *, now: datetime | None = None) -> None:
        published_at = _aware_now(now)
        queued = next(
            (
                item
                for item in self._queue
                if item.candidate.candidate_id == candidate_id
            ),
            None,
        )
        if queued is not None:
            self._queue.remove(queued)
            self._topic_expiry[(queued.candidate.match_id, queued.candidate.topic)] = (
                published_at + timedelta(seconds=queued.candidate.ttl_s)
            )
        self._next_publish_at = published_at + timedelta(seconds=self.config.publish_interval_s)

    def remove(self, candidate_id: str) -> None:
        self._queue = [
            queued
            for queued in self._queue
            if queued.candidate.candidate_id != candidate_id
        ]

    def _make_card(
        self,
        candidate: Candidate,
        salience: float,
        created_at: datetime,
        source: Literal["specialist", "fallback"],
    ) -> Card:
        bounded_candidate = candidate.model_copy(
            update={
                "self_salience": salience,
                "ttl_s": min(
                    candidate.ttl_s,
                    self.config.default_ttl_s,
                    self.config.max_ttl_s,
                ),
            }
        )
        return Card.from_candidate(bounded_candidate, created_at=created_at, source=source)

    def _is_critical(self, topic: str) -> bool:
        return topic in self.config.critical_topics

    def _focus_relevance(self, candidate: Candidate) -> float:
        if self._focus is None:
            return 1.0
        focused_values = {candidate.topic.lower(), *(entity.lower() for entity in candidate.entity_ids)}
        return (
            self.config.focus_match_relevance
            if self._focus in focused_values
            else self.config.focus_other_relevance
        )

    def _expire_topic_deduplication(self, now: datetime) -> None:
        self._topic_expiry = {
            key: expiry for key, expiry in self._topic_expiry.items() if expiry > now
        }


def fallback_card(signal: Signal, config: EditorConfig, *, now: datetime | None = None) -> Card:
    """Build a deterministic, evidence-preserving card when specialist delivery fails."""
    created_at = _aware_now(now)
    clock = f"{signal.match_clock_s // 60}:{signal.match_clock_s % 60:02d}"
    metrics: dict[str, int | float] = {signal.kind: signal.value}
    if isinstance(signal.event_context, ShotEventContext):
        metrics["shot_speed_kmh"] = signal.event_context.speed_kmh
        headline = "Goal - confirmed event" if signal.kind == "goal" else "Shot update"
        body = (
            f"A goal was recorded at {clock}; verified shot speed is "
            f"{signal.event_context.speed_kmh:g} km/h."
            if signal.kind == "goal"
            else f"A shot update was recorded at {clock}; verified shot speed is "
            f"{signal.event_context.speed_kmh:g} km/h."
        )
    elif isinstance(signal.event_context, PenaltyEventContext):
        headline = "Penalty - award recorded"
        body = f"A penalty was awarded at {clock}; the recorded intent was {signal.event_context.intent}."
    elif signal.kind == "red_card":
        headline = "Red card - event recorded"
        body = f"A red card was recorded at {clock}; this is the team's red card number {signal.value}."
    elif isinstance(signal.event_context, PassEventContext):
        headline = f"{signal.kind.replace('_', ' ').title()} - verified update"
        body = f"A {signal.kind.replace('_', ' ')} update was recorded at {clock}."
    else:
        headline = f"{signal.kind.replace('_', ' ').title()} - verified update"
        body = (
            f"A {signal.kind.replace('_', ' ')} update was recorded at {clock}; "
            f"the verified signal value is {signal.value}."
        )

    candidate = Candidate(
        candidate_id=str(uuid5(NAMESPACE_URL, f"calacat:fallback:{signal.signal_id}")),
        signal_id=signal.signal_id,
        match_id=signal.match_id,
        headline=headline,
        why_it_matters=body,
        metrics=metrics,
        evidence_event_ids=signal.evidence_event_ids,
        entity_ids=list(signal.entity.values()),
        topic=signal.kind,
        self_salience=1.0,
        ttl_s=min(config.default_ttl_s, config.max_ttl_s),
        match_clock_s=signal.match_clock_s,
    )
    return Card.from_candidate(candidate, created_at=created_at, source="fallback")


def fallback_candidate_card(
    candidate: Candidate,
    config: EditorConfig,
    *,
    now: datetime | None = None,
) -> Card:
    """Replace a dead-lettered narrative with a template over verified candidate fields."""
    created_at = _aware_now(now)
    clock = f"{candidate.match_clock_s // 60}:{candidate.match_clock_s % 60:02d}"
    headline = f"{candidate.topic.replace('_', ' ').title()} - verified update"
    metric_name, metric_value = next(iter(sorted(candidate.metrics.items())))
    body = (
        f"A {candidate.topic.replace('_', ' ')} update was recorded at {clock}; "
        f"verified {metric_name} is {metric_value:g}."
    )
    fallback = Candidate(
        candidate_id=str(uuid5(NAMESPACE_URL, f"calacat:fallback-candidate:{candidate.candidate_id}")),
        signal_id=candidate.signal_id,
        match_id=candidate.match_id,
        headline=headline,
        why_it_matters=body,
        metrics=candidate.metrics,
        evidence_event_ids=candidate.evidence_event_ids,
        entity_ids=candidate.entity_ids,
        topic=candidate.topic,
        self_salience=1.0,
        ttl_s=min(config.default_ttl_s, config.max_ttl_s, candidate.ttl_s),
        match_clock_s=candidate.match_clock_s,
    )
    return Card.from_candidate(fallback, created_at=created_at, source="fallback")


def _aware_now(now: datetime | None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Editor timestamps must include a timezone")
    return current
