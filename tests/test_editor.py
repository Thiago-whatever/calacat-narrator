from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from calacat_narrator.agent_runtime import Candidate
from calacat_narrator.editor import Editor, EditorConfig, fallback_card
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
        headline=f"{topic} update",
        why_it_matters="A verified match update.",
        metrics={topic: 5},
        evidence_event_ids=[f"evt-{candidate_id}"],
        entity_ids=["t-home"],
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
            outcome="goal",
            speed_kmh=104,
            body_part="foot",
        ),
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
