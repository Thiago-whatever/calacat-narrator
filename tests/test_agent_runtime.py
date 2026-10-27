import asyncio
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from calacat_narrator.agent_runtime import (
    BODY_MAX,
    HEADLINE_MAX,
    Candidate,
    CandidateDraft,
    Card,
    FoundryCandidateGenerator,
    _catalog,
    broadcast_minute,
    event_facts,
    signal_facts,
    signal_team_id,
    validate_caption,
)
from calacat_narrator.editor import template_caption
from calacat_narrator.signals import PassEventContext, ShotEventContext, Signal


def make_signal() -> Signal:
    return Signal(
        signal_id="82808bb1-7817-51a4-8a04-cdff8dc5d04e",
        match_id="m-0007",
        kind="goal",
        match_clock_s=3401,
        entity={"team_id": "t-home"},
        value=2,
        evidence_event_ids=["evt-0042"],
        event_context=ShotEventContext(
            event_id="evt-0042",
            period=2,
            player_id="p-nbr-09",
            outcome="goal",
            speed_kmh=94.5,
            body_part="foot",
        ),
        score={"t-home": 2, "t-away": 1},
        tier=1,
    )


def make_pass_streak_signal() -> Signal:
    return Signal(
        signal_id="c65a7e31-2f2c-575a-a943-e41ab8529bc1",
        match_id="m-0007",
        kind="pass_streak",
        match_clock_s=1200,
        entity={"team_id": "t-away"},
        value=8,
        evidence_event_ids=[f"evt-pass-{index}" for index in range(1, 8)] + ["evt-0008"],
        event_context=PassEventContext(event_id="evt-0008", period=1, outcome="complete"),
        tier=2,
    )


def make_shot_volume_signal() -> Signal:
    return Signal(
        signal_id="5d3a1f0e-1a0c-5d1e-9a77-0e0f6d8c2b11",
        match_id="m-0007",
        kind="shot_volume",
        match_clock_s=2950,
        entity={"team_id": "t-home"},
        value=10,
        evidence_event_ids=[f"evt-shot-{index}" for index in range(10)],
        score={"t-home": 1},
        tier=2,
    )


def make_candidate() -> Candidate:
    return Candidate(
        candidate_id="b6bb4751-38fc-57ae-b4f4-2635502b9ec4",
        signal_id="82808bb1-7817-51a4-8a04-cdff8dc5d04e",
        match_id="m-0007",
        headline="A second goal changes the balance",
        why_it_matters="The home side has now scored twice.",
        metrics={"goal": 2},
        evidence_event_ids=["evt-0042"],
        entity_ids=["t-home"],
        team_id="t-home",
        topic="goal",
        self_salience=0.8,
        match_clock_s=4020,
    )


class FakeAgent:
    """Calls the supplied facts tool like the framework would, then returns a fixed draft."""

    def __init__(self, value: CandidateDraft) -> None:
        self.value = value
        self.prompt = ""
        self.options: dict[str, object] = {}
        self.tool_names: list[str] = []
        self.facts: dict[str, str] = {}

    async def run(self, prompt: str, *, tools: list, options: dict[str, object]) -> SimpleNamespace:
        self.prompt = prompt
        self.options = options
        self.tool_names = [t.name for t in tools]
        self.facts = await tools[0].invoke(skip_parsing=True)
        return SimpleNamespace(value=self.value)


GOAL_DRAFT = CandidateDraft(
    headline="Bram Elsen puts Northbridge ahead",
    why_it_matters="57' Bram Elsen scores with a 94 km/h strike. It's 2-1 to Northbridge Comets.",
    self_salience=0.8,
)


