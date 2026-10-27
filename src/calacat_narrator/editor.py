"""Deterministic card ranking, queueing, and dead-letter recovery contracts."""

import asyncio
import logging
import re
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from math import exp, log
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .agent_runtime import (
    BODY_MAX,
    HEADLINE_MAX,
    Candidate,
    Card,
    Lang,
    ReviewDecision,
    card_facts,
    signal_body_part,
    signal_player_id,
    signal_team_id,
)
from .signals import ShotEventContext, Signal

logger = logging.getLogger(__name__)


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
    review_timeout_s: float = Field(gt=0, le=30)
    # Goals must reach air within ~5 s (ADR-038/039), so critical reviews give up sooner.
    critical_review_timeout_s: float = Field(gt=0, le=30)

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
        keep_ids = {
            queued.candidate.candidate_id for queued in ranked[: self.config.queue_capacity]
        }
        dropped = tuple(
            queued.candidate.candidate_id
            for queued in self._queue
            if queued.candidate.candidate_id not in keep_ids
        )
        self._queue = [
            queued for queued in self._queue if queued.candidate.candidate_id in keep_ids
        ]
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
            (item for item in self._queue if item.candidate.candidate_id == candidate_id),
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
            queued for queued in self._queue if queued.candidate.candidate_id != candidate_id
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
        focused_values = {
            candidate.topic.lower(),
            *(entity.lower() for entity in candidate.entity_ids),
        }
        return (
            self.config.focus_match_relevance
            if self._focus in focused_values
            else self.config.focus_other_relevance
        )

    def _expire_topic_deduplication(self, now: datetime) -> None:
        self._topic_expiry = {
            key: expiry for key, expiry in self._topic_expiry.items() if expiry > now
        }


