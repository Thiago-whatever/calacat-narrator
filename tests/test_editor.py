import asyncio
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

import pytest

from calacat_narrator.agent_runtime import (
    BODY_MAX,
    HEADLINE_MAX,
    Candidate,
    Card,
    LocalizedCaption,
    ReviewDecision,
)
from calacat_narrator.editor import Editor, EditorConfig, fallback_card, review_card
from calacat_narrator.signals import ShotEventContext, Signal


def make_candidate(
    *,
    candidate_id: str = "candidate-1",
    topic: str = "shot_volume",
    clock: int = 100,
    self_salience: float = 0.5,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        signal_id=f"signal-{candidate_id}",
        match_id="m-0007",
        headline=f"{topic.replace('_', ' ')} update",
        why_it_matters="A verified match update.",
        metrics={topic: 5},
        evidence_event_ids=[f"evt-{candidate_id}"],
        entity_ids=["t-home"],
        team_id="t-home",
        topic=topic,
        self_salience=self_salience,
        ttl_s=240,
        match_clock_s=clock,
    )


def make_goal_signal() -> Signal:
    return Signal(
        signal_id="signal-goal-1",
        match_id="m-0007",
        kind="goal",
        match_clock_s=4020,
        entity={"team_id": "t-home"},
        value=2,
        evidence_event_ids=["evt-goal-1"],
        event_context=ShotEventContext(
            event_id="evt-goal-1",
            period=2,
            player_id="p-nbr-09",
            outcome="goal",
            speed_kmh=104,
            body_part="foot",
        ),
        score={"t-home": 2},
        tier=1,
    )


def test_editor_ranks_by_configured_weights_recency_and_focus() -> None:
    config = EditorConfig.load()
    editor = Editor(config, focus="t-home")
    fresh = make_candidate(candidate_id="fresh", clock=100)
    stale = make_candidate(candidate_id="stale", clock=0)

    editor.submit(fresh, now=datetime(2026, 10, 25, tzinfo=UTC))
    editor.submit(stale, now=datetime(2026, 10, 25, tzinfo=UTC))

    assert editor.score(fresh) > editor.score(stale)
    assert editor.score(fresh) > Editor(config, focus="unrelated").score(fresh)
    assert editor.score(make_candidate(self_salience=0.1)) == editor.score(
        make_candidate(self_salience=1)
    )


def test_critical_card_preempts_rate_limit_and_has_stable_provenance() -> None:
    config = EditorConfig.load()
    editor = Editor(config)
    now = datetime(2026, 10, 25, tzinfo=UTC)

    first = editor.submit(make_candidate(), now=now)
    assert first.accepted
    normal_card = editor.peek_due(now=now)
    assert normal_card is not None
    editor.mark_published(normal_card.candidate_id, now=now)

    critical = editor.submit(make_candidate(candidate_id="goal", topic="goal"), now=now)
    assert critical.immediate_card is not None
    assert critical.immediate_card.salience == 1
    assert critical.immediate_card.topic == "goal"
    assert critical.immediate_card.evidence_event_ids == ["evt-goal"]
    assert editor.peek_due(now=now + timedelta(seconds=1)) is None


def test_editor_enforces_topic_deduplication_and_normal_rate_limit() -> None:
    config = EditorConfig.load()
    editor = Editor(config)
    now = datetime(2026, 10, 25, tzinfo=UTC)
    editor.submit(make_candidate(), now=now)

    first_card = editor.peek_due(now=now)
    assert first_card is not None
    editor.mark_published(first_card.candidate_id, now=now)
    duplicate_topic = editor.submit(
        make_candidate(candidate_id="duplicate", clock=200),
        now=now + timedelta(seconds=1),
    )
    assert not duplicate_topic.accepted
    assert editor.peek_due(now=now + timedelta(seconds=24)) is None

    queued = editor.submit(
        make_candidate(candidate_id="next", topic="pass_streak", clock=200),
        now=now + timedelta(seconds=1),
    )
    assert queued.accepted
    next_card = editor.peek_due(now=now + timedelta(seconds=25))
    assert next_card is not None
    assert next_card.topic == "pass_streak"