def test_generator_preserves_provenance_and_uses_low_reasoning() -> None:
    fake_agent = FakeAgent(GOAL_DRAFT)
    generator = FoundryCandidateGenerator(fake_agent, "goal-shot")  # type: ignore[arg-type]
    signal = make_signal()

    candidate = asyncio.run(generator.create_candidate(signal))

    assert candidate.signal_id == signal.signal_id
    assert candidate.match_id == signal.match_id
    assert candidate.metrics == {"goal": 2, "shot_speed_kmh": 94.5}
    assert candidate.evidence_event_ids == signal.evidence_event_ids
    assert candidate.entity_ids == ["t-home"]
    assert candidate.team_id == "t-home"
    assert candidate.player_id == "p-nbr-09"
    assert candidate.body_part == "foot"
    assert candidate.topic == signal.kind
    assert candidate.agent == "goal-shot"
    assert Card.from_candidate(candidate).agent == "goal-shot"
    assert candidate.ttl_s == 180
    assert fake_agent.options == {
        "response_format": CandidateDraft,
        "reasoning": {"effort": "low"},
        "tool_choice": {"mode": "required", "required_function_name": "get_event_facts"},
    }
    assert fake_agent.tool_names == ["get_event_facts"]


def test_prompt_has_no_raw_keys_or_ids_and_facts_come_from_the_tool() -> None:
    fake_agent = FakeAgent(GOAL_DRAFT)
    signal = make_signal()

    asyncio.run(FoundryCandidateGenerator(fake_agent, "goal-shot").create_candidate(signal))  # type: ignore[arg-type]

    prompt = fake_agent.prompt
    assert "get_event_facts" in prompt
    assert "Goal & Shot specialist" in prompt
    for leaked in (signal.signal_id, "t-home", "p-nbr-09", "evt-0042", "m-0007", "{", "3401"):
        assert leaked not in prompt
    assert not re.search(r"\b[a-z]+_[a-z_]+\b", prompt.replace("get_event_facts", ""))
    assert fake_agent.facts == signal_facts(signal)


def test_goal_facts_are_plain_words() -> None:
    assert signal_facts(make_signal()) == {
        "minute": "57'",
        "half": "second half",
        "team": "Northbridge Comets",
        "opponent": "Southmere Foxes",
        "player": "Bram Elsen",
        "score": "Northbridge Comets 2, Southmere Foxes 1",
        "event": "Bram Elsen scored for Northbridge Comets",
        "detail": "a 94 km/h strike",
    }


def test_pass_streak_facts() -> None:
    facts = signal_facts(make_pass_streak_signal())

    assert facts["minute"] == "21'"
    assert facts["half"] == "first half"
    assert facts["team"] == "Southmere Foxes"
    assert facts["opponent"] == "Northbridge Comets"
    assert facts["event"] == "Southmere Foxes completed 8 passes in a row"
    assert facts["score"] == "Northbridge Comets 0, Southmere Foxes 0"
    assert "player" not in facts and "detail" not in facts


def test_shot_volume_facts() -> None:
    facts = signal_facts(make_shot_volume_signal())

    assert facts["minute"] == "50'"
    assert facts["event"] == "Northbridge Comets have now taken 10 shots"
    assert facts["score"] == "Northbridge Comets 1, Southmere Foxes 0"


def test_facts_never_contain_ids_or_field_names() -> None:
    for signal in (make_signal(), make_pass_streak_signal(), make_shot_volume_signal()):
        for key, value in signal_facts(signal).items():
            assert "_" not in key
            validate_caption(value)


@pytest.mark.parametrize(
    ("clock_s", "minute"),
    [(0, "1'"), (59, "1'"), (2699, "45'"), (2700, "46'"), (5400, "90'")],
)
def test_broadcast_minute(clock_s: int, minute: str) -> None:
    assert broadcast_minute(clock_s) == minute


@pytest.mark.parametrize(
    "leak",
    [
        "Goal at match_clock_s 3401",
        "MATCH_CLOCK update",
        "Scored by p-nbr-09",
        "t-home take the lead",
        "Event e000123 confirmed",
        "Signal confirms the goal",
        "The evidence shows a goal",
        "The data says it was a goal",
        "A goal after 3401 s",
        "Goal 82808bb1-7817-51a4-8a04-cdff8dc5d04e",
    ],
)
def test_validator_rejects_leaked_internal_names(leak: str) -> None:
    with pytest.raises(ValidationError):
        CandidateDraft(headline="Goal", why_it_matters=leak, self_salience=0.5)