def _fit(text: str, limit: int) -> str:
    """Shorten at a word boundary so templates never exceed the caption limits."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


# Headline and body formats per language and topic; fields come from event_facts (ADR-040).
_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "en": {
        "goal": ("{who} scores for {team}", "{minute} {event}{detail}.{score}"),
        "penalty": ("Penalty to {team}", "{minute} {event} against {opponent}.{score}"),
        "red_card": (
            "Red card for {team}",
            "{minute} {event}. They play on a player down.{score}",
        ),
        "shot_volume": (
            "{team} keep shooting",
            "{minute} {event}, pushing {opponent} back.{score}",
        ),
        "pass_streak": (
            "{team} keep the ball",
            "{minute} {event}, keeping {opponent} chasing.{score}",
        ),
        "": ("{team} in the {half}", "{minute} {event}.{score}"),
    },
    "es": {
        "goal": ("{who} marca para {team}", "{minute} {event}{detail}.{score}"),
        "penalty": ("Penalti para {team}", "{minute} {event} ante {opponent}.{score}"),
        "red_card": ("Roja para {team}", "{minute} {event}.{score}"),
        "shot_volume": (
            "{team} insiste",
            "{minute} {event} y empuja a {opponent} hacia atrás.{score}",
        ),
        "pass_streak": (
            "{team} tiene la pelota",
            "{minute} {event} y hace correr a {opponent}.{score}",
        ),
        "": ("{team} en el {half}", "{minute} {event}.{score}"),
    },
}
_SCORE_SENTENCE = {"en": " It's {score}.", "es": " Marcador: {score}."}
_DETAIL_PREFIX = {"en": " with ", "es": " con "}


def template_caption(kind: str, facts: dict[str, str], lang: Lang = "en") -> tuple[str, str]:
    """Broadcast-voice headline and body built only from facts (ADR-038, ADR-040)."""
    headline_format, body_format = _TEMPLATES[lang].get(kind, _TEMPLATES[lang][""])
    fields = {
        **facts,
        "who": facts.get("player", facts["team"]),
        "detail": _DETAIL_PREFIX[lang] + facts["detail"] if "detail" in facts else "",
        "score": _SCORE_SENTENCE[lang].format(score=facts["score"]) if "score" in facts else "",
    }
    return (
        _fit(headline_format.format(**fields), HEADLINE_MAX),
        _fit(body_format.format(**fields), BODY_MAX),
    )


def localized_fallback_card(card: Card) -> Card:
    """The templated card in English with its Spanish translation; never needs a model."""
    headline, body = template_caption(card.topic, card_facts(card, "en"), "en")
    es_headline, es_body = template_caption(card.topic, card_facts(card, "es"), "es")
    return Card.model_validate(
        {
            **card.model_dump(),
            "headline": headline,
            "body": body,
            "i18n": {"es": {"headline": es_headline, "body": es_body}},
            "source": "fallback",
            "review": None,
        }
    )


def fallback_card(signal: Signal, config: EditorConfig, *, now: datetime | None = None) -> Card:
    """Build a deterministic, evidence-preserving card when specialist delivery fails."""
    created_at = _aware_now(now)
    metrics: dict[str, int | float] = {signal.kind: signal.value}
    if isinstance(signal.event_context, ShotEventContext):
        metrics["shot_speed_kmh"] = signal.event_context.speed_kmh

    candidate = Candidate(
        candidate_id=str(uuid5(NAMESPACE_URL, f"calacat:fallback:{signal.signal_id}")),
        signal_id=signal.signal_id,
        match_id=signal.match_id,
        # Placeholder text; localized_fallback_card writes the EN and ES captions below.
        headline=signal.kind.replace("_", " "),
        why_it_matters=signal.kind.replace("_", " "),
        metrics=metrics,
        evidence_event_ids=signal.evidence_event_ids,
        entity_ids=list(signal.entity.values()),
        team_id=signal_team_id(signal),
        player_id=signal_player_id(signal),
        body_part=signal_body_part(signal),
        score=signal.score,
        topic=signal.kind,
        self_salience=1.0,
        ttl_s=min(config.default_ttl_s, config.max_ttl_s),
        match_clock_s=signal.match_clock_s,
    )
    return localized_fallback_card(
        Card.from_candidate(candidate, created_at=created_at, source="fallback")
    )


def fallback_candidate_card(
    candidate: Candidate,
    config: EditorConfig,
    *,
    now: datetime | None = None,
) -> Card:
    """Replace a dead-lettered narrative with a template over verified candidate fields."""
    created_at = _aware_now(now)
    fallback = candidate.model_copy(
        update={
            "candidate_id": str(
                uuid5(NAMESPACE_URL, f"calacat:fallback-candidate:{candidate.candidate_id}")
            ),
            "self_salience": 1.0,
            "ttl_s": min(config.default_ttl_s, config.max_ttl_s, candidate.ttl_s),
        }
    )
    return localized_fallback_card(
        Card.from_candidate(fallback, created_at=created_at, source="fallback")
    )


# ---- Review (ADR-039): after the budget picks a card, before it is stored and pushed.


class Reviewer(Protocol):
    async def review(self, card: Card, facts: dict[str, str]) -> ReviewDecision: ...


_NUMBER = re.compile(r"\d+")


def check_against_facts(card: Card, facts: dict[str, str]) -> None:
    """Every number must come from the facts, and each body must give the minute."""
    if card.i18n is None:
        raise ValueError("reviewed card has no Spanish text")
    allowed = set(_NUMBER.findall(" ".join(facts.values())))
    texts = (card.headline, card.body, card.i18n.es.headline, card.i18n.es.body)
    if unknown := set(_NUMBER.findall(" ".join(texts))) - allowed:
        raise ValueError(f"reviewed text has numbers not in the facts: {sorted(unknown)}")
    if facts["minute"] not in card.body or facts["minute"] not in card.i18n.es.body:
        raise ValueError("reviewed text must give the minute in both languages")


async def review_card(
    card: Card,
    reviewer: Reviewer | None,
    *,
    timeout_s: float,
    critical_topics: Collection[str] = (),
) -> Card | None:
    """Approve or revise to a reviewed bilingual card, reject to None, or fall back on failure.

    A critical card (goal, red card, penalty) is never dropped: a reject publishes the template.
    """
    if card.source == "fallback" and card.i18n is not None:
        return card
    if card.source == "fallback" or reviewer is None:
        return localized_fallback_card(card)
    facts = card_facts(card)
    try:
        decision = await asyncio.wait_for(reviewer.review(card, facts), timeout_s)
        if decision.decision == "reject":
            if card.topic in critical_topics:
                logger.warning(
                    "Reviewer rejected critical card %s; using the fallback", card.card_id
                )
                return localized_fallback_card(card)
            logger.info("Reviewer rejected card %s", card.card_id)
            return None
        reviewed = Card.model_validate(
            {
                **card.model_dump(),
                "headline": decision.headline,
                "body": decision.body,
                "i18n": {"es": decision.es.model_dump()},
                "review": "approved" if decision.decision == "approve" else "revised",
            }
        )
        check_against_facts(reviewed, facts)
        return reviewed
    except Exception:
        # Timeout, model or network error, or invalid output: publish the template instead.
        logger.warning("Review failed for card %s; using the fallback", card.card_id, exc_info=True)
        return localized_fallback_card(card)


def _aware_now(now: datetime | None) -> datetime:
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("Editor timestamps must include a timezone")
    return current