def test_editor_caps_queue_and_expires_candidates() -> None:
    config = EditorConfig.load()
    editor = Editor(config)
    now = datetime(2026, 10, 25, tzinfo=UTC)
    first = editor.submit(make_candidate(candidate_id="first"), now=now)
    assert first.accepted
    first_card = editor.peek_due(now=now)
    assert first_card is not None
    editor.mark_published(first_card.candidate_id, now=now)

    for index in range(config.queue_capacity):
        result = editor.submit(
            make_candidate(
                candidate_id=f"queued-{index}",
                topic=f"topic-{index}",
            ),
            now=now + timedelta(seconds=1),
        )
        assert result.accepted
    overflow = editor.submit(
        make_candidate(candidate_id="overflow", topic="unknown", self_salience=0.01),
        now=now + timedelta(seconds=2),
    )
    assert not overflow.accepted
    assert len(editor.expire_queue(now=now + timedelta(seconds=241))) == config.queue_capacity


def test_deadletter_fallback_is_deterministic_and_preserves_verified_evidence() -> None:
    signal = make_goal_signal()
    now = datetime(2026, 10, 25, tzinfo=UTC)

    card = fallback_card(signal, EditorConfig.load(), now=now)
    repeated = fallback_card(signal, EditorConfig.load(), now=now)

    assert card == repeated
    assert card.source == "fallback"
    assert card.card_id == str(uuid5(NAMESPACE_URL, f"calacat:card:{card.candidate_id}"))
    assert card.signal_id == signal.signal_id
    assert card.evidence_event_ids == signal.evidence_event_ids
    assert card.metrics == {"goal": 2, "shot_speed_kmh": 104}
    assert card.match_clock_s == signal.match_clock_s
    assert card.expires_at == now + timedelta(seconds=card.ttl_s)


@pytest.mark.parametrize(
    "kind", ["goal", "penalty", "red_card", "shot_volume", "pass_streak", "corners"]
)
@pytest.mark.parametrize("entity", [{"team_id": "t-home"}, {"team_id": "t-away"}])
def test_fallback_cards_fit_caption_limits_in_broadcast_voice(kind: str, entity: dict) -> None:
    signal = Signal(
        signal_id=f"signal-{kind}",
        match_id="m-0007",
        kind=kind,
        match_clock_s=5399,
        entity=entity,
        value=12,
        evidence_event_ids=["evt-1"],
        score={"t-home": 10, "t-away": 10},
        tier=1,
    )

    card = fallback_card(signal, EditorConfig.load(), now=datetime(2026, 10, 25, tzinfo=UTC))

    assert len(card.headline) <= HEADLINE_MAX
    assert len(card.body) <= BODY_MAX
    assert card.body.startswith("90' ")
    assert (
        "Northbridge Comets" if entity["team_id"] == "t-home" else "Southmere Foxes"
    ) in card.body
    assert card.team_id == entity["team_id"]


def test_goal_fallback_names_the_scorer_and_the_new_score() -> None:
    card = fallback_card(
        make_goal_signal(), EditorConfig.load(), now=datetime(2026, 10, 25, tzinfo=UTC)
    )

    assert card.headline == "Bram Elsen scores for Northbridge Comets"
    assert card.body == (
        "68' Bram Elsen scored for Northbridge Comets with a 104 km/h strike. "
        "It's Northbridge Comets 2, Southmere Foxes 0."
    )
    assert card.player_id == "p-nbr-09"


# ---- Reviewer (ADR-039, ADR-040)


class FakeReviewer:
    def __init__(self, result=None, *, delay: float = 0, error: Exception | None = None) -> None:
        self.result, self.delay, self.error = result, delay, error
        self.facts: dict[str, str] = {}

    async def review(self, card, facts):
        self.facts = facts
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


def specialist_goal_card() -> Card:
    candidate = Candidate(
        candidate_id="cand-goal",
        signal_id="signal-goal-1",
        match_id="m-0007",
        headline="Elsen doubles the lead",
        why_it_matters="68' Bram Elsen scores again for Northbridge Comets.",
        metrics={"goal": 2, "shot_speed_kmh": 104},
        evidence_event_ids=["evt-goal-1"],
        entity_ids=["t-home"],
        team_id="t-home",
        player_id="p-nbr-09",
        score={"t-home": 2},
        topic="goal",
        self_salience=0.9,
        match_clock_s=4020,
    )
    return Card.from_candidate(candidate, created_at=datetime(2026, 10, 25, tzinfo=UTC))


def decision(
    kind: str, *, body: str = "68' Bram Elsen scores with a 104 km/h strike. It's 2-0."
) -> ReviewDecision:
    return ReviewDecision(
        decision=kind,
        headline="Bram Elsen doubles the lead",
        body=body,
        es=LocalizedCaption(
            headline="Bram Elsen amplía la ventaja",
            body="68' Bram Elsen marca con un remate a 104 km/h. Va 2-0.",
        ),
    )