def test_draft_enforces_caption_lengths() -> None:
    with pytest.raises(ValidationError):
        CandidateDraft(headline="x" * 61, why_it_matters="Fine.", self_salience=0.5)
    with pytest.raises(ValidationError):
        CandidateDraft(headline="Fine", why_it_matters="x" * 181, self_salience=0.5)


def test_signal_rejects_event_context_outside_its_evidence() -> None:
    values = make_signal().model_dump()
    values["event_context"]["event_id"] = "evt-not-evidenced"

    with pytest.raises(ValueError, match="included in signal evidence"):
        Signal.model_validate(values)


def test_pass_streak_context_requires_a_completed_pass() -> None:
    values = make_pass_streak_signal().model_dump()
    values["event_context"]["outcome"] = "incomplete"

    with pytest.raises(ValueError, match="completed pass"):
        Signal.model_validate(values)


def test_candidate_id_is_stable_for_message_retries() -> None:
    generator = FoundryCandidateGenerator(FakeAgent(GOAL_DRAFT), "goal-shot")  # type: ignore[arg-type]

    first = asyncio.run(generator.create_candidate(make_signal()))
    retried = asyncio.run(generator.create_candidate(make_signal()))

    assert first.candidate_id == retried.candidate_id
    assert Candidate.model_validate_json(first.model_dump_json()) == first


def test_card_has_stable_id_and_ttl_bounded_expiry() -> None:
    candidate = make_candidate()
    created_at = datetime(2026, 10, 23, 18, 30, tzinfo=UTC)

    card = Card.from_candidate(candidate, created_at=created_at)
    repeated = Card.from_candidate(candidate, created_at=created_at)

    assert card == repeated
    assert card.team_id == "t-home"
    assert card.expires_at == created_at + timedelta(seconds=candidate.ttl_s)
    assert Card.model_validate_json(card.model_dump_json()) == card


def test_card_rejects_naive_creation_time() -> None:
    with pytest.raises(ValueError, match="timezone"):
        Card.from_candidate(make_candidate(), created_at=datetime(2026, 10, 23, 18, 30))


def test_card_rejects_naive_timestamps_when_constructed_directly() -> None:
    card = Card.from_candidate(make_candidate())
    values = card.model_dump()
    values["created_at"] = datetime(2026, 10, 23, 18, 30)

    with pytest.raises(ValueError, match="timezone"):
        Card.model_validate(values)


def test_card_rejects_expiry_that_does_not_match_ttl() -> None:
    card = Card.from_candidate(
        make_candidate(),
        created_at=datetime(2026, 10, 23, 18, 30, tzinfo=UTC),
    )
    values = card.model_dump()
    values["expires_at"] += timedelta(seconds=1)

    with pytest.raises(ValueError, match="TTL"):
        Card.model_validate(values)


def test_unknown_team_or_player_raises_value_error_not_stop_iteration() -> None:
    with pytest.raises(ValueError, match="unknown team_id"):
        event_facts(kind="goal", value=1, clock_s=600, team_id="t-ghost")
    ghost_player = Signal(
        signal_id="signal-ghost",
        match_id="m-0007",
        kind="pass_streak",
        match_clock_s=600,
        entity={"player_id": "p-ghost"},
        value=8,
        evidence_event_ids=["evt-1"],
        tier=2,
    )
    with pytest.raises(ValueError, match="unknown player_id"):
        signal_team_id(ghost_player)


@pytest.mark.parametrize("clock_s", [600, 3600])
@pytest.mark.parametrize("kind", ["goal", "penalty", "red_card", "shot_volume", "pass_streak"])
def test_template_captions_pass_validation_for_every_catalog_name(kind: str, clock_s: int) -> None:
    """A catalog name that trips the leak validator would fail every fallback for that player."""
    catalog = _catalog()
    for player in catalog.players:
        facts = event_facts(
            kind=kind,
            value=12,
            clock_s=clock_s,
            team_id=player.club_id,
            player_id=player.id,
            score={team.id: 2 for team in catalog.teams},
            speed_kmh=104,
            body_part="head",
        )
        headline, body = template_caption(kind, facts)
        assert validate_caption(headline) and len(headline) <= HEADLINE_MAX, (player.id, headline)
        assert validate_caption(body) and len(body) <= BODY_MAX, (player.id, body)