def review(
    reviewer, card: Card | None = None, timeout_s: float = 1, critical_topics: tuple[str, ...] = ()
) -> Card | None:
    return asyncio.run(
        review_card(
            card or specialist_goal_card(),
            reviewer,
            timeout_s=timeout_s,
            critical_topics=critical_topics,
        )
    )


def test_reviewer_approve_publishes_reviewed_bilingual_card() -> None:
    reviewer = FakeReviewer(decision("approve"))

    card = review(reviewer)

    assert card is not None and card.source == "specialist"
    assert card.headline == "Bram Elsen doubles the lead"
    assert card.i18n is not None and card.i18n.es.headline == "Bram Elsen amplía la ventaja"
    assert reviewer.facts["minute"] == "68'"
    assert card.evidence_event_ids == ["evt-goal-1"] and card.player_id == "p-nbr-09"


def test_reviewer_revise_replaces_the_draft_text() -> None:
    revised = decision("revise", body="68' Bram Elsen makes it 2-0 for Northbridge Comets.")

    card = review(FakeReviewer(revised))

    assert card is not None
    assert card.body == "68' Bram Elsen makes it 2-0 for Northbridge Comets."
    assert card.body != specialist_goal_card().body


def test_reviewer_reject_drops_a_non_critical_card() -> None:
    assert review(FakeReviewer(decision("reject"))) is None


def test_reviewer_reject_of_a_critical_card_publishes_the_template() -> None:
    critical = tuple(EditorConfig.load().critical_topics)

    card = review(FakeReviewer(decision("reject")), critical_topics=critical)

    assert card is not None and card.source == "fallback"
    assert card.headline == "Bram Elsen scores for Northbridge Comets"
    assert card.i18n is not None


def test_body_part_travels_from_signal_to_card_and_its_captions() -> None:
    signal = make_goal_signal()
    header = signal.model_copy(
        update={"event_context": signal.event_context.model_copy(update={"body_part": "head"})}
    )

    card = fallback_card(header, EditorConfig.load(), now=datetime(2026, 10, 25, tzinfo=UTC))

    assert card.body_part == "head"
    assert "104 km/h header" in card.body
    assert card.i18n is not None and "un cabezazo a 104 km/h" in card.i18n.es.body


def test_reviewer_sees_the_body_part_stored_on_the_card() -> None:
    reviewer = FakeReviewer(decision("reject"))
    header_card = specialist_goal_card().model_copy(update={"body_part": "head"})

    review(reviewer, header_card)

    assert reviewer.facts["detail"] == "a 104 km/h header"


@pytest.mark.parametrize(
    "reviewer",
    [
        FakeReviewer(decision("approve"), delay=0.5),
        FakeReviewer(error=RuntimeError("model unavailable")),
        FakeReviewer(error=ValueError("response did not match the schema")),
        FakeReviewer(decision("approve", body="68' Bram Elsen scores. It's 3-0.")),
        FakeReviewer("not a decision"),
    ],
    ids=["timeout", "error", "invalid-output", "wrong-number", "wrong-type"],
)
def test_reviewer_failures_publish_the_bilingual_fallback(reviewer: FakeReviewer) -> None:
    card = review(reviewer, timeout_s=0.05)

    assert card is not None and card.source == "fallback"
    assert card.headline == "Bram Elsen scores for Northbridge Comets"
    assert card.i18n is not None
    assert card.i18n.es.headline == "Bram Elsen marca para Northbridge Comets"
    assert card.i18n.es.body.startswith("68' Bram Elsen marcó para Northbridge Comets")


def test_fallback_cards_carry_spanish_without_a_reviewer() -> None:
    card = fallback_card(
        make_goal_signal(), EditorConfig.load(), now=datetime(2026, 10, 25, tzinfo=UTC)
    )

    assert card.i18n is not None
    assert card.i18n.es.body == (
        "68' Bram Elsen marcó para Northbridge Comets con un remate a 104 km/h. "
        "Marcador: Northbridge Comets 2, Southmere Foxes 0."
    )
    assert review(None, card) == card


@pytest.mark.parametrize(
    "leak", ["Según los datos, gol", "La señal confirma el gol", "Gol a los 3401 segundos"]
)
def test_spanish_text_is_validated_too(leak: str) -> None:
    with pytest.raises(ValueError):
        LocalizedCaption(headline="Gol", body=leak)
